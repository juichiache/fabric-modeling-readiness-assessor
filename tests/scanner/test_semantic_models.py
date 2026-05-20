"""Tests for semantic_models.py — written before implementation (T016).

Tests verify:
- SemanticModel extraction: table count, relationship list, measure names
- Primary key columns extraction
- Source columns (column names) extraction
- Graceful handling of models with no declared primary keys
"""
import json
from pathlib import Path

import pytest

from scanner.lib.scanner.semantic_models import extract_semantic_models_from_response
from scanner.lib.scanner.findings import SemanticModel

FIXTURES = Path(__file__).parent / "fixtures" / "power_bi_rest_responses"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture()
def crm_response():
    return load_fixture("crm_sales.json")


@pytest.fixture()
def erp_response():
    return load_fixture("erp_finance.json")


@pytest.fixture()
def invoicing_response():
    return load_fixture("invoicing_legacy.json")


class TestCrmSalesExtraction:
    def test_model_id_and_name(self, crm_response):
        models = extract_semantic_models_from_response(crm_response, workspace_id="ws-001")
        assert len(models) == 1
        m = models[0]
        assert m.model_id == "crm-sales-model-guid-001"
        assert m.name == "CRM-Sales"
        assert m.workspace_id == "ws-001"

    def test_table_count(self, crm_response):
        models = extract_semantic_models_from_response(crm_response, workspace_id="ws-001")
        assert len(models[0].tables) == 3

    def test_customer_table_primary_key(self, crm_response):
        models = extract_semantic_models_from_response(crm_response, workspace_id="ws-001")
        customer_table = next(t for t in models[0].tables if t.name == "Customer")
        assert customer_table.primary_key_columns == ["CustomerGUID"]

    def test_customer_table_source_columns(self, crm_response):
        models = extract_semantic_models_from_response(crm_response, workspace_id="ws-001")
        customer_table = next(t for t in models[0].tables if t.name == "Customer")
        assert "CustomerGUID" in customer_table.source_columns
        assert "CustomerName" in customer_table.source_columns

    def test_relationships_extracted(self, crm_response):
        models = extract_semantic_models_from_response(crm_response, workspace_id="ws-001")
        rels = models[0].relationships
        assert len(rels) == 2
        rel_pairs = {(r.from_table, r.to_table) for r in rels}
        assert ("SalesOrder", "Customer") in rel_pairs

    def test_measures_extracted(self, crm_response):
        models = extract_semantic_models_from_response(crm_response, workspace_id="ws-001")
        measure_names = {m.name for m in models[0].measures}
        assert "Total Revenue" in measure_names
        assert "Customer Count" in measure_names


class TestErpFinanceExtraction:
    def test_model_id(self, erp_response):
        models = extract_semantic_models_from_response(erp_response, workspace_id="ws-001")
        assert models[0].model_id == "erp-finance-model-guid-002"

    def test_account_table_primary_key(self, erp_response):
        models = extract_semantic_models_from_response(erp_response, workspace_id="ws-001")
        account_table = next(t for t in models[0].tables if t.name == "Account")
        assert account_table.primary_key_columns == ["AccountNumber"]

    def test_material_table_exists(self, erp_response):
        models = extract_semantic_models_from_response(erp_response, workspace_id="ws-001")
        table_names = {t.name for t in models[0].tables}
        assert "Material" in table_names


class TestInvoicingLegacyExtraction:
    def test_invoicing_model_id(self, invoicing_response):
        models = extract_semantic_models_from_response(invoicing_response, workspace_id="ws-001")
        assert models[0].model_id == "invoicing-legacy-model-guid-003"

    def test_customer_primary_key_is_invoice_customer_id(self, invoicing_response):
        models = extract_semantic_models_from_response(invoicing_response, workspace_id="ws-001")
        customer_table = next(t for t in models[0].tables if t.name == "Customer")
        assert customer_table.primary_key_columns == ["InvoiceCustomerID"]

    def test_no_measures_gracefully_handled(self, invoicing_response):
        models = extract_semantic_models_from_response(invoicing_response, workspace_id="ws-001")
        assert models[0].measures == []


