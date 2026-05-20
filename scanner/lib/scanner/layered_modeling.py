"""Layered Modeling gap detection (Discipline 3).

Inspects semantic model table names for vocabulary that implies a data staging
architecture (bronze/silver/gold or equivalent). Does NOT prescribe exact names;
bucket matching is vocabulary-based (Framework Principle VI).

A workspace that has semantic models but no layering vocabulary is flagged —
suggesting data is being served directly from source without staging layers.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass

from scanner.lib.scanner.findings import LayeringGap, SemanticModel

logger = logging.getLogger(__name__)

# Vocabulary buckets representing the three canonical staging layers.
# Tokens are lower-case; matching is case-insensitive.
LAYER_BUCKETS: dict[str, frozenset[str]] = {
    "bronze": frozenset({
        "raw", "bronze", "ingest", "ingested", "landing", "extract", "extracted",
        "source", "src", "stage0", "layer0", "l0",
    }),
    "silver": frozenset({
        "silver", "clean", "cleansed", "conform", "conformed", "stage", "staged",
        "staging", "prep", "prepared", "validated", "validate", "curate",
        "enriched", "enrich", "intermediate", "int", "layer1", "l1",
    }),
    "gold": frozenset({
        "gold", "curated", "publish", "published", "mart", "datamart",
        "semantic", "refined", "final", "report", "serve", "serving",
        "presentation", "consumer", "layer2", "l2",
    }),
}

_TOKEN_SPLITTER = re.compile(
    r"(?<=[a-z])(?=[A-Z])"  # camelCase → lower|Upper boundary
    r"|(?<=[A-Z])(?=[A-Z][a-z])"  # ABCDef → ABC|Def
    r"|[\s_\-]+"             # whitespace / underscore / hyphen
)


def _tokenize(name: str) -> list[str]:
    """Split a table name into lowercase tokens."""
    return [t.lower() for t in _TOKEN_SPLITTER.split(name) if t]


def _detect_layers(model: SemanticModel) -> dict[str, list[str]]:
    """Return {bucket_name: [matched_tokens]} for all tables in the model."""
    all_tokens: list[str] = []
    for table in model.tables:
        all_tokens.extend(_tokenize(table.name))

    matched: dict[str, list[str]] = {}
    for bucket, vocab in LAYER_BUCKETS.items():
        hits = [t for t in all_tokens if t in vocab]
        if hits:
            matched[bucket] = hits
    return matched


def _gap_id(model_id: str) -> str:
    return "lm-" + hashlib.sha1(model_id.encode()).hexdigest()[:8]


def detect_layering_gaps(models: list[SemanticModel]) -> list[LayeringGap]:
    """Detect layered-modeling gaps across all semantic models.

    A gap is raised for any model where table-name vocabulary covers fewer than
    three layer buckets, suggesting the workspace lacks a full staging architecture.

    Args:
        models: All semantic models extracted from the workspace.

    Returns:
        List of LayeringGap; one entry per model with fewer than 3 detected layers.
        Empty list when no models are supplied.
    """
    gaps: list[LayeringGap] = []

    for model in models:
        if not model.tables:
            logger.debug("Model %r has no tables — skipping layering check.", model.name)
            continue

        try:
            matched = _detect_layers(model)
            detected = sorted(matched.keys())
            missing = sorted(set(LAYER_BUCKETS) - set(detected))

            if missing:  # fewer than 3 layers detected
                gaps.append(
                    LayeringGap(
                        gap_id=_gap_id(model.model_id),
                        model_id=model.model_id,
                        model_name=model.name,
                        detected_layers=detected,
                        missing_layers=missing,
                        table_count=len(model.tables),
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error checking layering for model %r: %s", model.name, exc)

    return gaps


def severity_for_gap(gap: LayeringGap) -> str:
    """Map a LayeringGap to a finding severity string."""
    missing_count = len(gap.missing_layers)
    if missing_count == 3:
        return "high"
    if missing_count == 2:
        return "medium"
    return "low"


def remediation_hint_for_gap(gap: LayeringGap) -> str:
    """Return a remediation hint appropriate for the gap."""
    if not gap.detected_layers:
        return (
            "No staging-layer vocabulary detected in table names. "
            "Introduce a bronze/silver/gold (or equivalent) layered architecture "
            "to separate raw ingestion, conformation, and serving concerns."
        )
    if len(gap.missing_layers) == 2:
        detected = ", ".join(gap.detected_layers)
        missing = " and ".join(gap.missing_layers)
        return (
            f"Only '{detected}' layer vocabulary detected; '{missing}' layers appear absent. "
            "Verify that upstream ingestion and downstream serving layers exist and are "
            "accessible as separate semantic model tables or artifacts."
        )
    # One layer missing
    missing = gap.missing_layers[0]
    return (
        f"'{missing}' layer vocabulary not detected. "
        "Confirm whether this layer is intentionally absent or represented under different naming."
    )
