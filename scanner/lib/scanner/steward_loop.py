"""Steward-Loop Modeling gap detection (Discipline 4).

Scans semantic model tables/measures and ontology entity types for vocabulary
that implies a human-in-the-loop data quality feedback cycle. Does NOT prescribe
exact names; detection is vocabulary-based (Framework Principle VI).

v2 additions (d4-binding-check):
- Correction-capture structure detection: identifies tables/entities whose name
  implies they hold correction or exception data.
- Relationship-wiring check: confirms whether a correction-capture structure is
  referenced by relationships from other tables (closing path to the model).

has_signals semantics
---------------------
Because steward-loop vocabulary is entirely optional in a workspace that has
not yet adopted quality practices, absence of vocabulary cannot be distinguished
from different naming conventions. Therefore:

- ``has_signals = True``  → at least one stewardship-vocabulary token was found
  anywhere in the workspace.  Gaps are scored normally.
- ``has_signals = False`` → no tokens found; discipline is returned as not_assessed
  rather than reporting every scope as a gap.

Honest ceiling
--------------
This detector sees only Fabric-side stewardship machinery: correction tables,
feedback measures, and ontology relationships. It cannot detect correction
processes running in external systems (Power BI report annotations, Teams
messages, Excel overrides, ServiceNow tickets). A low or not_assessed score
should prompt: "do you run a data quality correction workflow outside Fabric?"
"""
from __future__ import annotations

import hashlib
import logging
import re

from scanner.lib.scanner.findings import Ontology, SemanticModel, StewardLoopGap

logger = logging.getLogger(__name__)

# Vocabulary that implies the presence of a stewardship / feedback-loop pattern.
TABLE_ENTITY_VOCAB: frozenset[str] = frozenset({
    "correction", "corrections", "override", "overrides", "exception", "exceptions",
    "feedback", "review", "reviews", "approval", "approvals", "approved",
    "reject", "rejected", "flag", "flagged", "flags", "issue", "issues",
    "steward", "stewardship", "quality", "dq", "audit", "audits",
    "validation", "validations", "alert", "alerts", "dispute", "disputes",
    "annotation", "annotations", "remediation", "remediations",
})

MEASURE_VOCAB: frozenset[str] = frozenset({
    "error", "exception", "correction", "reject", "flag", "quality",
    "accuracy", "completeness", "validity", "integrity", "conformity",
    "steward", "audit", "review", "feedback", "score",
})

# Tokens strongly associated with correction-capture structures (d4-binding-check).
# These are the names SLM-01 describes for typed correction entities.
CORRECTION_CAPTURE_VOCAB: frozenset[str] = frozenset({
    "correction", "corrections", "exception", "exceptions", "override", "overrides",
    "remediation", "remediations", "dispute", "disputes", "feedback",
})

_TOKEN_SPLITTER = re.compile(
    r"(?<=[a-z])(?=[A-Z])"
    r"|(?<=[A-Z])(?=[A-Z][a-z])"
    r"|[\s_\-]+"
)


def _tokenize(name: str) -> list[str]:
    return [t.lower() for t in _TOKEN_SPLITTER.split(name) if t]


# ---------------------------------------------------------------------------
# Correction-capture binding check (d4-binding-check)
# ---------------------------------------------------------------------------

def _detect_correction_binding_model(
    model: SemanticModel,
) -> tuple[bool, bool]:
    """Check whether a correction-capture structure exists and is wired in (semantic model).

    Returns:
        (correction_structure_found, correction_has_relationships)
    """
    # Find tables whose name tokens match the correction-capture vocabulary
    correction_tables = [
        t.name for t in model.tables
        if any(tok in CORRECTION_CAPTURE_VOCAB for tok in _tokenize(t.name))
    ]
    if not correction_tables:
        return False, False

    # Check whether any relationship references a correction table (either direction)
    correction_set = set(correction_tables)
    has_rels = any(
        r.from_table in correction_set or r.to_table in correction_set
        for r in model.relationships
    )
    return True, has_rels


def _detect_correction_binding_ontology(
    ontology: Ontology,
) -> tuple[bool, bool]:
    """Check whether a correction-capture structure exists and is wired in (ontology).

    Returns:
        (correction_structure_found, correction_has_relationships)
    """
    correction_entities = [
        et.name for et in ontology.entity_types
        if any(tok in CORRECTION_CAPTURE_VOCAB for tok in _tokenize(et.name))
    ]
    if not correction_entities:
        return False, False

    # Check whether any relationship references a correction entity (either direction)
    correction_set = set(correction_entities)
    has_rels = any(
        r.from_entity in correction_set or r.to_entity in correction_set
        for et in ontology.entity_types
        for r in et.relationships
    )
    return True, has_rels


# ---------------------------------------------------------------------------
# Existing vocabulary scan (updated to include binding check)
# ---------------------------------------------------------------------------

def _scan_model(model: SemanticModel) -> tuple[list[str], list[str], bool, bool]:
    """Return (detected_signals, missing_signals, correction_found, correction_wired)."""
    detected: list[str] = []

    table_tokens = [t for table in model.tables for t in _tokenize(table.name)]
    for token in table_tokens:
        if token in TABLE_ENTITY_VOCAB and token not in detected:
            detected.append(token)

    measure_tokens = [t for m in model.measures for t in _tokenize(m.name)]
    for token in measure_tokens:
        if token in MEASURE_VOCAB and token not in detected:
            detected.append(f"measure:{token}")

    missing: list[str] = []
    has_table_signal = any(t in TABLE_ENTITY_VOCAB for t in table_tokens)
    has_measure_signal = any(t in MEASURE_VOCAB for t in measure_tokens)

    if not has_table_signal:
        missing.append("correction_or_feedback_table")
    if not has_measure_signal:
        missing.append("quality_or_feedback_measure")

    corr_found, corr_wired = _detect_correction_binding_model(model)
    return detected, missing, corr_found, corr_wired


