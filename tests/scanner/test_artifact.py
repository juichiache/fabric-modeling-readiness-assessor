"""Tests for artifact.py — must be written before artifact.py is implemented.

Tests verify:
- manifest.json contains all required fields
- run_id matches the YYYYMMDD-HHmmss-<4-char-hex> format
- findings.json schema_version matches manifest.json
- raw/ subfolder is created
"""
import json
import re
import time
from pathlib import Path

import pytest

from scanner.lib.scanner.artifact import FindingsArtifactWriter
from scanner.lib.scanner.findings import (
    Finding,
    MaturityScore,
    ScanScope,
    SourceArtifactRef,
)


MANIFEST_REQUIRED_FIELDS = {
    "schema_version",
    "run_id",
    "timestamp",
    "scanner_version",
    "workspace_id",
    "workspace_url",
    "scope",
    "artifact_counts",
}

RUN_ID_PATTERN = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")

SAMPLE_FINDING = Finding(
    finding_id="cem-001",
    discipline="canonical_entity_modeling",
    severity="high",
    description="Customer entity defined differently in CRM-Sales and ERP-Finance.",
    source_artifacts=[
        SourceArtifactRef("semantic_model", "model-guid-001", "CRM-Sales"),
        SourceArtifactRef("semantic_model", "model-guid-002", "ERP-Finance"),
    ],
    remediation_hint="Align primary key columns across both models.",
    entity_name="Customer",
)

SAMPLE_SCORE = MaturityScore(
    discipline="canonical_entity_modeling",
    score=2,
    assessment_status="assessed",
    finding_count=3,
    rationale="3 canonical entity conflicts detected across CRM-Sales and ERP-Finance.",
    rubric_version="1.0",
)

SAMPLE_SCOPE = ScanScope(type="full")


@pytest.fixture()
def writer(tmp_path):
    return FindingsArtifactWriter(
        output_root=str(tmp_path),
        workspace_id="ws-guid-test-0001",
        workspace_url="https://app.fabric.microsoft.com/groups/ws-guid-test-0001",
        scanner_version="0.1.0",
        scope=SAMPLE_SCOPE,
    )


class TestManifestStructure:
    def test_all_required_fields_present(self, writer, tmp_path):
        writer.write(findings=[SAMPLE_FINDING], maturity_scores=[SAMPLE_SCORE])
        run_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        assert len(run_dirs) == 1
        manifest = json.loads((run_dirs[0] / "manifest.json").read_text())
        missing = MANIFEST_REQUIRED_FIELDS - manifest.keys()
        assert not missing, f"Missing manifest fields: {missing}"

    def test_schema_version_is_1_0(self, writer, tmp_path):
        writer.write(findings=[], maturity_scores=[])
        run_dir = next(d for d in tmp_path.iterdir() if d.is_dir())
        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert manifest["schema_version"] == "1.0"

    def test_workspace_id_matches(self, writer, tmp_path):
        writer.write(findings=[], maturity_scores=[])
        run_dir = next(d for d in tmp_path.iterdir() if d.is_dir())
        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert manifest["workspace_id"] == "ws-guid-test-0001"

    def test_artifact_counts_present(self, writer, tmp_path):
        writer.write(findings=[], maturity_scores=[], artifact_counts={"semantic_models": 3, "ontologies": 1})
        run_dir = next(d for d in tmp_path.iterdir() if d.is_dir())
        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert manifest["artifact_counts"]["semantic_models"] == 3


class TestRunIdFormat:
    def test_run_id_matches_pattern(self, writer, tmp_path):
        writer.write(findings=[], maturity_scores=[])
        run_dir = next(d for d in tmp_path.iterdir() if d.is_dir())
        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert RUN_ID_PATTERN.match(manifest["run_id"]), f"run_id {manifest['run_id']!r} does not match pattern"

    def test_run_id_is_directory_name(self, writer, tmp_path):
        writer.write(findings=[], maturity_scores=[])
        run_dir = next(d for d in tmp_path.iterdir() if d.is_dir())
        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert run_dir.name == manifest["run_id"]

    def test_two_runs_have_different_ids(self, tmp_path):
        w1 = FindingsArtifactWriter(str(tmp_path), "ws-1", "https://example.com/1", "0.1.0", SAMPLE_SCOPE)
        time.sleep(0.01)
        w2 = FindingsArtifactWriter(str(tmp_path), "ws-1", "https://example.com/1", "0.1.0", SAMPLE_SCOPE)
        w1.write([], [])
        w2.write([], [])
        run_dirs = sorted(tmp_path.iterdir())
        assert run_dirs[0].name != run_dirs[1].name


class TestFindingsJson:
    def test_schema_version_matches_manifest(self, writer, tmp_path):
        writer.write(findings=[SAMPLE_FINDING], maturity_scores=[SAMPLE_SCORE])
        run_dir = next(d for d in tmp_path.iterdir() if d.is_dir())
        manifest = json.loads((run_dir / "manifest.json").read_text())
        findings_doc = json.loads((run_dir / "findings.json").read_text())
        assert findings_doc["schema_version"] == manifest["schema_version"]

    def test_findings_list_preserved(self, writer, tmp_path):
        writer.write(findings=[SAMPLE_FINDING], maturity_scores=[SAMPLE_SCORE])
        run_dir = next(d for d in tmp_path.iterdir() if d.is_dir())
        findings_doc = json.loads((run_dir / "findings.json").read_text())
        assert len(findings_doc["findings"]) == 1
        assert findings_doc["findings"][0]["finding_id"] == "cem-001"

    def test_maturity_scores_preserved(self, writer, tmp_path):
        writer.write(findings=[SAMPLE_FINDING], maturity_scores=[SAMPLE_SCORE])
        run_dir = next(d for d in tmp_path.iterdir() if d.is_dir())
        findings_doc = json.loads((run_dir / "findings.json").read_text())
        assert len(findings_doc["maturity_scores"]) == 1
        assert findings_doc["maturity_scores"][0]["discipline"] == "canonical_entity_modeling"


class TestRawSubfolder:
    def test_raw_directory_created(self, writer, tmp_path):
        writer.write(findings=[], maturity_scores=[])
        run_dir = next(d for d in tmp_path.iterdir() if d.is_dir())
        assert (run_dir / "raw").is_dir()

    def test_raw_semantic_models_subfolder_created(self, writer, tmp_path):
        writer.write(findings=[], maturity_scores=[])
        run_dir = next(d for d in tmp_path.iterdir() if d.is_dir())
        assert (run_dir / "raw" / "semantic_models").is_dir()

    def test_raw_ontologies_subfolder_created(self, writer, tmp_path):
        writer.write(findings=[], maturity_scores=[])
        run_dir = next(d for d in tmp_path.iterdir() if d.is_dir())
        assert (run_dir / "raw" / "ontologies").is_dir()

    def test_write_raw_model_response(self, writer, tmp_path):
        writer.write(findings=[], maturity_scores=[])
        run_dir = next(d for d in tmp_path.iterdir() if d.is_dir())
        writer.write_raw("semantic_models", "model-001", {"tables": []})
        assert (run_dir / "raw" / "semantic_models" / "model-001.json").exists()
