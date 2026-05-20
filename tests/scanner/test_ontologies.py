"""Tests for ontologies.py — written before implementation (T017).

Tests verify:
- Ontology extraction: entity type count, property list
- is_source_attribution classification from fixture
- DataBinding has_temporal_source_marker field
- Graceful degradation when ontology API returns 404 (preview feature absent)
"""
import json
from pathlib import Path

import pytest

from scanner.lib.scanner.ontologies import extract_ontologies_from_response, handle_ontology_404
from scanner.lib.scanner.findings import Ontology

FIXTURES = Path(__file__).parent / "fixtures" / "fabric_iq_responses"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture()
def manufacturing_response():
    return load_fixture("manufacturing_ontology.json")


class TestOntologyExtraction:
    def test_ontology_id_and_name(self, manufacturing_response):
        ontologies = extract_ontologies_from_response(manufacturing_response, workspace_id="contoso-workspace-guid-0001")
        assert len(ontologies) == 1
        o = ontologies[0]
        assert o.ontology_id == "manufacturing-ontology-guid-001"
        assert o.name == "Manufacturing-Ontology"
        assert o.workspace_id == "contoso-workspace-guid-0001"

    def test_entity_type_count(self, manufacturing_response):
        ontologies = extract_ontologies_from_response(manufacturing_response, workspace_id="ws-001")
        assert len(ontologies[0].entity_types) == 3

    def test_entity_type_names(self, manufacturing_response):
        ontologies = extract_ontologies_from_response(manufacturing_response, workspace_id="ws-001")
        names = {et.name for et in ontologies[0].entity_types}
        assert "Customer" in names
        assert "Product" in names
        assert "Vendor" in names


class TestSourceAttributionClassification:
    def test_customer_has_no_source_attribution_properties(self, manufacturing_response):
        ontologies = extract_ontologies_from_response(manufacturing_response, workspace_id="ws-001")
        customer = next(et for et in ontologies[0].entity_types if et.name == "Customer")
        attribution_props = [p for p in customer.properties if p.is_source_attribution]
        assert attribution_props == []

    def test_vendor_has_four_source_attribution_properties(self, manufacturing_response):
        ontologies = extract_ontologies_from_response(manufacturing_response, workspace_id="ws-001")
        vendor = next(et for et in ontologies[0].entity_types if et.name == "Vendor")
        attribution_props = [p for p in vendor.properties if p.is_source_attribution]
        assert len(attribution_props) == 4

    def test_property_names_preserved(self, manufacturing_response):
        ontologies = extract_ontologies_from_response(manufacturing_response, workspace_id="ws-001")
        vendor = next(et for et in ontologies[0].entity_types if et.name == "Vendor")
        prop_names = {p.name for p in vendor.properties}
        assert "vendor_name" in prop_names
        assert "extracted_at" in prop_names


class TestDataBindings:
    def test_vendor_binding_has_temporal_marker(self, manufacturing_response):
        ontologies = extract_ontologies_from_response(manufacturing_response, workspace_id="ws-001")
        vendor = next(et for et in ontologies[0].entity_types if et.name == "Vendor")
        assert len(vendor.bindings) == 1
        assert vendor.bindings[0].has_temporal_source_marker is True

    def test_customer_binding_no_temporal_marker(self, manufacturing_response):
        ontologies = extract_ontologies_from_response(manufacturing_response, workspace_id="ws-001")
        customer = next(et for et in ontologies[0].entity_types if et.name == "Customer")
        assert customer.bindings[0].has_temporal_source_marker is False

    def test_binding_source_type_and_id(self, manufacturing_response):
        ontologies = extract_ontologies_from_response(manufacturing_response, workspace_id="ws-001")
        customer = next(et for et in ontologies[0].entity_types if et.name == "Customer")
        b = customer.bindings[0]
        assert b.source_type == "semantic_model"
        assert b.source_id == "crm-sales-model-guid-001"


class TestGracefulDegradation:
    def test_empty_value_list_returns_empty(self):
        ontologies = extract_ontologies_from_response({"value": []}, workspace_id="ws-001")
        assert ontologies == []

    def test_handle_404_returns_empty_list(self):
        result = handle_ontology_404(workspace_id="ws-001")
        assert result == []

    def test_handle_404_does_not_raise(self):
        # Should be callable without raising any exception.
        handle_ontology_404(workspace_id="any-workspace-id")


class TestOntologyPerItemErrorIsolation:
    """Verify one malformed ontology item never aborts extraction of valid items."""

    def test_ontology_missing_id_is_skipped(self):
        payload = {
            "value": [
                {"name": "BadOntology"},          # missing "id" → skipped
                {"id": "good-ont", "name": "GoodOnt", "entityTypes": []},
            ]
        }
        ontologies = extract_ontologies_from_response(payload, workspace_id="ws-001")
        assert len(ontologies) == 1
        assert ontologies[0].ontology_id == "good-ont"

    def test_entity_type_missing_name_is_skipped(self):
        payload = {
            "value": [
                {
                    "id": "ont-1",
                    "name": "Ont1",
                    "entityTypes": [
                        {"properties": []},              # missing "name" → skipped
                        {"name": "GoodType", "properties": [], "relationships": [], "bindings": []},
                    ],
                }
            ]
        }
        ontologies = extract_ontologies_from_response(payload, workspace_id="ws-001")
        assert len(ontologies[0].entity_types) == 1
        assert ontologies[0].entity_types[0].name == "GoodType"


class TestOntologyContinuationToken:
    """Verify extract_ontologies_from_response handles multi-page responses correctly."""

    def test_multi_page_response_combined(self):
        # Simulate caller accumulating pages before calling extract_ontologies_from_response
        page1 = {"id": "ont-p1", "name": "Ont1", "entityTypes": []}
        page2 = {"id": "ont-p2", "name": "Ont2", "entityTypes": []}
        combined = {"value": [page1, page2]}
        ontologies = extract_ontologies_from_response(combined, workspace_id="ws-001")
        assert len(ontologies) == 2
        ids = {o.ontology_id for o in ontologies}
        assert "ont-p1" in ids
        assert "ont-p2" in ids


class TestOntologyGetWithRetry:
    """Verify ontologies._get_with_retry retries 429/503."""

    def test_429_triggers_retry_then_succeeds(self, requests_mock):
        from scanner.lib.scanner.ontologies import _get_with_retry
        import unittest.mock as mock

        call_count = {"n": 0}

        def side_effect(request, context):
            call_count["n"] += 1
            if call_count["n"] < 2:
                context.status_code = 429
            else:
                context.status_code = 200
            return {}

        requests_mock.get("https://example.com/ont-test", json=side_effect)

        with mock.patch("time.sleep"):
            resp = _get_with_retry("https://example.com/ont-test", {})

        assert resp.status_code == 200
        assert call_count["n"] == 2

    def test_503_retries_exhausted_returns_last_response(self, requests_mock):
        from scanner.lib.scanner.ontologies import _get_with_retry
        import unittest.mock as mock

        requests_mock.get("https://example.com/ont-503", status_code=503)

        with mock.patch("time.sleep"):
            resp = _get_with_retry("https://example.com/ont-503", {})

        assert resp.status_code == 503
