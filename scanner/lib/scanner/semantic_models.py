"""Semantic model extraction for the Modeling Readiness Assessor scanner.

In a Fabric notebook, extract_semantic_models() calls the Power BI REST API
via notebookutils. In tests, extract_semantic_models_from_response() parses
a pre-loaded API response dict, enabling full testing without a live Fabric tenant.

FR-003: Extract SemanticModel list from a Fabric workspace.
"""
from __future__ import annotations

import json
import logging
from typing import Callable

from scanner.lib.scanner.findings import (
    Measure,
    Relationship,
    SemanticModel,
    Table,
)

logger = logging.getLogger(__name__)

PBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"


def extract_semantic_models(  # pragma: no cover
    workspace_id: str,
    token_fn: Callable[[], str],
    raw_writer=None,
) -> list[SemanticModel]:
    """Extract all semantic models from a Fabric workspace via Power BI REST API.

    Args:
        workspace_id: Fabric workspace GUID.
        token_fn: Zero-argument callable that returns a bearer token string.
            In a Fabric notebook use:
                lambda: notebookutils.credentials.getToken("pbi")
        raw_writer: Optional FindingsArtifactWriter; if provided, raw API
            responses are written to raw/semantic_models/<model-id>.json.

    Returns:
        List of SemanticModel dataclasses.
    """
    import requests  # noqa: PLC0415 — optional dep; not needed for unit tests

    headers = {"Authorization": f"Bearer {token_fn()}"}
    url = f"{PBI_API_BASE}/groups/{workspace_id}/datasets"
    response = requests.get(url, headers=headers, timeout=60)
    response.raise_for_status()
    payload = response.json()

    if raw_writer is not None:
        for item in payload.get("value", []):
            raw_writer.write_raw("semantic_models", item["id"], item)

    return extract_semantic_models_from_response(payload, workspace_id=workspace_id)


def extract_semantic_models_from_response(
    payload: dict,
    workspace_id: str,
) -> list[SemanticModel]:
    """Parse a Power BI REST API response dict into SemanticModel dataclasses.

    This function is the pure, testable core — no HTTP calls.

    The payload is the JSON body of GET /groups/{workspace}/datasets, which
    may embed tables, relationships, and measures in the ``value`` array items.
    """
    models: list[SemanticModel] = []
    for item in payload.get("value", []):
        model_id = item["id"]
        tables = _extract_tables(item.get("tables", []))
        relationships = _extract_relationships(item.get("relationships", []))
        measures = _extract_measures(item.get("measures", []))
        models.append(
            SemanticModel(
                model_id=model_id,
                name=item.get("name", ""),
                workspace_id=workspace_id,
                tables=tables,
                relationships=relationships,
                measures=measures,
            )
        )
    return models


def _extract_tables(raw_tables: list[dict]) -> list[Table]:
    tables: list[Table] = []
    for t in raw_tables:
        columns = t.get("columns", [])
        source_columns = [c["name"] for c in columns if c.get("columnType") == "data"]
        pk_entry = t.get("primaryKey", {})
        primary_key_columns: list[str] = pk_entry.get("keyColumns", []) if pk_entry else []
        tables.append(
            Table(
                name=t["name"],
                source_columns=source_columns,
                primary_key_columns=primary_key_columns,
                source_expression=t.get("source"),
            )
        )
    return tables


def _extract_relationships(raw_rels: list[dict]) -> list[Relationship]:
    rels: list[Relationship] = []
    for r in raw_rels:
        cardinality = f"{r.get('fromCardinality', '?').lower()}-to-{r.get('toCardinality', '?').lower()}"
        rels.append(
            Relationship(
                from_table=r["fromTable"],
                from_column=r["fromColumn"],
                to_table=r["toTable"],
                to_column=r["toColumn"],
                cardinality=cardinality,
                cross_filter_direction=r.get("crossFilteringBehavior", "oneDirection"),
            )
        )
    return rels


def _extract_measures(raw_measures: list[dict]) -> list[Measure]:
    return [
        Measure(name=m["name"], table=m.get("table", ""), expression=m.get("expression", ""))
        for m in raw_measures
    ]
