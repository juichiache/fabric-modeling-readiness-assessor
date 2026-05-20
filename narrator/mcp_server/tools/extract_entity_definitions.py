"""MCP tool: extract_entity_definitions

Returns canonical entity definitions extracted from the findings artifact.
Only surfaces entities that appear in at least one canonical_entity_modeling finding.

Tool contract: contracts/mcp-tools.md § extract_entity_definitions
"""
from __future__ import annotations

from typing import Any


def extract_entity_definitions(loaded_artifact: dict) -> dict:
    """Extract canonical entity definitions from a loaded run artifact.

    Args:
        loaded_artifact: The dict returned by ArtifactReader.load() or
                         OneLakeArtifactReader.load().

    Returns:
        {"entities": [{"entity_name": str, "source_artifacts": list, "finding_ids": list}]}
    """
    cem_findings = [
        f for f in loaded_artifact.get("findings", [])
        if f.get("discipline") == "canonical_entity_modeling"
    ]

    entity_map: dict[str, dict[str, Any]] = {}
    for finding in cem_findings:
        name = finding.get("entity_name", "")
        if not name:
            continue
        if name not in entity_map:
            entity_map[name] = {
                "entity_name": name,
                "source_artifacts": [],
                "finding_ids": [],
            }
        entity_map[name]["finding_ids"].append(finding["finding_id"])
        for src in finding.get("source_artifacts", []):
            if src not in entity_map[name]["source_artifacts"]:
                entity_map[name]["source_artifacts"].append(src)

    return {"entities": sorted(entity_map.values(), key=lambda e: e["entity_name"])}
