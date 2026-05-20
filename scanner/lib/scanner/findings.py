"""Core domain dataclasses for the Modeling Readiness Assessor scanner.

All discipline references use the four exact canonical names from the constitution:
  - canonical_entity_modeling
  - field_level_lineage
  - layered_modeling
  - steward_loop_modeling
"""
from __future__ import annotations

from dataclasses import dataclass, field


CANONICAL_DISCIPLINES = frozenset({
    "canonical_entity_modeling",
    "field_level_lineage",
    "layered_modeling",
    "steward_loop_modeling",
})


# ---------------------------------------------------------------------------
# Workspace metadata (scoping context)
# ---------------------------------------------------------------------------


@dataclass
class ScanScope:
    type: str  # "full" | "single_discipline" | "single_artifact"
    discipline_filter: str | None = None
    artifact_filter: str | None = None


# ---------------------------------------------------------------------------
# Semantic model entities (FR-003)
# ---------------------------------------------------------------------------


@dataclass
class Measure:
    name: str
    table: str
    expression: str


@dataclass
class Relationship:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: str
    cross_filter_direction: str


@dataclass
class Table:
    name: str
    source_columns: list[str] = field(default_factory=list)
    primary_key_columns: list[str] = field(default_factory=list)
    source_expression: str | None = None


@dataclass
class SemanticModel:
    model_id: str
    name: str
    workspace_id: str
    tables: list[Table] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    measures: list[Measure] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Ontology entities (FR-004)
# ---------------------------------------------------------------------------


@dataclass
class OntologyProperty:
    name: str
    data_type: str
    is_source_attribution: bool = False


@dataclass
class OntologyRelationship:
    from_entity: str
    to_entity: str
    relationship_name: str


@dataclass
class DataBinding:
    binding_id: str
    source_type: str  # "semantic_model" | "lakehouse_table"
    source_id: str
    has_temporal_source_marker: bool = False


@dataclass
class EntityType:
    name: str
    properties: list[OntologyProperty] = field(default_factory=list)
    relationships: list[OntologyRelationship] = field(default_factory=list)
    bindings: list[DataBinding] = field(default_factory=list)


@dataclass
class Ontology:
    ontology_id: str
    name: str
    workspace_id: str
    entity_types: list[EntityType] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Canonical Entity Modeling entities (FR-005/006)
# ---------------------------------------------------------------------------


@dataclass
class EntityDefinition:
    logical_entity_name: str
    source_type: str  # "semantic_model" | "ontology"
    source_id: str
    source_name: str
    primary_key_columns: list[str] = field(default_factory=list)
    join_relationships: list[Relationship] = field(default_factory=list)
    measure_names: list[str] = field(default_factory=list)
    source_columns: list[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class Disagreement:
    dimension: str  # "primary_key" | "join_logic" | "filter_context" | "measure_definition" | "source_columns"
    description: str


@dataclass
class CanonicalEntityConflict:
    conflict_id: str
    logical_entity_name: str
    definitions: list[EntityDefinition] = field(default_factory=list)
    disagreements: list[Disagreement] = field(default_factory=list)
    confirmed: bool = False


# ---------------------------------------------------------------------------
# Field-Level Lineage entities (FR-007)
# ---------------------------------------------------------------------------


@dataclass
class SourceAttributionGap:
    gap_id: str
    ontology_id: str
    entity_type_name: str
    missing_attribution_types: list[str] = field(default_factory=list)
    binding_count: int = 0


# ---------------------------------------------------------------------------
# Findings and scoring (FR-008, FR-010, FR-019)
# ---------------------------------------------------------------------------


@dataclass
class SourceArtifactRef:
    artifact_type: str  # "semantic_model" | "ontology" | "lakehouse_table"
    artifact_id: str
    artifact_name: str


@dataclass
class Finding:
    finding_id: str
    discipline: str  # one of CANONICAL_DISCIPLINES
    severity: str  # "high" | "medium" | "low"
    description: str
    source_artifacts: list[SourceArtifactRef]  # FR-010: required, ≥1
    remediation_hint: str
    entity_name: str | None = None
    pattern_reference: str | None = None


@dataclass
class MaturityScore:
    discipline: str
    score: int | None  # 0–4, or None if not_assessed
    assessment_status: str  # "assessed" | "partially_assessed" | "not_assessed"
    finding_count: int
    rationale: str
    rubric_version: str


# ---------------------------------------------------------------------------
# Run summary (returned by list_runs MCP tool)
# ---------------------------------------------------------------------------


@dataclass
class RunSummary:
    run_id: str
    timestamp: str
    scanner_version: str
    workspace_id: str
    artifact_counts: dict[str, int] = field(default_factory=dict)
