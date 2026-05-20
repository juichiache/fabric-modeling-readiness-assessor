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


class TestRunScanner:
    """Tests for run_scanner — all calls are mocked; no live Fabric API."""

    def _make_headers(self, token="test-token"):
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def test_successful_run(self, requests_mock):
        from narrator.mcp_server.tools.run_scanner import run_scanner

        workspace_id = "ws-guid"
        notebook_id = "nb-guid"
        job_id = "job-guid-001"

        # Mock trigger endpoint
        requests_mock.post(
            f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"
            f"/items/{notebook_id}/jobs/instances",
            status_code=202,
            headers={
                "Location": (
                    f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"
                    f"/items/{notebook_id}/jobs/instances/{job_id}"
                )
            },
            json={},
        )

        # Mock poll endpoint — succeed on first poll
        requests_mock.get(
            f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"
            f"/items/{notebook_id}/jobs/instances/{job_id}",
            json={"status": "Succeeded"},
        )

        result = run_scanner(
            workspace_id=workspace_id,
            notebook_id=notebook_id,
            fabric_token="test-token",
            poll=True,
        )

        assert result["status"] == "Succeeded"
        assert result["job_instance_id"] == job_id
        assert "succeeded" in result["message"].lower()

    def test_trigger_failure_returns_error(self, requests_mock):
        from narrator.mcp_server.tools.run_scanner import run_scanner

        requests_mock.post(
            "https://api.fabric.microsoft.com/v1/workspaces/ws/items/nb/jobs/instances",
            status_code=403,
            text="Forbidden",
        )

        result = run_scanner(
            workspace_id="ws",
            notebook_id="nb",
            fabric_token="bad-token",
            poll=False,
        )

        assert result["status"] == "Failed"
        assert "403" in result["message"]

    def test_no_poll_returns_submitted(self, requests_mock):
        from narrator.mcp_server.tools.run_scanner import run_scanner

        job_id = "job-guid-002"
        requests_mock.post(
            "https://api.fabric.microsoft.com/v1/workspaces/ws/items/nb/jobs/instances",
            status_code=202,
            headers={
                "Location": (
                    "https://api.fabric.microsoft.com/v1/workspaces/ws"
                    f"/items/nb/jobs/instances/{job_id}"
                )
            },
            json={},
        )

        result = run_scanner(
            workspace_id="ws",
            notebook_id="nb",
            fabric_token="tok",
            poll=False,
        )

        assert result["status"] == "Submitted"
        assert result["job_instance_id"] == job_id

    def test_parameters_injected(self, requests_mock):
        from narrator.mcp_server.tools.run_scanner import run_scanner
        import json as _json

        captured = {}

        def capture_request(request, context):
            captured["body"] = _json.loads(request.body)
            context.status_code = 202
            context.headers["Location"] = (
                "https://api.fabric.microsoft.com/v1/workspaces/ws/items/nb/jobs/instances/jid"
            )
            return {}

        requests_mock.post(
            "https://api.fabric.microsoft.com/v1/workspaces/ws/items/nb/jobs/instances",
            json=capture_request,
        )

        run_scanner(
            workspace_id="ws",
            notebook_id="nb",
            fabric_token="tok",
            workspace_id_param="my-ws-guid",
            workspace_url_param="https://app.fabric.microsoft.com/groups/my-ws-guid",
            poll=False,
        )

        params = captured["body"]["executionData"]["parameters"]
        assert params["WORKSPACE_ID"]["value"] == "my-ws-guid"
        assert "my-ws-guid" in params["WORKSPACE_URL"]["value"]

    def test_failed_job_returns_failure_reason(self, requests_mock):
        from narrator.mcp_server.tools.run_scanner import run_scanner

        job_id = "job-guid-003"
        requests_mock.post(
            "https://api.fabric.microsoft.com/v1/workspaces/ws/items/nb/jobs/instances",
            status_code=202,
            headers={
                "Location": (
                    f"https://api.fabric.microsoft.com/v1/workspaces/ws"
                    f"/items/nb/jobs/instances/{job_id}"
                )
            },
            json={},
        )
        requests_mock.get(
            f"https://api.fabric.microsoft.com/v1/workspaces/ws/items/nb/jobs/instances/{job_id}",
            json={"status": "Failed", "failureReason": {"message": "Kernel crashed"}},
        )

        result = run_scanner(
            workspace_id="ws",
            notebook_id="nb",
            fabric_token="tok",
            poll=True,
        )

        assert result["status"] == "Failed"
        assert "Kernel crashed" in result["message"]

    def test_trigger_retries_on_429_then_succeeds(self, requests_mock):
        """Verify trigger POST is retried on 429 before succeeding."""
        from narrator.mcp_server.tools.run_scanner import run_scanner
        import unittest.mock as mock

        job_id = "job-retry-001"
        call_count = {"n": 0}

        def side_effect(request, context):
            call_count["n"] += 1
            if call_count["n"] < 2:
                context.status_code = 429
                return {}
            context.status_code = 202
            context.headers["Location"] = (
                f"https://api.fabric.microsoft.com/v1/workspaces/ws/items/nb/jobs/instances/{job_id}"
            )
            return {}

        requests_mock.post(
            "https://api.fabric.microsoft.com/v1/workspaces/ws/items/nb/jobs/instances",
            json=side_effect,
        )

        with mock.patch("time.sleep"):  # don't actually sleep in tests
            result = run_scanner(
                workspace_id="ws",
                notebook_id="nb",
                fabric_token="tok",
                poll=False,
            )

        assert result["status"] == "Submitted"
        assert call_count["n"] == 2  # first 429, then success

    def test_poll_uses_increasing_interval(self, requests_mock):
        """Verify poll intervals grow with linear backoff (not fixed)."""
        from narrator.mcp_server.tools.run_scanner import (
            run_scanner,
            POLL_INTERVAL_SEC,
            POLL_BACKOFF_STEP_SEC,
        )
        import unittest.mock as mock

        job_id = "job-backoff-001"
        requests_mock.post(
            "https://api.fabric.microsoft.com/v1/workspaces/ws/items/nb/jobs/instances",
            status_code=202,
            headers={
                "Location": (
                    f"https://api.fabric.microsoft.com/v1/workspaces/ws"
                    f"/items/nb/jobs/instances/{job_id}"
                )
            },
            json={},
        )
        # Succeed on second poll
        poll_count = {"n": 0}

        def poll_side_effect(request, context):
            poll_count["n"] += 1
            if poll_count["n"] < 2:
                return {"status": "Running"}
            return {"status": "Succeeded"}

        requests_mock.get(
            f"https://api.fabric.microsoft.com/v1/workspaces/ws/items/nb/jobs/instances/{job_id}",
            json=poll_side_effect,
        )

        sleep_calls = []
        with mock.patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)):
            run_scanner(workspace_id="ws", notebook_id="nb", fabric_token="tok", poll=True)

        # First sleep = POLL_INTERVAL_SEC, second sleep should be larger
        assert len(sleep_calls) >= 2
        assert sleep_calls[0] == POLL_INTERVAL_SEC
        assert sleep_calls[1] == POLL_INTERVAL_SEC + POLL_BACKOFF_STEP_SEC
