"""MCP tool: load_run

Loads the full artifact (manifest + findings + maturity_scores) for a specific run.

Tool contract: contracts/mcp-tools.md § load_run
"""
from __future__ import annotations

from narrator.mcp_server.artifact_reader import OneLakeArtifactReader


def load_run(workspace_id: str, run_id: str, auth_token: str) -> dict:  # pragma: no cover
    """Load a run artifact from OneLake.

    Args:
        workspace_id: The Fabric workspace GUID.
        run_id: Run identifier (e.g. "20260520-143022-a3f7").
        auth_token: Bearer token for OneLake access.

    Returns:
        Dict with 'manifest', 'findings', 'maturity_scores', 'unknown_fields'.
    """
    reader = OneLakeArtifactReader(
        workspace_id=workspace_id,
        run_id=run_id,
        token_fn=lambda: auth_token,
    )
    return reader.load()
