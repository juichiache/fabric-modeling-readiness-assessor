"""MCP tool: list_runs

Returns all available run IDs from the OneLake modeling-readiness directory,
sorted newest-first. Caller supplies a bearer token via the auth_token parameter.

Tool contract: contracts/mcp-tools.md § list_runs
"""
from __future__ import annotations

from narrator.mcp_server.artifact_reader import OneLakeArtifactReader


def list_runs(workspace_id: str, auth_token: str) -> dict:  # pragma: no cover
    """List available scan run IDs, newest first.

    Args:
        workspace_id: The Fabric workspace GUID.
        auth_token: Bearer token for OneLake access.

    Returns:
        {"runs": ["<run_id>", ...]}
    """
    reader = OneLakeArtifactReader(
        workspace_id=workspace_id,
        run_id="",
        token_fn=lambda: auth_token,
    )
    return {"runs": reader.list_runs()}
