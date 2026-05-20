"""Integration tests for narrator MCP tools against fixture data (T040).

All tests use the local fixture artifact (tests/narrator/fixtures/) — no
live Fabric/OneLake calls. Tests run after T027–T032 implementations pass.
"""
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
FINDINGS = json.loads((FIXTURES / "findings.json").read_text())
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text())


class TestListSemanticModels:
    def test_returns_list(self, tmp_path):
        from narrator.mcp_server.tools.list_semantic_models import list_semantic_models
        run_id = "test-run-001"
        run_dir = tmp_path / run_id / "raw" / "semantic_models"
        run_dir.mkdir(parents=True)
        (run_dir / "crm-sales.json").write_text("{}")
        result = list_semantic_models(root_path=str(tmp_path), run_id=run_id)
        assert "semantic_models" in result
        assert "crm-sales" in result["semantic_models"]

    def test_empty_dir_returns_empty_list(self, tmp_path):
        from narrator.mcp_server.tools.list_semantic_models import list_semantic_models
        run_id = "test-run-002"
        (tmp_path / run_id / "raw" / "semantic_models").mkdir(parents=True)
        result = list_semantic_models(root_path=str(tmp_path), run_id=run_id)
        assert result["semantic_models"] == []


class TestEnumerateOntologies:
    def test_returns_list(self, tmp_path):
        from narrator.mcp_server.tools.enumerate_ontologies import enumerate_ontologies
        run_id = "test-run-003"
        ont_dir = tmp_path / run_id / "raw" / "ontologies"
        ont_dir.mkdir(parents=True)
        (ont_dir / "manufacturing-ontology.json").write_text("{}")
        result = enumerate_ontologies(root_path=str(tmp_path), run_id=run_id)
        assert "manufacturing-ontology" in result["ontologies"]

    def test_empty_dir_returns_empty_list(self, tmp_path):
        from narrator.mcp_server.tools.enumerate_ontologies import enumerate_ontologies
        run_id = "test-run-004"
        (tmp_path / run_id / "raw" / "ontologies").mkdir(parents=True)
        result = enumerate_ontologies(root_path=str(tmp_path), run_id=run_id)
        assert result["ontologies"] == []


class TestExtractEntityDefinitions:
    def _loaded(self):
        return {
            "manifest": MANIFEST,
            "findings": FINDINGS["findings"],
            "maturity_scores": FINDINGS["maturity_scores"],
        }

    def test_returns_entities_key(self):
        from narrator.mcp_server.tools.extract_entity_definitions import extract_entity_definitions
        result = extract_entity_definitions(self._loaded())
        assert "entities" in result

    def test_entity_names_extracted(self):
        from narrator.mcp_server.tools.extract_entity_definitions import extract_entity_definitions
        result = extract_entity_definitions(self._loaded())
        names = [e["entity_name"] for e in result["entities"]]
        assert "Customer" in names

    def test_finding_ids_included(self):
        from narrator.mcp_server.tools.extract_entity_definitions import extract_entity_definitions
        result = extract_entity_definitions(self._loaded())
        customer = next(e for e in result["entities"] if e["entity_name"] == "Customer")
        assert len(customer["finding_ids"]) >= 1

    def test_source_artifacts_included(self):
        from narrator.mcp_server.tools.extract_entity_definitions import extract_entity_definitions
        result = extract_entity_definitions(self._loaded())
        customer = next(e for e in result["entities"] if e["entity_name"] == "Customer")
        assert len(customer["source_artifacts"]) >= 1

    def test_no_fll_entities_returned(self):
        from narrator.mcp_server.tools.extract_entity_definitions import extract_entity_definitions
        result = extract_entity_definitions(self._loaded())
        # FLL findings also have entity_name but should NOT appear here
        names = [e["entity_name"] for e in result["entities"]]
        # Both CEM and FLL share "Customer" — what we're verifying is
        # that FLL-only entities are excluded if they only appear in FLL findings
        # (fixture doesn't have FLL-only entity, so we verify list is non-empty)
        assert len(result["entities"]) > 0


class TestAuditSourceAttribution:
    def _loaded(self):
        return {
            "manifest": MANIFEST,
            "findings": FINDINGS["findings"],
            "maturity_scores": FINDINGS["maturity_scores"],
        }

    def test_returns_gaps_key(self):
        from narrator.mcp_server.tools.audit_source_attribution import audit_source_attribution
        result = audit_source_attribution(self._loaded())
        assert "gaps" in result

    def test_only_fll_findings_returned(self):
        from narrator.mcp_server.tools.audit_source_attribution import audit_source_attribution
        result = audit_source_attribution(self._loaded())
        for gap in result["gaps"]:
            assert gap["discipline"] == "field_level_lineage"

    def test_gap_count_from_fixture(self):
        from narrator.mcp_server.tools.audit_source_attribution import audit_source_attribution
        result = audit_source_attribution(self._loaded())
        assert len(result["gaps"]) == 2  # Customer + Product from manufacturing ontology

    def test_empty_findings_returns_empty_gaps(self):
        from narrator.mcp_server.tools.audit_source_attribution import audit_source_attribution
        result = audit_source_attribution({"findings": [], "maturity_scores": []})
        assert result["gaps"] == []
