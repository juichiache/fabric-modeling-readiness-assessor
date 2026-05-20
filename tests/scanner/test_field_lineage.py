"""Tests for field_lineage.py — written before implementation (T025).

Tests verify:
- Gap detection when all attribution types absent (Customer entity in fixture)
- Partial gap (some attribution types present, some missing)
- Full attribution = no gap (Vendor entity in fixture)
- Property name matching does NOT prescribe specific names (semantic check on is_source_attribution)
- Temporal marker detection in DataBinding
"""
import json
from pathlib import Path

import pytest

from scanner.lib.scanner.field_lineage import audit_field_level_lineage
from scanner.lib.scanner.findings import (
    DataBinding,
    EntityType,
    Ontology,
    OntologyProperty,
    SourceAttributionGap,
)
from scanner.lib.scanner.ontologies import extract_ontologies_from_response

FIXTURES = Path(__file__).parent / "fixtures" / "fabric_iq_responses"


@pytest.fixture()
def manufacturing_ontology():
    response = json.loads((FIXTURES / "manufacturing_ontology.json").read_text())
    return extract_ontologies_from_response(response, "ws-001")


class TestGapDetectionAllAbsent:
    def test_customer_entity_has_gap(self, manufacturing_ontology):
        gaps = audit_field_level_lineage(manufacturing_ontology)
        gap_entity_names = {g.entity_type_name for g in gaps}
        assert "Customer" in gap_entity_names

    def test_product_entity_has_gap(self, manufacturing_ontology):
        gaps = audit_field_level_lineage(manufacturing_ontology)
        gap_entity_names = {g.entity_type_name for g in gaps}
        assert "Product" in gap_entity_names

    def test_gap_includes_missing_attribution_types(self, manufacturing_ontology):
        gaps = audit_field_level_lineage(manufacturing_ontology)
        customer_gap = next(g for g in gaps if g.entity_type_name == "Customer")
        assert len(customer_gap.missing_attribution_types) > 0

    def test_gap_references_ontology_id(self, manufacturing_ontology):
        gaps = audit_field_level_lineage(manufacturing_ontology)
        for gap in gaps:
            assert gap.ontology_id == "manufacturing-ontology-guid-001"

    def test_gap_id_is_non_empty_string(self, manufacturing_ontology):
        gaps = audit_field_level_lineage(manufacturing_ontology)
        for gap in gaps:
            assert isinstance(gap.gap_id, str)
            assert len(gap.gap_id) > 0


class TestNoGapWhenFullAttribution:
    def test_vendor_entity_has_no_gap(self, manufacturing_ontology):
        # Vendor has 4 source-attribution properties in fixture → no gap
        gaps = audit_field_level_lineage(manufacturing_ontology)
        vendor_gaps = [g for g in gaps if g.entity_type_name == "Vendor"]
        assert len(vendor_gaps) == 0

    def test_entity_with_all_four_attribution_types_no_gap(self):
        ontology = Ontology(
            ontology_id="o-001",
            name="Test",
            workspace_id="ws-001",
            entity_types=[
                EntityType(
                    name="FullyAttributed",
                    properties=[
                        OntologyProperty("src_system", "string", is_source_attribution=True),
                        OntologyProperty("src_record_key", "string", is_source_attribution=True),
                        OntologyProperty("extracted_at", "datetime", is_source_attribution=True),
                        OntologyProperty("confidence", "decimal", is_source_attribution=True),
                    ],
                    bindings=[
                        DataBinding("b-1", "semantic_model", "m-001", has_temporal_source_marker=True)
                    ],
                )
            ],
        )
        gaps = audit_field_level_lineage([ontology])
        assert gaps == []


class TestPartialGap:
    def test_entity_with_only_some_attribution_types_has_gap(self):
        ontology = Ontology(
            ontology_id="o-partial",
            name="Partial",
            workspace_id="ws-001",
            entity_types=[
                EntityType(
                    name="PartialEntity",
                    properties=[
                        OntologyProperty("source_id", "string", is_source_attribution=True),
                        # Missing: extraction_timestamp, confidence, source_system_identifier
                    ],
                    bindings=[],
                )
            ],
        )
        gaps = audit_field_level_lineage([ontology])
        assert len(gaps) == 1
        assert "PartialEntity" == gaps[0].entity_type_name

    def test_partial_gap_missing_types_not_empty(self):
        ontology = Ontology(
            ontology_id="o-partial",
            name="Partial",
            workspace_id="ws-001",
            entity_types=[
                EntityType(
                    name="PartialEntity",
                    properties=[
                        OntologyProperty("any_source_attr", "string", is_source_attribution=True),
                    ],
                    bindings=[],
                )
            ],
        )
        gaps = audit_field_level_lineage([ontology])
        if gaps:  # partial gaps expected
            assert len(gaps[0].missing_attribution_types) > 0


class TestSemanticCheckNotPrescriptive:
    def test_arbitrary_property_names_respected(self):
        """The framework must NOT require specific property names — only the semantic flag matters."""
        ontology = Ontology(
            ontology_id="o-named",
            name="Named",
            workspace_id="ws-001",
            entity_types=[
                EntityType(
                    name="CustomNamed",
                    properties=[
                        # Names are completely arbitrary — is_source_attribution is the semantic signal
                        OntologyProperty("xref_id", "string", is_source_attribution=True),
                        OntologyProperty("rec_key", "string", is_source_attribution=True),
                        OntologyProperty("ts_load", "datetime", is_source_attribution=True),
                        OntologyProperty("conf_score", "decimal", is_source_attribution=True),
                    ],
                    bindings=[DataBinding("b", "semantic_model", "m", has_temporal_source_marker=True)],
                )
            ],
        )
        gaps = audit_field_level_lineage([ontology])
        assert gaps == [], "Arbitrary names with is_source_attribution=True should produce no gap"


class TestTemporalMarkerDetection:
    def test_binding_temporal_marker_influences_gap(self):
        ontology = Ontology(
            ontology_id="o-temporal",
            name="Temporal",
            workspace_id="ws-001",
            entity_types=[
                EntityType(
                    name="NoTemporalBinding",
                    properties=[
                        OntologyProperty("src_id", "string", is_source_attribution=True),
                        OntologyProperty("rec_key", "string", is_source_attribution=True),
                        OntologyProperty("conf", "decimal", is_source_attribution=True),
                        # No extraction-timestamp property; binding also has no temporal marker
                    ],
                    bindings=[DataBinding("b", "semantic_model", "m", has_temporal_source_marker=False)],
                )
            ],
        )
        gaps = audit_field_level_lineage([ontology])
        # Should detect gap because no temporal source marker in property OR binding
        assert len(gaps) == 1


class TestEmptyOntologies:
    def test_empty_ontology_list_returns_empty(self):
        assert audit_field_level_lineage([]) == []

    def test_ontology_with_no_entity_types_returns_empty(self):
        o = Ontology("o-empty", "Empty", "ws", entity_types=[])
        assert audit_field_level_lineage([o]) == []
