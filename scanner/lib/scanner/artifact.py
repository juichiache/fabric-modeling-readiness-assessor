"""Findings artifact writer for the Modeling Readiness Assessor scanner.

Writes the schema-versioned findings artifact to a local path (which may be
an OneLake-mounted directory in a Fabric notebook or a local temp dir in tests).

Artifact layout:
    <output_root>/<run_id>/
        manifest.json
        findings.json
        raw/
            semantic_models/<model-id>.json
            ontologies/<ontology-id>.json
"""
from __future__ import annotations

import dataclasses
import datetime
import json
import os
import random
import string
from pathlib import Path

from scanner.lib.scanner.findings import (
    Finding,
    MaturityScore,
    ScanScope,
)

SCHEMA_VERSION = "1.0"


def _generate_run_id() -> str:
    """Return a sortable run_id: YYYYMMDD-HHmmss-<4-char-hex>."""
    now = datetime.datetime.now(datetime.timezone.utc)
    suffix = "".join(random.choices(string.hexdigits[:16].lower(), k=4))
    return now.strftime("%Y%m%d-%H%M%S-") + suffix


class FindingsArtifactWriter:
    """Writes a complete findings artifact directory to output_root/<run_id>/."""

    def __init__(
        self,
        output_root: str,
        workspace_id: str,
        workspace_url: str,
        scanner_version: str,
        scope: ScanScope,
    ) -> None:
        self.output_root = Path(output_root)
        self.workspace_id = workspace_id
        self.workspace_url = workspace_url
        self.scanner_version = scanner_version
        self.scope = scope
        self.run_id = _generate_run_id()
        self._run_dir: Path | None = None

    @property
    def run_dir(self) -> Path:
        if self._run_dir is None:
            raise RuntimeError("write() must be called before accessing run_dir.")
        return self._run_dir

    def write(
        self,
        findings: list[Finding],
        maturity_scores: list[MaturityScore],
        artifact_counts: dict[str, int] | None = None,
    ) -> Path:
        """Write manifest.json, findings.json, and raw/ subdirectory.

        Returns the path to the run directory.
        """
        run_dir = self.output_root / self.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self._run_dir = run_dir

        # Create raw/ subdirectories eagerly (required by tests).
        (run_dir / "raw" / "semantic_models").mkdir(parents=True, exist_ok=True)
        (run_dir / "raw" / "ontologies").mkdir(parents=True, exist_ok=True)

        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "timestamp": timestamp,
            "scanner_version": self.scanner_version,
            "workspace_id": self.workspace_id,
            "workspace_url": self.workspace_url,
            "scope": dataclasses.asdict(self.scope),
            "artifact_counts": artifact_counts or {},
        }
        _write_json(run_dir / "manifest.json", manifest)

        findings_doc = {
            "schema_version": SCHEMA_VERSION,
            "findings": [_finding_to_dict(f) for f in findings],
            "maturity_scores": [dataclasses.asdict(s) for s in maturity_scores],
        }
        _write_json(run_dir / "findings.json", findings_doc)

        return run_dir

    def write_raw(self, category: str, item_id: str, data: dict) -> Path:
        """Write a raw API response to raw/<category>/<item_id>.json."""
        if self._run_dir is None:
            raise RuntimeError("write() must be called before write_raw().")
        dest = self._run_dir / "raw" / category / f"{item_id}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        _write_json(dest, data)
        return dest


def _finding_to_dict(f: Finding) -> dict:
    return dataclasses.asdict(f)


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
