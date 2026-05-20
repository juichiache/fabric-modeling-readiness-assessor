"""MCP tool: audit_source_attribution

Returns field-level lineage gaps from the findings artifact.
Only surfaces findings for the field_level_lineage discipline.

Tool contract: contracts/mcp-tools.md § audit_source_attribution
"""
from __future__ import annotations


def audit_source_attribution(loaded_artifact: dict) -> dict:
    """Extract FLL gaps from a loaded run artifact.

    Args:
        loaded_artifact: The dict returned by ArtifactReader.load() or
                         OneLakeArtifactReader.load().

    Returns:
        {"gaps": [<finding dict>, ...]}
    """
    fll_findings = [
        f for f in loaded_artifact.get("findings", [])
        if f.get("discipline") == "field_level_lineage"
    ]
    return {"gaps": fll_findings}
