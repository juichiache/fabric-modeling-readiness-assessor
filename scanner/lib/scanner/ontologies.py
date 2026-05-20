"""Fabric IQ ontology extraction for the Modeling Readiness Assessor scanner.

In a Fabric notebook, extract_ontologies() calls the Fabric IQ REST API (preview)
via notebookutils. In tests, extract_ontologies_from_response() parses a pre-loaded
response dict, enabling full testing without a live Fabric tenant.

FR-004: Extract Ontology list from a Fabric workspace.
NFR-003: Wrap all Fabric IQ calls in try/except; mark failed scopes as not_assessed.
NFR-PERF: Paginate via continuationToken; retry on transient errors; isolate per-item
parse failures so one bad ontology never aborts a full workspace scan.
"""
from __future__ import annotations

import logging
import time
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

_MAX_RETRIES = 3
_RETRY_DELAY_SEC = 2.0


def _get_with_retry(url: str, headers: dict, *, timeout: int = 60) -> "requests.Response":  # type: ignore[name-defined]
    """GET with up to _MAX_RETRIES retries on 429/503."""
    import requests  # noqa: PLC0415

    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code in (429, 503) and attempt < _MAX_RETRIES:
                delay = _RETRY_DELAY_SEC * attempt
                logger.warning(
                    "HTTP %d from Fabric IQ API (attempt %d/%d); retrying in %.0fs.",
                    resp.status_code, attempt, _MAX_RETRIES, delay,
                )
                time.sleep(delay)
                continue
            return resp
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY_SEC * attempt)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Unreachable")


def extract_ontologies(  # pragma: no cover
    workspace_id: str,
    token_fn: Callable[[], str],
    raw_writer=None,
) -> list[Ontology]:
    """Extract all Fabric IQ ontologies from a workspace via the Fabric REST API (preview).

    Paginates via continuationToken in the response body. Catches HTTP 404
    (Fabric IQ not yet provisioned) and returns an empty list so the scanner
    can mark the discipline as not_assessed. Retries transient 429/503 errors.

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
    try:
        headers = {"Authorization": f"Bearer {token_fn()}"}
        all_items: list[dict] = []
        url: str | None = f"{FABRIC_API_BASE}/workspaces/{workspace_id}/ontologies"

        while url is not None:
            response = _get_with_retry(url, headers)

            if response.status_code == 404:
                logger.warning(
                    "Fabric IQ ontology API returned 404 for workspace %s. "
                    "Fabric IQ may not be provisioned. Skipping ontology extraction.",
                    workspace_id,
                )
                return handle_ontology_404(workspace_id)

            response.raise_for_status()
            payload = response.json()
            page_items = payload.get("value", [])

            for item in page_items:
                if raw_writer is not None and "id" in item:
                    raw_writer.write_raw("ontologies", item["id"], item)

            all_items.extend(page_items)

            # Fabric IQ API uses continuationToken (not $skip)
            continuation = payload.get("continuationToken") or payload.get("@odata.nextLink")
            if continuation:
                # continuationToken is passed as a query param on the same base URL
                if continuation.startswith("http"):
                    url = continuation
                else:
                    url = f"{FABRIC_API_BASE}/workspaces/{workspace_id}/ontologies?continuationToken={continuation}"
            else:
                url = None

        return extract_ontologies_from_response({"value": all_items}, workspace_id=workspace_id)

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
    Malformed items are skipped with a warning; one bad ontology never aborts parsing.
    """
    ontologies: list[Ontology] = []
    for item in payload.get("value", []):
        try:
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
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Skipping malformed ontology item (missing required field): %s. Item keys: %s",
                exc,
                list(item.keys()) if isinstance(item, dict) else type(item),
            )
    return ontologies


def _extract_entity_types(raw_types: list[dict]) -> list[EntityType]:
    entity_types: list[EntityType] = []
    for t in raw_types:
        try:
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
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping malformed entity type item: %s", exc)
    return entity_types


def _extract_properties(raw_props: list[dict]) -> list[OntologyProperty]:
    props: list[OntologyProperty] = []
    for p in raw_props:
        try:
            props.append(OntologyProperty(
                name=p["name"],
                data_type=p.get("dataType", "string"),
                is_source_attribution=bool(p.get("isSourceAttribution", False)),
            ))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping malformed property item: %s", exc)
    return props


def _extract_relationships(raw_rels: list[dict]) -> list[OntologyRelationship]:
    rels: list[OntologyRelationship] = []
    for r in raw_rels:
        try:
            rels.append(OntologyRelationship(
                from_entity=r.get("fromEntity", ""),
                to_entity=r.get("toEntity", ""),
                relationship_name=r.get("relationshipName", ""),
            ))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping malformed ontology relationship item: %s", exc)
    return rels


def _extract_bindings(raw_bindings: list[dict]) -> list[DataBinding]:
    bindings: list[DataBinding] = []
    for b in raw_bindings:
        try:
            bindings.append(DataBinding(
                binding_id=b.get("bindingId", ""),
                source_type=b.get("sourceType", ""),
                source_id=b.get("sourceId", ""),
                has_temporal_source_marker=bool(b.get("hasTemporalSourceMarker", False)),
            ))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping malformed binding item: %s", exc)
    return bindings