def _scan_ontology(ontology: Ontology) -> tuple[list[str], list[str], bool, bool]:
    """Return (detected_signals, missing_signals, correction_found, correction_wired)."""
    detected: list[str] = []

    entity_tokens = [t for et in ontology.entity_types for t in _tokenize(et.name)]
    for token in entity_tokens:
        if token in TABLE_ENTITY_VOCAB and token not in detected:
            detected.append(token)

    rel_pairs: set[frozenset[str]] = set()
    for et in ontology.entity_types:
        for rel in et.relationships:
            pair = frozenset({rel.from_entity, rel.to_entity})
            if pair in rel_pairs:
                if "bidirectional_relationship" not in detected:
                    detected.append("bidirectional_relationship")
            rel_pairs.add(pair)

    rel_tokens = [
        t
        for et in ontology.entity_types
        for rel in et.relationships
        for t in _tokenize(rel.relationship_name)
    ]
    for token in rel_tokens:
        if token in TABLE_ENTITY_VOCAB and token not in detected:
            detected.append(f"rel:{token}")

    missing: list[str] = []
    if not detected:
        missing.append("stewardship_entity_or_relationship")

    corr_found, corr_wired = _detect_correction_binding_ontology(ontology)
    return detected, missing, corr_found, corr_wired


def _gap_id(scope_id: str, scope_type: str) -> str:
    return "sl-" + hashlib.sha1(f"{scope_type}|{scope_id}".encode()).hexdigest()[:8]


def detect_steward_loop_gaps(
    models: list[SemanticModel],
    ontologies: list[Ontology],
) -> tuple[list[StewardLoopGap], bool]:
    """Detect steward-loop modeling gaps across models and ontologies.

    Returns:
        (gaps, has_signals) where has_signals=False means no stewardship vocabulary
        was found anywhere — discipline should be scored as not_assessed.
    """
    gaps: list[StewardLoopGap] = []
    any_signal_found = False

    for model in models:
        if not model.tables and not model.measures:
            continue
        try:
            detected, missing, corr_found, corr_wired = _scan_model(model)
            if detected:
                any_signal_found = True
            if missing:
                gaps.append(StewardLoopGap(
                    gap_id=_gap_id(model.model_id, "semantic_model"),
                    scope_id=model.model_id,
                    scope_type="semantic_model",
                    scope_name=model.name,
                    missing_signals=missing,
                    detected_signals=detected,
                    correction_structure_found=corr_found,
                    correction_has_relationships=corr_wired,
                ))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error scanning steward-loop signals for model %r: %s", model.name, exc)

    for ontology in ontologies:
        try:
            detected, missing, corr_found, corr_wired = _scan_ontology(ontology)
            if detected:
                any_signal_found = True
            if missing:
                gaps.append(StewardLoopGap(
                    gap_id=_gap_id(ontology.ontology_id, "ontology"),
                    scope_id=ontology.ontology_id,
                    scope_type="ontology",
                    scope_name=ontology.name,
                    missing_signals=missing,
                    detected_signals=detected,
                    correction_structure_found=corr_found,
                    correction_has_relationships=corr_wired,
                ))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error scanning steward-loop signals for ontology %r: %s", ontology.name, exc)

    return gaps, any_signal_found


def severity_for_gap(gap: StewardLoopGap) -> str:
    """Map a StewardLoopGap to a finding severity string."""
    detected = gap.detected_signals
    missing = gap.missing_signals
    has_table = any("table" in s or "entity" in s or ":" not in s for s in detected)
    has_measure = any("measure:" in s for s in detected)

    if not detected:
        return "high"
    if has_table and not has_measure:
        return "medium"
    if has_measure and not has_table:
        return "low"
    return "low"


def remediation_hint_for_gap(gap: StewardLoopGap) -> str:
    """Return a remediation hint for the gap, including structural binding context."""
    missing = gap.missing_signals
    if not gap.detected_signals:
        return (
            "No stewardship vocabulary detected (correction, feedback, quality, audit, etc.). "
            "Consider adding tables or ontology entity types that capture data quality "
            "issues, corrections, and reviewer feedback to close the steward loop."
        )
    hints = []
    if gap.correction_structure_found and not gap.correction_has_relationships:
        hints.append(
            "A correction-capture structure exists but is not referenced by any model "
            "relationships — it may be orphaned. Wire it into the data model so corrections "
            "can flow back to canonical entity definitions."
        )
    if "correction_or_feedback_table" in missing:
        hints.append("Add a correction or feedback table to capture data quality exceptions.")
    if "quality_or_feedback_measure" in missing:
        hints.append("Add quality or accuracy measures to quantify stewardship health.")
    if "stewardship_entity_or_relationship" in missing:
        hints.append("Add stewardship entity types or review relationships to the ontology.")
    return " ".join(hints) or "Verify stewardship coverage across all scoped artifacts."


# ---------------------------------------------------------------------------
# Ceiling note (honest communication of detection limits)
# ---------------------------------------------------------------------------

CEILING_NOTE = (
    "Steward-Loop Modeling is assessed by detecting Fabric-side stewardship machinery: "
    "correction/exception tables, quality measures, and ontology feedback relationships. "
    "The scanner cannot detect correction processes running in external systems "
    "(Power BI annotations, Teams messages, Excel overrides, ServiceNow tickets). "
    "A low score is a prompt to ask: 'do you run a data quality correction workflow "
    "outside Fabric?' — not a verdict that no steward loop exists. "
    "Population and recency checks (is the corrections table actually used?) require "
    "the lightweight OneLake data layer and are deferred to a future version."
)
