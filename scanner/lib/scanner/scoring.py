"""Scoring engine for the Modeling Readiness Assessor.

Loads scoring-rubric.yaml at call time and derives MaturityScore deterministically
from finding counts. Raises RuntimeError on missing rubric or unknown schema_version.

Any discipline can receive not_assessed by passing has_signals=False.
This is the universal gate — no hardcoded per-discipline list.
"""
from __future__ import annotations

import os

import yaml

from scanner.lib.scanner.findings import MaturityScore

SUPPORTED_SCHEMA_VERSIONS = {"1.0"}


def load_rubric(rubric_path: str) -> dict:
    """Load and return the parsed scoring rubric YAML.

    Raises RuntimeError if the file does not exist.
    """
    if not os.path.exists(rubric_path):
        raise RuntimeError(
            f"Scoring rubric not found: {rubric_path!r}. "
            "Ensure scoring-rubric.yaml is present in the repository root."
        )
    with open(rubric_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def compute_score(
    discipline: str,
    finding_count: int,
    rubric: dict,
    *,
    has_signals: bool = True,
    rationale: str | None = None,
) -> MaturityScore:
    """Derive a MaturityScore for a discipline from a finding count.

    Args:
        discipline: Exact canonical discipline name.
        finding_count: Number of findings in this discipline.
        rubric: Parsed rubric dict (from load_rubric or inline test fixture).
        has_signals: Pass False when the discipline could not be assessed
            (no ontologies, skipped due to size, extraction failed, etc.)
            to return not_assessed rather than a potentially false score.
        rationale: Optional override rationale string.

    Raises:
        RuntimeError: If schema_version is missing or unrecognized.
        KeyError: If discipline is not present in the rubric.
    """
    version = rubric.get("schema_version")
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise RuntimeError(
            f"Unrecognized scoring rubric schema_version: {version!r}. "
            f"Supported versions: {sorted(SUPPORTED_SCHEMA_VERSIONS)}"
        )

    if not has_signals:
        return MaturityScore(
            discipline=discipline,
            score=None,
            assessment_status="not_assessed",
            finding_count=finding_count,
            rationale=rationale or (
                f"{discipline} was not assessed in this version — "
                "no unambiguous signals present in the scanned workspace."
            ),
            rubric_version=version,
        )

    # KeyError propagates naturally if discipline is absent — callers catch it.
    thresholds = rubric["disciplines"][discipline]["thresholds"]
    score = _resolve_score(finding_count, thresholds)

    return MaturityScore(
        discipline=discipline,
        score=score,
        assessment_status="assessed",
        finding_count=finding_count,
        rationale=rationale or _default_rationale(discipline, finding_count, score),
        rubric_version=version,
    )

    # KeyError propagates naturally if discipline is absent — callers catch it.
    thresholds = rubric["disciplines"][discipline]["thresholds"]
    score = _resolve_score(finding_count, thresholds)

    return MaturityScore(
        discipline=discipline,
        score=score,
        assessment_status="assessed",
        finding_count=finding_count,
        rationale=rationale or _default_rationale(discipline, finding_count, score),
        rubric_version=version,
    )


def _resolve_score(finding_count: int, thresholds: list[dict]) -> int:
    """Walk threshold entries in order; return score for first matching band."""
    for entry in thresholds:
        if "max_findings" not in entry:
            # Catch-all entry (no max_findings key).
            return entry["score"]
        if finding_count <= entry["max_findings"]:
            return entry["score"]
    # Safety fallback — should not reach here with a well-formed rubric.
    return 0


def _default_rationale(discipline: str, finding_count: int, score: int) -> str:
    return (
        f"{finding_count} finding(s) detected in {discipline}; "
        f"score {score}/4 per rubric v1.0."
    )
