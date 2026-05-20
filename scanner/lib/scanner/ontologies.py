"""Fabric IQ ontology extraction for the Modeling Readiness Assessor scanner.

In a Fabric notebook, extract_ontologies() calls the Fabric IQ REST API (preview)
via notebookutils. In tests, extract_ontologies_from_response() parses a pre-loaded
response dict, enabling full testing without a live Fabric tenant.

FR-004: Extract Ontology list from a Fabric workspace.
NFR-003: Wrap all Fabric IQ calls in try/except; mark failed scopes as not_assessed.
"""
from __future__ import annotations

import logging
from typing import Callable

from scanner.lib.scanner.findings import (
    DataBinding,
    EntityType,
    Ontology,
    OntologyProperty,
    OntologyRelationship,
)

logger = logging.getLogger(__name__)

FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"


def extract_ontologies(  # pragma: no cover
    workspace_id: str,
    token_fn: Callable[[], str],
    raw_writer=None,
) -> list[Ontology]:
    """Extract all Fabric IQ ontologies from a workspace via the Fabric REST API (preview).

    Catches HTTP 404 (Fabric IQ not yet provisioned in this workspace) and
    returns an empty list so the scanner can mark the discipline as not_assessed.

    Args:
        workspace_id: Fabric workspace GUID.
        token_fn: Zero-argument callable returning a bearer token string.
            In a Fabric notebook use:
                lambda: notebookutils.credentials.getToken("fabric")
        raw_writer: Optional FindingsArtifactWriter; raw responses written to
            raw/ontologies/<ontology-id>.json if provided.

    Returns:
        List of Ontology dataclasses; empty if Fabric IQ is unavailable.
    """
    import requests  # noqa: PLC0415 — optional dep; not needed for unit tests

    try:
        headers = {"Authorization": f"Bearer {token_fn()}"}
        url = f"{FABRIC_API_BASE}/workspaces/{workspace_id}/ontologies"
        response = requests.get(url, headers=headers, timeout=60)

        if response.status_code == 404:
            logger.warning(
                "Fabric IQ ontology API returned 404 for workspace %s. "
                "Fabric IQ may not be provisioned. Skipping ontology extraction.",
                workspace_id,
            )
            return handle_ontology_404(workspace_id)

        response.raise_for_status()
        payload = response.json()

        if raw_writer is not None:
            for item in payload.get("value", []):
                raw_writer.write_raw("ontologies", item["id"], item)

        return extract_ontologies_from_response(payload, workspace_id=workspace_id)

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Ontology extraction failed for workspace %s: %s. "
            "Field-Level Lineage will be marked not_assessed.",
            workspace_id,
            exc,
        )
        return []


def handle_ontology_404(workspace_id: str) -> list[Ontology]:
    """Return empty list when Fabric IQ is absent (404). Enables not_assessed scoring."""
    logger.info("Ontology extraction skipped for workspace %s (404 — Fabric IQ absent).", workspace_id)
    return []


def extract_ontologies_from_response(
    payload: dict,
    workspace_id: str,
) -> list[Ontology]:
    """Parse a Fabric IQ REST API response dict into Ontology dataclasses.

    This function is the pure, testable core — no HTTP calls.
    """
    ontologies: list[Ontology] = []
    for item in payload.get("value", []):
        ontology_id = item["id"]
        entity_types = _extract_entity_types(item.get("entityTypes", []))
        ontologies.append(
            Ontology(
                ontology_id=ontology_id,
                name=item.get("name", ""),
                workspace_id=workspace_id,
                entity_types=entity_types,
            )
        )
    return ontologies


def _extract_entity_types(raw_types: list[dict]) -> list[EntityType]:
    entity_types: list[EntityType] = []
    for t in raw_types:
        properties = _extract_properties(t.get("properties", []))
        relationships = _extract_relationships(t.get("relationships", []))
        bindings = _extract_bindings(t.get("bindings", []))
        entity_types.append(
            EntityType(
                name=t["name"],
                properties=properties,
                relationships=relationships,
                bindings=bindings,
            )
        )
    return entity_types


def _extract_properties(raw_props: list[dict]) -> list[OntologyProperty]:
    return [
        OntologyProperty(
            name=p["name"],
            data_type=p.get("dataType", "string"),
            is_source_attribution=bool(p.get("isSourceAttribution", False)),
        )
        for p in raw_props
    ]


def _extract_relationships(raw_rels: list[dict]) -> list[OntologyRelationship]:
    return [
        OntologyRelationship(
            from_entity=r.get("fromEntity", ""),
            to_entity=r.get("toEntity", ""),
            relationship_name=r.get("relationshipName", ""),
        )
        for r in raw_rels
    ]


def _extract_bindings(raw_bindings: list[dict]) -> list[DataBinding]:
    return [
        DataBinding(
            binding_id=b.get("bindingId", ""),
            source_type=b.get("sourceType", ""),
            source_id=b.get("sourceId", ""),
            has_temporal_source_marker=bool(b.get("hasTemporalSourceMarker", False)),
        )
        for b in raw_bindings
    ]
