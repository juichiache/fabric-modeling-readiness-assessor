"""Field-Level Lineage source attribution auditor.

Audits Fabric IQ ontology entity types for source-attribution property gaps.
The check is semantic — it tests the is_source_attribution flag on properties
and has_temporal_source_marker on bindings. It does NOT prescribe specific
property names (Framework Principle VI and constitution vocabulary rules).

FR-007: Audit source attribution gaps per entity type.
"""
from __future__ import annotations

import hashlib
import logging

from scanner.lib.scanner.findings import (
    EntityType,
    Ontology,
    SourceAttributionGap,
)

logger = logging.getLogger(__name__)

# Minimum number of distinct is_source_attribution=True properties expected.
# Four semantic roles: source-system identifier, source-record identifier,
# extraction-timestamp, confidence score.
# NOTE: These are documentation labels only — never used to positionally name
# which specific roles are absent (that would require field-name inspection,
# which contradicts the flag-based principle).
EXPECTED_ATTRIBUTION_COUNT = 4

ATTRIBUTION_ROLE_LABELS = [
    "source_system_identifier",
    "source_record_identifier",
    "extraction_timestamp",
    "confidence_score",
]


def _is_derived_entity(entity_type: EntityType) -> bool:
    """Return True if this entity is in-platform derived (computed, no external source).

    Derived entities (roll-ups, aggregates, virtual entities) have bindings but none
    point to a raw source. Flagging them for missing source attribution is a false
    positive — they have no external source to attribute.

    Entities with no bindings at all are not considered derived — they are audited
    normally (absence of bindings is itself a gap signal).
    """
    if not entity_type.bindings:
        return False
    return all(b.source_type not in ("semantic_model", "lakehouse_table")
               for b in entity_type.bindings)


def audit_field_level_lineage(ontologies: list[Ontology]) -> list[SourceAttributionGap]:
    """Audit all entity types across all ontologies for source-attribution gaps.

    An entity type is considered fully attributed when it has at least
    EXPECTED_ATTRIBUTION_COUNT properties with is_source_attribution=True
    AND at least one binding with has_temporal_source_marker=True.

    Derived/computed entity types (all bindings non-source-backed) are skipped —
    they have no external source to attribute.

    Returns:
        List of SourceAttributionGap for entity types that are not fully attributed.
    """
    gaps: list[SourceAttributionGap] = []

    for ontology in ontologies:
        for entity_type in ontology.entity_types:
            if _is_derived_entity(entity_type):
                logger.debug(
                    "Skipping derived entity type %r in ontology %r — no source attribution expected.",
                    entity_type.name,
                    ontology.ontology_id,
                )
                continue
            gap = _check_entity_type(entity_type, ontology.ontology_id)
            if gap is not None:
                gaps.append(gap)

    return gaps


def _check_entity_type(entity_type: EntityType, ontology_id: str) -> SourceAttributionGap | None:
    """Return a SourceAttributionGap if the entity type has attribution gaps, else None."""
    attribution_props = [p for p in entity_type.properties if p.is_source_attribution]
    attribution_count = len(attribution_props)

    # Flag-based only — no name-based fallback (Framework Principle VI).
    has_temporal = any(b.has_temporal_source_marker for b in entity_type.bindings)

    missing: list[str] = []

    if attribution_count < EXPECTED_ATTRIBUTION_COUNT:
        needed = EXPECTED_ATTRIBUTION_COUNT - attribution_count
        # Report count only — positional role labeling would be fictional precision
        # since we cannot determine which specific roles are absent without name inspection.
        missing.append(
            f"source_attribution_property ({needed} of {EXPECTED_ATTRIBUTION_COUNT} missing)"
        )

    if not has_temporal:
        missing.append("temporal_source_marker")

    if not missing:
        return None

    gap_id = "fll-" + hashlib.sha1(f"{ontology_id}|{entity_type.name}".encode()).hexdigest()[:8]
    return SourceAttributionGap(
        gap_id=gap_id,
        ontology_id=ontology_id,
        entity_type_name=entity_type.name,
        missing_attribution_types=missing,
        binding_count=len(entity_type.bindings),
    )
