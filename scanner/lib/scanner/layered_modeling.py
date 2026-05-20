"""Layered Modeling gap detection (Discipline 3) — v2 structural detector.

Combines three independent signals to assess whether a workspace has a genuine
staged data architecture:

  1. **Vocabulary** (weak) — table name tokens matching bronze/silver/gold buckets.
  2. **Derivation depth** (strong) — how many inter-table dependency hops exist in
     the semantic model's M-query expressions, reflecting ETL chain depth.
  3. **Expression classification** (strong) — whether tables apply real transformations
     (AddColumn, TransformColumnTypes, Group, Distinct …) or are pure passthroughs.

A workspace scores well when its models show depth ≥ 2 AND have transformed/
aggregated tables at each hop, regardless of naming conventions.

Scoring thresholds (per model):
  - Gap NOT raised if: max_derivation_depth >= 2 AND transformed_ratio >= 0.25
  - Gap raised with severity "low"  if: depth >= 1 OR vocabulary partially present
  - Gap raised with severity "medium" if: depth == 0 AND some vocabulary present
  - Gap raised with severity "high"  if: depth == 0 AND no vocabulary

Honest ceiling: even structural analysis cannot distinguish "transformation that
improves the data" from "transformation that merely reshapes it." Notebook/M-query
source inspection is required for v3 rigor.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import field

from scanner.lib.scanner.findings import LayeringGap, SemanticModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Vocabulary (retained as a corroborating signal — no longer the sole gate)
# ---------------------------------------------------------------------------

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
    r"(?<=[a-z])(?=[A-Z])"
    r"|(?<=[A-Z])(?=[A-Z][a-z])"
    r"|[\s_\-]+"
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


# ---------------------------------------------------------------------------
# Expression classifier (d3-expression-parser)
# ---------------------------------------------------------------------------

# M-query function prefixes that indicate real structural transformations.
_AGGREGATED = frozenset({"Table.Group", "Table.Pivot", "Table.Unpivot"})
_TRANSFORMED = frozenset({
    "Table.AddColumn", "Table.RemoveColumns", "Table.TransformColumnTypes",
    "Table.RenameColumns", "Table.Distinct", "Table.Sort",
    "Table.ExpandListColumn", "Table.ExpandTableColumn",
    "Table.ExpandRecordColumn", "Table.Buffer", "Table.FillDown", "Table.FillUp",
    "Table.SplitColumn", "Table.CombineColumns", "Table.Transpose",
})
_FILTERED = frozenset({"Table.SelectRows", "Table.FirstN", "Table.LastN", "Table.Skip"})


def classify_expression(expr: str | None) -> str:
    """Classify an M-query source expression into one of four structural categories.

    Returns:
        "aggregated"  — groups, pivots, or unpivots rows
        "transformed" — adds/removes/reshapes columns or deduplicates
        "filtered"    — selects a subset of rows but does not change schema
        "passthrough" — binds to a source with no detected transformation
        "unknown"     — expression is absent or empty
    """
    if not expr:
        return "unknown"
    for kw in _AGGREGATED:
        if kw in expr:
            return "aggregated"
    for kw in _TRANSFORMED:
        if kw in expr:
            return "transformed"
    for kw in _FILTERED:
        if kw in expr:
            return "filtered"
    return "passthrough"


def _classify_model_expressions(model: SemanticModel) -> dict[str, int]:
    """Return count of tables per expression class for a model."""
    counts: dict[str, int] = {}
    for table in model.tables:
        cls = classify_expression(table.source_expression)
        counts[cls] = counts.get(cls, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Derivation depth counter (d3-derivation-depth)
# ---------------------------------------------------------------------------

def _build_inter_table_deps(model: SemanticModel) -> dict[str, set[str]]:
    """Return {table_name: {tables_this_depends_on}} from M-query expression analysis.

    If table B's source_expression contains the name of table A, B depends on A.
    This is a proxy for ETL derivation chains within the semantic model.
    """
    table_names = {t.name for t in model.tables}
    deps: dict[str, set[str]] = {}
    for table in model.tables:
        if not table.source_expression:
            deps[table.name] = set()
            continue
        referenced: set[str] = set()
        for other_name in table_names:
            if other_name != table.name and other_name in table.source_expression:
                referenced.add(other_name)
        deps[table.name] = referenced
    return deps


def compute_derivation_depths(deps: dict[str, set[str]]) -> dict[str, int]:
    """Compute max path length from any source table for each table (memoised DFS).

    Source tables (no dependencies) have depth 0.
    A table derived from one other table has depth 1. And so on.
    Cycles are short-circuited (depth 0 on the cycle node).
    """
    depths: dict[str, int] = {}

    def _depth(name: str, visiting: frozenset[str]) -> int:
        if name in depths:
            return depths[name]
        if name in visiting:
            return 0  # cycle guard
        visiting = visiting | {name}
        d = 0
        for dep in deps.get(name, set()):
            d = max(d, _depth(dep, visiting) + 1)
        depths[name] = d
        return d

    for name in deps:
        _depth(name, frozenset())
    return depths


def _structural_analysis(model: SemanticModel) -> tuple[int, float, dict[str, int]]:
    """Return (max_depth, flat_ratio, expression_class_counts) for a model."""
    deps = _build_inter_table_deps(model)
    depths = compute_derivation_depths(deps)
    max_depth = max(depths.values()) if depths else 0
    flat_count = sum(1 for d in depths.values() if d == 0)
    flat_ratio = flat_count / len(depths) if depths else 1.0
    expr_counts = _classify_model_expressions(model)
    return max_depth, flat_ratio, expr_counts


# ---------------------------------------------------------------------------
# Gap detection (d3-rewrite-detection)
# ---------------------------------------------------------------------------

def _gap_id(model_id: str) -> str:
    return "lm-" + hashlib.sha1(model_id.encode()).hexdigest()[:8]


def _has_sufficient_layering_evidence(
    max_depth: int,
    expr_counts: dict[str, int],
    matched: dict[str, list[str]],
) -> bool:
    """Return True if any combination of signals confirms genuine layering.

    Two paths to clearing a gap:
    1. Structural: derivation depth ≥ 2 AND ≥25% tables are transformed/aggregated.
    2. Vocabulary: all three canonical layers (bronze/silver/gold) represented — strong
       corroborating signal even without M-query depth data.
    """
    # Vocabulary path — all three buckets present
    if len(matched) >= len(LAYER_BUCKETS):
        return True
    # Structural path — deep chain with real transformations
    if max_depth >= 2:
        non_passthrough = sum(
            v for k, v in expr_counts.items()
            if k in ("transformed", "aggregated")
        )
        total = sum(expr_counts.values())
        if total > 0 and non_passthrough / total >= 0.25:
            return True
    return False


def detect_layering_gaps(models: list[SemanticModel]) -> list[LayeringGap]:
    """Detect layered-modeling gaps across all semantic models using structural + vocabulary signals.

    A gap is NOT raised when structural evidence (derivation depth ≥ 2 AND ≥25% transformed
    tables) confirms genuine layering — even if vocabulary is absent.

    A gap IS raised when structural signals are weak, with severity calibrated to how
    much evidence is available:
      - high:   no structural depth, no vocabulary
      - medium: some vocabulary but no structural depth
      - low:    structural depth present but shallow OR one vocab layer missing

    Args:
        models: All semantic models extracted from the workspace.

    Returns:
        List of LayeringGap; one entry per model without confirmed structural layering.
        Empty list when no models are supplied.
    """
    gaps: list[LayeringGap] = []

    for model in models:
        if not model.tables:
            logger.debug("Model %r has no tables — skipping layering check.", model.name)
            continue

        try:
            max_depth, flat_ratio, expr_counts = _structural_analysis(model)
            matched = _detect_layers(model)
            detected = sorted(matched.keys())
            missing = sorted(set(LAYER_BUCKETS) - set(detected))

            # Skip if vocabulary + structural evidence confirms genuine layering.
            if _has_sufficient_layering_evidence(max_depth, expr_counts, matched):
                continue

            gaps.append(
                LayeringGap(
                    gap_id=_gap_id(model.model_id),
                    model_id=model.model_id,
                    model_name=model.name,
                    detected_layers=detected,
                    missing_layers=missing,
                    table_count=len(model.tables),
                    max_derivation_depth=max_depth,
                    flat_table_ratio=flat_ratio,
                    expression_class_counts=expr_counts,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error checking layering for model %r: %s", model.name, exc)

    return gaps


# ---------------------------------------------------------------------------
# Severity and remediation (updated for structural context)
# ---------------------------------------------------------------------------

def severity_for_gap(gap: LayeringGap) -> str:
    """Map a LayeringGap to a finding severity string."""
    # Strong structural evidence of shallow architecture
    if gap.max_derivation_depth == 0 and not gap.detected_layers:
        return "high"
    if gap.max_derivation_depth == 0:
        return "medium"  # vocabulary present but no derivation chain
    return "low"          # some depth but not enough to confirm full layering


def remediation_hint_for_gap(gap: LayeringGap) -> str:
    """Return a remediation hint appropriate for the gap, informed by structural signals."""
    if gap.max_derivation_depth >= 1:
        non_passthrough = sum(
            v for k, v in gap.expression_class_counts.items()
            if k in ("transformed", "aggregated")
        )
        total = sum(gap.expression_class_counts.values()) or 1
        return (
            f"Derivation chain detected (max depth {gap.max_derivation_depth}) but "
            f"only {non_passthrough}/{total} tables apply structural transformations. "
            "Ensure each layer boundary introduces cleaning, type coercion, deduplication, "
            "or business-rule logic — not just a passthrough rename."
        )
    if not gap.detected_layers:
        return (
            "No staging-layer vocabulary detected and no inter-table derivation chain found. "
            "Introduce a bronze/silver/gold (or equivalent) layered architecture to separate "
            "raw ingestion, conformation, and serving concerns."
        )
    missing = " and ".join(gap.missing_layers)
    return (
        f"Vocabulary suggests partial layering but no derivation chain confirms it. "
        f"'{missing}' layer(s) appear absent. Verify that upstream ingestion and "
        "downstream serving stages exist as distinct semantic model tables or artifacts."
    )


# ---------------------------------------------------------------------------
# Ceiling note (honest communication of detection limits)
# ---------------------------------------------------------------------------

CEILING_NOTE = (
    "Layered Modeling is assessed via two structural signals (inter-table derivation depth "
    "from M-query expressions, and expression classification) plus vocabulary corroboration. "
    "The detector cannot distinguish 'transformation that improves data quality' from "
    "'transformation that merely reshapes columns' — notebook/dataflow logic inspection "
    "is required for full rigor (v3). A high score means structural layering is detectable; "
    "a low score should prompt: 'do your layers apply real cleaning and business rules, "
    "not just passthrough renames?'"
)
