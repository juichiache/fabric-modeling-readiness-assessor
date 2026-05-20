"""Semantic model extraction for the Modeling Readiness Assessor scanner.

In a Fabric notebook, extract_semantic_models() calls the Power BI REST API
via notebookutils. In tests, extract_semantic_models_from_response() parses
a pre-loaded API response dict, enabling full testing without a live Fabric tenant.

FR-003: Extract SemanticModel list from a Fabric workspace.
NFR-PERF: Paginate API calls ($top/$skip); retry on transient errors; isolate
per-item parse failures so one bad model never aborts a full workspace scan.
"""
from __future__ import annotations

import logging
import time
from typing import Callable

from scanner.lib.scanner.findings import (
    Measure,
    Relationship,
    SemanticModel,
    Table,
)

logger = logging.getLogger(__name__)

PBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"

_PAGE_SIZE = 100          # Power BI default max; explicit keeps us in control
_MAX_RETRIES = 3          # transient retry count for 429 / 503
_RETRY_DELAY_SEC = 2.0    # initial delay; reused for all retry slots


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
                    "HTTP %d from Power BI API (attempt %d/%d); retrying in %.0fs.",
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


def extract_semantic_models(  # pragma: no cover
    workspace_id: str,
    token_fn: Callable[[], str],
    raw_writer=None,
) -> list[SemanticModel]:
    """Extract all semantic models from a Fabric workspace via Power BI REST API.

    Paginates through all result pages using $top/$skip and retries transient
    HTTP errors (429/503) up to _MAX_RETRIES times.

    Args:
        workspace_id: Fabric workspace GUID.
        token_fn: Zero-argument callable that returns a bearer token string.
            In a Fabric notebook use:
                lambda: notebookutils.credentials.getToken("pbi")
        raw_writer: Optional FindingsArtifactWriter; if provided, raw API
            responses are written to raw/semantic_models/<model-id>.json.

    Returns:
        List of SemanticModel dataclasses (all pages combined).
    """
    headers = {"Authorization": f"Bearer {token_fn()}"}
    all_items: list[dict] = []
    skip = 0

    while True:
        url = (
            f"{PBI_API_BASE}/groups/{workspace_id}/datasets"
            f"?$top={_PAGE_SIZE}&$skip={skip}"
        )
        response = _get_with_retry(url, headers)
        response.raise_for_status()
        payload = response.json()
        page_items = payload.get("value", [])

        for item in page_items:
            if raw_writer is not None and "id" in item:
                raw_writer.write_raw("semantic_models", item["id"], item)

        all_items.extend(page_items)

        if len(page_items) < _PAGE_SIZE:
            break  # Last page
        skip += _PAGE_SIZE

    return extract_semantic_models_from_response({"value": all_items}, workspace_id=workspace_id)


def extract_semantic_models_from_response(
    payload: dict,
    workspace_id: str,
) -> list[SemanticModel]:
    """Parse a Power BI REST API response dict into SemanticModel dataclasses.

    This function is the pure, testable core — no HTTP calls.

    The payload is the JSON body of GET /groups/{workspace}/datasets, which
    may embed tables, relationships, and measures in the ``value`` array items.

    Malformed items are skipped with a warning; one bad model never aborts parsing.
    """
    models: list[SemanticModel] = []
    for item in payload.get("value", []):
        try:
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
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Skipping malformed semantic model item (missing required field): %s. Item keys: %s",
                exc,
                list(item.keys()) if isinstance(item, dict) else type(item),
            )
    return models


def _extract_tables(raw_tables: list[dict]) -> list[Table]:
    tables: list[Table] = []
    for t in raw_tables:
        try:
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
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping malformed table item: %s", exc)
    return tables


def _extract_relationships(raw_rels: list[dict]) -> list[Relationship]:
    rels: list[Relationship] = []
    for r in raw_rels:
        try:
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
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping malformed relationship item: %s", exc)
    return rels


def _extract_measures(raw_measures: list[dict]) -> list[Measure]:
    measures: list[Measure] = []
    for m in raw_measures:
        try:
            measures.append(
                Measure(name=m["name"], table=m.get("table", ""), expression=m.get("expression", ""))
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping malformed measure item: %s", exc)
    return measures
