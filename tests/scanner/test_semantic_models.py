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
