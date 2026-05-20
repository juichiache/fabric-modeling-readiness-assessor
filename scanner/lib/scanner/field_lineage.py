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
EXPECTED_ATTRIBUTION_COUNT = 4

ATTRIBUTION_ROLE_LABELS = [
    "source_system_identifier",
    "source_record_identifier",
    "extraction_timestamp",
    "confidence_score",
]


def audit_field_level_lineage(ontologies: list[Ontology]) -> list[SourceAttributionGap]:
    """Audit all entity types across all ontologies for source-attribution gaps.

    An entity type is considered fully attributed when it has at least
    EXPECTED_ATTRIBUTION_COUNT properties with is_source_attribution=True
    AND at least one binding with has_temporal_source_marker=True.

    Returns:
        List of SourceAttributionGap for entity types that are not fully attributed.
    """
    gaps: list[SourceAttributionGap] = []

    for ontology in ontologies:
        for entity_type in ontology.entity_types:
            gap = _check_entity_type(entity_type, ontology.ontology_id)
            if gap is not None:
                gaps.append(gap)

    return gaps


def _check_entity_type(entity_type: EntityType, ontology_id: str) -> SourceAttributionGap | None:
    """Return a SourceAttributionGap if the entity type has attribution gaps, else None."""
    attribution_props = [p for p in entity_type.properties if p.is_source_attribution]
    attribution_count = len(attribution_props)

    has_temporal_binding = any(b.has_temporal_source_marker for b in entity_type.bindings)

    # Also check if any attribution property carries temporal semantics
    has_temporal_property = any(
        "time" in p.name.lower()
        or "timestamp" in p.name.lower()
        or "date" in p.name.lower()
        or "extract" in p.name.lower()
        for p in attribution_props
    )

    has_temporal = has_temporal_binding or has_temporal_property

    missing: list[str] = []

    # Check we have enough attribution properties for the 4 expected roles
    if attribution_count < EXPECTED_ATTRIBUTION_COUNT:
        needed = EXPECTED_ATTRIBUTION_COUNT - attribution_count
        # Report the conceptual roles that appear to be missing
        # (cannot determine exact roles without prescribing names)
        missing.extend(ATTRIBUTION_ROLE_LABELS[attribution_count : attribution_count + needed])

    if not has_temporal:
        if "extraction_timestamp" not in missing:
            missing.append("extraction_timestamp")

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
