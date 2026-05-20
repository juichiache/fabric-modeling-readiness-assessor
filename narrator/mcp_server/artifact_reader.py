"""Forward-tolerant findings artifact reader for the Modeling Readiness narrator.

Reads manifest.json and findings.json from a local or OneLake-mounted run directory.
Unknown top-level keys are recorded in the returned dict under 'unknown_fields'
and never cause errors (forward compatibility for schema v1.x additions).

FR-023: Forward-tolerant artifact reading.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
MANIFEST_REQUIRED = {"schema_version", "run_id", "timestamp", "workspace_id", "workspace_url", "scope", "artifact_counts"}
MANIFEST_KNOWN = MANIFEST_REQUIRED | {"scanner_version"}


class ArtifactReader:
    """Reads a findings artifact from a local path (real OneLake mount or test fixture).

    For live OneLake reads, mount the OneLake filesystem before constructing this reader
    (or use the DataLakeServiceClient variant in artifact_reader_onelake.py).
    """

    def __init__(self, root_path: str, run_id: str) -> None:
        self.root_path = Path(root_path)
        self.run_id = run_id
        self._run_dir = self.root_path / run_id

    def load(self) -> dict[str, Any]:
        """Load and return the complete artifact.

        Returns a dict with keys:
            manifest: dict of known manifest fields
            findings: list of finding dicts
            maturity_scores: list of score dicts
            unknown_fields: list of unknown top-level manifest keys

        Raises:
            RuntimeError: If required fields are missing or schema_version is absent.
        """
        manifest_path = self._run_dir / "manifest.json"
        findings_path = self._run_dir / "findings.json"

        if not manifest_path.exists():
            raise RuntimeError(f"manifest.json not found in run dir: {self._run_dir}")
        if not findings_path.exists():
            raise RuntimeError(f"findings.json not found in run dir: {self._run_dir}")

        raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        raw_findings = json.loads(findings_path.read_text(encoding="utf-8"))

        # Validate required fields
        if "schema_version" not in raw_manifest:
            raise RuntimeError("manifest.json is missing required field 'schema_version'.")
        if "run_id" not in raw_manifest:
            raise RuntimeError("manifest.json is missing required field 'run_id'.")
        for field in MANIFEST_REQUIRED - {"schema_version", "run_id"}:
            if field not in raw_manifest:
                raise RuntimeError(f"manifest.json is missing required field '{field}'.")

        # Separate known and unknown fields for forward tolerance
        unknown_fields = [k for k in raw_manifest if k not in MANIFEST_KNOWN]

        return {
            "manifest": raw_manifest,
            "findings": raw_findings.get("findings", []),
            "maturity_scores": raw_findings.get("maturity_scores", []),
            "unknown_fields": unknown_fields,
        }

    def list_raw_entries(self, category: str) -> list[str]:
        """Return file names in raw/<category>/ (without extension)."""
        raw_dir = self._run_dir / "raw" / category
        if not raw_dir.is_dir():
            return []
        return [p.stem for p in raw_dir.glob("*.json")]

    def read_raw(self, category: str, item_id: str) -> dict:
        """Read raw/<category>/<item_id>.json."""
        path = self._run_dir / "raw" / category / f"{item_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Raw entry not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))


class OneLakeArtifactReader:  # pragma: no cover
    """Reads a findings artifact from OneLake via azure-storage-file-datalake.

    Used by the narrator MCP server in production. Tests use ArtifactReader
    (filesystem) with fixture data instead.
    """

    def __init__(
        self,
        workspace_id: str,
        run_id: str,
        token_fn,
    ) -> None:
        from azure.storage.filedatalake import DataLakeServiceClient  # type: ignore
        self.workspace_id = workspace_id
        self.run_id = run_id
        self._token_fn = token_fn
        self._base_path = f"Files/modeling-readiness/{run_id}"

    def _client(self):
        from azure.core.credentials import AccessToken
        from azure.storage.filedatalake import DataLakeServiceClient

        class _StaticCred:
            def __init__(self, token_fn):
                self._fn = token_fn

            def get_token(self, *scopes, **kw):
                return AccessToken(self._fn(), 9999999999)

        return DataLakeServiceClient(
            account_url=f"https://onelake.dfs.fabric.microsoft.com",
            credential=_StaticCred(self._token_fn),
        )

    def load(self) -> dict:
        """Download and parse the artifact from OneLake."""
        client = self._client()
        fs = client.get_file_system_client(self.workspace_id)

        manifest_bytes = fs.get_file_client(f"{self._base_path}/manifest.json").download_file().readall()
        findings_bytes = fs.get_file_client(f"{self._base_path}/findings.json").download_file().readall()

        raw_manifest = json.loads(manifest_bytes)
        raw_findings = json.loads(findings_bytes)

        if "schema_version" not in raw_manifest:
            raise RuntimeError("manifest.json is missing required field 'schema_version'.")
        if "run_id" not in raw_manifest:
            raise RuntimeError("manifest.json is missing required field 'run_id'.")

        unknown_fields = [k for k in raw_manifest if k not in MANIFEST_KNOWN]

        return {
            "manifest": raw_manifest,
            "findings": raw_findings.get("findings", []),
            "maturity_scores": raw_findings.get("maturity_scores", []),
            "unknown_fields": unknown_fields,
        }

    def list_runs(self) -> list[str]:
        """List all run IDs in Files/modeling-readiness/."""
        client = self._client()
        fs = client.get_file_system_client(self.workspace_id)
        try:
            paths = fs.get_paths("Files/modeling-readiness/", recursive=False)
            return sorted([p.name.split("/")[-1] for p in paths if p.is_directory], reverse=True)
        except Exception:
            return []
