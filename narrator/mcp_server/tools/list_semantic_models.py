"""MCP tool: list_semantic_models

Lists semantic models captured in the raw/ directory of a run artifact.
Operates on a locally-mounted / pre-loaded artifact (no live Fabric calls).

Tool contract: contracts/mcp-tools.md § list_semantic_models
"""
from __future__ import annotations

from narrator.mcp_server.artifact_reader import ArtifactReader


def list_semantic_models(root_path: str, run_id: str) -> dict:
    """List semantic model IDs in a run artifact.

    Args:
        root_path: Local filesystem root containing the run directory.
        run_id: Run identifier.

    Returns:
        {"semantic_models": ["<model_id>", ...]}
    """
    reader = ArtifactReader(root_path=root_path, run_id=run_id)
    return {"semantic_models": reader.list_raw_entries("semantic_models")}
