"""MCP tool: enumerate_ontologies

Lists ontology IDs captured in the raw/ directory of a run artifact.

Tool contract: contracts/mcp-tools.md § enumerate_ontologies
"""
from __future__ import annotations

from narrator.mcp_server.artifact_reader import ArtifactReader


def enumerate_ontologies(root_path: str, run_id: str) -> dict:
    """List ontology IDs in a run artifact.

    Args:
        root_path: Local filesystem root containing the run directory.
        run_id: Run identifier.

    Returns:
        {"ontologies": ["<ontology_id>", ...]}
    """
    reader = ArtifactReader(root_path=root_path, run_id=run_id)
    return {"ontologies": reader.list_raw_entries("ontologies")}
