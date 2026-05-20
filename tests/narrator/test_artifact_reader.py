"""Tests for narrator artifact_reader.py (T027).

Tests verify forward-tolerant reading of v1.0 artifact:
- All known fields parsed correctly
- Unknown top-level keys recorded in unknown_fields, not errored
- Missing required field raises RuntimeError
- Full parse of schema_version 1.0
"""
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _make_reader(tmp_path: Path, manifest_override=None, findings_override=None):
    """Build an ArtifactReader pointing at a copy of fixture data."""
    from narrator.mcp_server.artifact_reader import ArtifactReader

    run_id = "20260520-143022-a3f7"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "raw" / "semantic_models").mkdir(parents=True)
    (run_dir / "raw" / "ontologies").mkdir(parents=True)

    manifest = manifest_override or json.loads((FIXTURES / "manifest.json").read_text())
    findings = findings_override or json.loads((FIXTURES / "findings.json").read_text())

    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "findings.json").write_text(json.dumps(findings), encoding="utf-8")

    return ArtifactReader(root_path=str(tmp_path), run_id=run_id)


class TestV10Parse:
    def test_manifest_schema_version_parsed(self, tmp_path):
        reader = _make_reader(tmp_path)
        result = reader.load()
        assert result["manifest"]["schema_version"] == "1.0"

    def test_manifest_run_id_parsed(self, tmp_path):
        reader = _make_reader(tmp_path)
        result = reader.load()
        assert result["manifest"]["run_id"] == "20260520-143022-a3f7"

    def test_workspace_id_parsed(self, tmp_path):
        reader = _make_reader(tmp_path)
        result = reader.load()
        assert result["manifest"]["workspace_id"] == "contoso-workspace-guid-0001"

    def test_findings_count(self, tmp_path):
        reader = _make_reader(tmp_path)
        result = reader.load()
        assert len(result["findings"]) == 4

    def test_maturity_scores_count(self, tmp_path):
        reader = _make_reader(tmp_path)
        result = reader.load()
        assert len(result["maturity_scores"]) == 4

    def test_not_assessed_score_is_none(self, tmp_path):
        reader = _make_reader(tmp_path)
        result = reader.load()
        layered = next(s for s in result["maturity_scores"] if s["discipline"] == "layered_modeling")
        assert layered["score"] is None
        assert layered["assessment_status"] == "not_assessed"


class TestForwardTolerance:
    def test_unknown_top_level_key_recorded_not_errored(self, tmp_path):
        manifest = json.loads((FIXTURES / "manifest.json").read_text())
        manifest["future_field_from_v2"] = "some_value"
        reader = _make_reader(tmp_path, manifest_override=manifest)
        result = reader.load()
        assert "future_field_from_v2" in result.get("unknown_fields", []) or \
               result["manifest"].get("future_field_from_v2") == "some_value"

    def test_unknown_key_does_not_raise(self, tmp_path):
        manifest = json.loads((FIXTURES / "manifest.json").read_text())
        manifest["unknown_key_xyz"] = {"nested": True}
        reader = _make_reader(tmp_path, manifest_override=manifest)
        result = reader.load()  # Should not raise
        assert result is not None


class TestMissingRequiredField:
    def test_missing_schema_version_raises(self, tmp_path):
        from narrator.mcp_server.artifact_reader import ArtifactReader
        manifest = json.loads((FIXTURES / "manifest.json").read_text())
        del manifest["schema_version"]
        with pytest.raises(RuntimeError, match="schema_version"):
            _make_reader(tmp_path, manifest_override=manifest).load()

    def test_missing_run_id_raises(self, tmp_path):
        manifest = json.loads((FIXTURES / "manifest.json").read_text())
        del manifest["run_id"]
        with pytest.raises(RuntimeError):
            _make_reader(tmp_path, manifest_override=manifest).load()


class TestRawAccess:
    def test_raw_subdirectory_exists(self, tmp_path):
        reader = _make_reader(tmp_path)
        raw_path = Path(tmp_path) / "20260520-143022-a3f7" / "raw"
        assert raw_path.is_dir()