class TestNoPrimaryKeyGrace:
    def test_table_without_primary_key_has_empty_list(self):
        response = {
            "value": [
                {
                    "id": "no-pk-model-guid",
                    "name": "NoPKModel",
                    "tables": [
                        {
                            "name": "NoKeyTable",
                            "columns": [
                                {"name": "Col1", "dataType": "text", "columnType": "data"}
                            ]
                        }
                    ],
                    "relationships": [],
                    "measures": [],
                }
            ]
        }
        models = extract_semantic_models_from_response(response, workspace_id="ws-001")
        no_pk_table = next(t for t in models[0].tables if t.name == "NoKeyTable")
        assert no_pk_table.primary_key_columns == []


class TestPerItemErrorIsolation:
    """Verify one malformed item never aborts extraction of remaining valid items."""

    def test_model_missing_id_is_skipped(self):
        response = {
            "value": [
                {"name": "BadModel"},          # missing "id" → should be skipped
                {"id": "good-id", "name": "GoodModel", "tables": [], "relationships": [], "measures": []},
            ]
        }
        models = extract_semantic_models_from_response(response, workspace_id="ws-001")
        assert len(models) == 1
        assert models[0].model_id == "good-id"

    def test_table_missing_name_is_skipped(self):
        response = {
            "value": [
                {
                    "id": "model-1",
                    "name": "M1",
                    "tables": [
                        {"columns": []},            # missing "name" → skipped
                        {"name": "GoodTable", "columns": []},
                    ],
                    "relationships": [],
                    "measures": [],
                }
            ]
        }
        models = extract_semantic_models_from_response(response, workspace_id="ws-001")
        assert len(models) == 1
        assert len(models[0].tables) == 1
        assert models[0].tables[0].name == "GoodTable"

    def test_relationship_missing_from_table_is_skipped(self):
        response = {
            "value": [
                {
                    "id": "model-2",
                    "name": "M2",
                    "tables": [],
                    "relationships": [
                        {"fromColumn": "c", "toTable": "T", "toColumn": "c2"},  # missing fromTable
                        {"fromTable": "A", "fromColumn": "id", "toTable": "B", "toColumn": "id"},
                    ],
                    "measures": [],
                }
            ]
        }
        models = extract_semantic_models_from_response(response, workspace_id="ws-001")
        assert len(models[0].relationships) == 1


class TestGetWithRetry:
    """Verify _get_with_retry retries 429/503 and propagates non-retryable errors."""

    def test_429_triggers_retry_then_succeeds(self, requests_mock):
        from scanner.lib.scanner.semantic_models import _get_with_retry
        import unittest.mock as mock

        call_count = {"n": 0}

        def side_effect(request, context):
            call_count["n"] += 1
            if call_count["n"] < 2:
                context.status_code = 429
            else:
                context.status_code = 200
            return {}

        requests_mock.get("https://example.com/test", json=side_effect)

        with mock.patch("time.sleep"):
            resp = _get_with_retry("https://example.com/test", {})

        assert resp.status_code == 200
        assert call_count["n"] == 2

    def test_503_retries_then_propagates_on_exhaustion(self, requests_mock):
        from scanner.lib.scanner.semantic_models import _get_with_retry
        import unittest.mock as mock

        requests_mock.get("https://example.com/test503", status_code=503)

        with mock.patch("time.sleep"):
            resp = _get_with_retry("https://example.com/test503", {})

        # After retries exhausted, returns the last 503 response
        assert resp.status_code == 503

    def test_non_retryable_error_returned_immediately(self, requests_mock):
        from scanner.lib.scanner.semantic_models import _get_with_retry

        requests_mock.get("https://example.com/test403", status_code=403)
        resp = _get_with_retry("https://example.com/test403", {})
        assert resp.status_code == 403
