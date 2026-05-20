"""Narrator MCP server entrypoint.

Wires all 6 MCP tools via fastmcp and registers them with the server.
Run with: python -m narrator.mcp_server.server

FR-040: MCP server wiring.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from narrator.mcp_server.auth import get_token
from narrator.mcp_server.onelake import resolve_workspace_url
from narrator.mcp_server.tools.list_runs import list_runs
from narrator.mcp_server.tools.load_run import load_run
from narrator.mcp_server.tools.list_semantic_models import list_semantic_models
from narrator.mcp_server.tools.extract_entity_definitions import extract_entity_definitions
from narrator.mcp_server.tools.audit_source_attribution import audit_source_attribution
from narrator.mcp_server.tools.enumerate_ontologies import enumerate_ontologies
from narrator.mcp_server.tools.run_scanner import run_scanner

try:
    import fastmcp
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False

CONFIG_PATH = "narrator.config.yaml"
TOOLS_DIR = "Files/modeling-readiness"


def _load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    return {}


def _validate_config(config: dict) -> None:
    threshold = config.get("similarity_threshold", 0.85)
    if not (0.5 <= float(threshold) <= 1.0):
        raise RuntimeError(
            f"narrator.config.yaml: similarity_threshold must be in [0.5, 1.0], got {threshold}"
        )


def build_server():  # pragma: no cover
    """Build and return the fastmcp Server with all tools registered."""
    if not _MCP_AVAILABLE:
        raise RuntimeError(
            "fastmcp is not installed. Run: pip install fastmcp"
        )

    config = _load_config()
    _validate_config(config)

    mcp = fastmcp.FastMCP("modeling-readiness-narrator")

    @mcp.tool()
    def tool_list_runs(workspace_id: str, auth_token: str) -> dict:
        """List available modeling-readiness scan runs (newest first)."""
        return list_runs(workspace_id=workspace_id, auth_token=auth_token)

    @mcp.tool()
    def tool_load_run(workspace_id: str, run_id: str, auth_token: str) -> dict:
        """Load a full run artifact (manifest + findings + scores)."""
        return load_run(workspace_id=workspace_id, run_id=run_id, auth_token=auth_token)

    @mcp.tool()
    def tool_list_semantic_models(root_path: str, run_id: str) -> dict:
        """List semantic model IDs captured in a run artifact."""
        return list_semantic_models(root_path=root_path, run_id=run_id)

    @mcp.tool()
    def tool_extract_entity_definitions(manifest_json: str, findings_json: str) -> dict:
        """Extract canonical entity definitions from the run artifact JSON strings."""
        import json
        loaded = {
            "manifest": json.loads(manifest_json),
            "findings": json.loads(findings_json).get("findings", []),
            "maturity_scores": json.loads(findings_json).get("maturity_scores", []),
        }
        return extract_entity_definitions(loaded)

    @mcp.tool()
    def tool_audit_source_attribution(findings_json: str) -> dict:
        """Return field-level lineage gaps from the run artifact findings JSON string."""
        import json
        loaded = {
            "findings": json.loads(findings_json).get("findings", []),
            "maturity_scores": [],
        }
        return audit_source_attribution(loaded)

    @mcp.tool()
    def tool_enumerate_ontologies(root_path: str, run_id: str) -> dict:
        """List ontology IDs captured in a run artifact."""
        return enumerate_ontologies(root_path=root_path, run_id=run_id)

    @mcp.tool()
    def tool_run_scanner(
        workspace_id: str,
        notebook_id: str,
        fabric_token: str,
        workspace_id_param: str = "",
        workspace_url_param: str = "",
    ) -> dict:
        """Trigger the modeling-readiness-scanner notebook in Fabric and wait for completion.

        Runs the scanner notebook via the Fabric REST API, optionally injecting
        WORKSPACE_ID and WORKSPACE_URL as notebook parameters so the customer
        does not need to edit Cell 1 manually.

        Args:
            workspace_id: Fabric workspace GUID that owns the notebook.
            notebook_id: Fabric item ID (GUID) of the scanner notebook.
            fabric_token: Bearer token with Fabric API scope
                (https://api.fabric.microsoft.com/user_impersonation).
            workspace_id_param: Workspace GUID to scan (injected as WORKSPACE_ID).
                Leave empty to use the value already in the notebook.
            workspace_url_param: Fabric workspace URL to scan (injected as WORKSPACE_URL).
                Leave empty to use the value already in the notebook.

        Returns:
            {"status": "Succeeded"|"Failed"|"Timeout", "job_instance_id": "...", "message": "..."}
        """
        return run_scanner(
            workspace_id=workspace_id,
            notebook_id=notebook_id,
            fabric_token=fabric_token,
            workspace_id_param=workspace_id_param,
            workspace_url_param=workspace_url_param,
            poll=True,
        )

    return mcp


if __name__ == "__main__":
    server = build_server()
    server.run()
