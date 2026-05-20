"""Deliverable generation for the Modeling Readiness narrator.

Renders the 4 Jinja templates with run data and writes them to
assessments/<YYYY-MM-DD>-<workspace-name>/

FR-002, FR-009, FR-010, FR-014: generate deliverables with exact discipline names,
source citations, and scope-honesty markers for not-assessed disciplines.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jinja2

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
ASSESSMENTS_DIR = Path(__file__).parent.parent.parent / "assessments"

TEMPLATE_FILES = [
    "executive-summary.md.jinja",
    "findings-detail.md.jinja",
    "remediation-plan.md.jinja",
    "workshop-agenda.md.jinja",
]

DISCIPLINE_LABELS = {
    "canonical_entity_modeling": "Canonical Entity Modeling",
    "field_level_lineage": "Field-Level Lineage",
    "layered_modeling": "Layered Modeling",
    "steward_loop_modeling": "Steward-Loop Modeling",
}


def _slug(text: str) -> str:
    """Convert workspace name to a filesystem-safe slug."""
    return re.sub(r"[^a-zA-Z0-9-]", "-", text).strip("-").lower()


def _enrich_scores(maturity_scores: list[dict]) -> list[dict]:
    """Add display labels to maturity score dicts."""
    enriched = []
    for score in maturity_scores:
        s = dict(score)
        s["discipline_label"] = DISCIPLINE_LABELS.get(s.get("discipline", ""), s.get("discipline", ""))
        raw_score = s.get("score")
        s["score_display"] = str(raw_score) if raw_score is not None else "—"
        enriched.append(s)
    return enriched


def generate_deliverables(
    run_data: dict,
    output_dir: Path | None = None,
    templates_dir: Path | None = None,
) -> list[Path]:
    """Render 4 Jinja templates and write deliverable files.

    Args:
        run_data: Dict with keys: manifest, findings, maturity_scores, unknown_fields.
                  Returned directly by ArtifactReader.load() or OneLakeArtifactReader.load().
        output_dir: Override output directory (default: assessments/<date>-<workspace>/).
        templates_dir: Override templates directory (default: templates/ in repo root).

    Returns:
        List of Paths to the 4 written files.
    """
    manifest = run_data.get("manifest", {})
    findings = run_data.get("findings", [])
    maturity_scores = run_data.get("maturity_scores", [])

    workspace_url = manifest.get("workspace_url", "")
    workspace_id = manifest.get("workspace_id", "unknown")
    workspace_name = _extract_workspace_name(workspace_url) or workspace_id
    run_id = manifest.get("run_id", "unknown")
    assessment_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    artifact_id = run_id

    enriched_scores = _enrich_scores(maturity_scores)
    has_not_assessed = any(
        s.get("assessment_status") == "not_assessed" for s in maturity_scores
    )

    context: dict[str, Any] = {
        "workspace_name": workspace_name,
        "workspace_url": workspace_url,
        "workspace_id": workspace_id,
        "run_id": run_id,
        "assessment_date": assessment_date,
        "artifact_id": artifact_id,
        "scanner_version": manifest.get("scanner_version", "0.1.0"),
        "artifact_counts": manifest.get("artifact_counts", {"semantic_models": 0, "ontologies": 0}),
        "findings": findings,
        "maturity_scores": enriched_scores,
        "total_findings": len(findings),
        "has_not_assessed": has_not_assessed,
    }

    tmpl_dir = templates_dir or TEMPLATES_DIR
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(tmpl_dir)),
        autoescape=False,
        keep_trailing_newline=True,
    )

    if output_dir is None:
        folder_name = f"{assessment_date}-{_slug(workspace_name)}"
        output_dir = ASSESSMENTS_DIR / folder_name

    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for tmpl_file in TEMPLATE_FILES:
        tmpl = env.get_template(tmpl_file)
        rendered = tmpl.render(**context)
        out_name = tmpl_file.replace(".jinja", "")
        out_path = output_dir / out_name
        out_path.write_text(rendered, encoding="utf-8")
        written.append(out_path)

    return written


def _extract_workspace_name(workspace_url: str) -> str:
    """Derive a human-readable workspace name from a Fabric workspace URL.

    Falls back to empty string if no name can be derived.
    """
    if not workspace_url:
        return ""
    # Try to extract from URL query params or path — Fabric URLs don't embed names,
    # so we return an empty string and let the caller use workspace_id as fallback.
    return ""
