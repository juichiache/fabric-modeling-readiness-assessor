# Data Model: Modeling Readiness Assessor

**Branch**: `001-modeling-readiness-assessor` | **Date**: 2026-05-20

All entities below map to Python dataclasses (scanner library) or TypedDicts (narrator MCP tools). Field names use `snake_case`; discipline references use exact canonical names from the constitution.

---

## Core Domain Entities

### Workspace

The unit of scope for a single scanner run.

| Field | Type | Notes |
|-------|------|-------|
| `workspace_id` | `str` (UUID) | Fabric workspace GUID |
| `workspace_url` | `str` | Full Fabric workspace URL; primary user gesture for narrator scoping (FR-021) |
| `display_name` | `str` | Human-readable name |

---

### SemanticModel

A Power BI semantic model item extracted by the scanner (FR-003).

| Field | Type | Notes |
|-------|------|-------|
| `model_id` | `str` (UUID) | Power BI dataset GUID; required on all findings citing this model (FR-010) |
| `name` | `str` | Display name |
| `workspace_id` | `str` | Parent workspace |
| `tables` | `list[Table]` | All tables in the model |
| `relationships` | `list[Relationship]` | All relationships |
| `measures` | `list[Measure]` | All measures |

### Table

| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | Table name |
| `source_columns` | `list[str]` | Column names the table exposes |
| `primary_key_columns` | `list[str]` | Declared primary key columns (empty if undeclared) |
| `source_expression` | `str \| None` | M query or SQL expression backing the table |

### Relationship

| Field | Type | Notes |
|-------|------|-------|
| `from_table` | `str` | |
| `from_column` | `str` | |
| `to_table` | `str` | |
| `to_column` | `str` | |
| `cardinality` | `str` | e.g., `"many-to-one"` |
| `cross_filter_direction` | `str` | e.g., `"single"`, `"both"` |

### Measure

| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | |
| `table` | `str` | Containing table |
| `expression` | `str` | DAX expression |

---

### Ontology

A Fabric IQ ontology item extracted by the scanner (FR-004).

| Field | Type | Notes |
|-------|------|-------|
| `ontology_id` | `str` (UUID) | Required on all findings citing this ontology (FR-010) |
| `name` | `str` | Display name |
| `workspace_id` | `str` | Parent workspace |
| `entity_types` | `list[EntityType]` | All entity types |

### EntityType

| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | Canonical entity type name within the ontology |
| `properties` | `list[OntologyProperty]` | All properties |
| `relationships` | `list[OntologyRelationship]` | Declared relationships to other entity types |
| `bindings` | `list[DataBinding]` | OneLake / semantic model data bindings |

### OntologyProperty

| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | |
| `data_type` | `str` | e.g., `"string"`, `"datetime"` |
| `is_source_attribution` | `bool` | `True` if this property carries source-system identifier, source-record identifier, extraction timestamp, or confidence score semantics |

### DataBinding

| Field | Type | Notes |
|-------|------|-------|
| `binding_id` | `str` | |
| `source_type` | `str` | `"semantic_model"` \| `"lakehouse_table"` |
| `source_id` | `str` | Model GUID or lakehouse table path |
| `has_temporal_source_marker` | `bool` | Presence of extraction-timestamp attribution |

---

### EntityDefinition

An extracted representation of how a semantic model or ontology defines a logical business entity. Used for Canonical Entity Modeling conflict detection (FR-005/006).

| Field | Type | Notes |
|-------|------|-------|
| `logical_entity_name` | `str` | Normalized canonical name (post-similarity matching) |
| `source_type` | `str` | `"semantic_model"` \| `"ontology"` |
| `source_id` | `str` | Model or ontology GUID |
| `source_name` | `str` | Display name of the source artifact |
| `primary_key_columns` | `list[str]` | |
| `join_relationships` | `list[Relationship]` | Relationships to related entities |
| `measure_names` | `list[str]` | Measure names (for comparison across definitions) |
| `source_columns` | `list[str]` | Underlying source columns |
| `confidence` | `float` | Similarity score that produced this match (0.85–1.0) |

---

### CanonicalEntityConflict

A detected disagreement between two or more EntityDefinitions claiming to represent the same logical entity. The unit of Canonical Entity Modeling debt (FR-006).

| Field | Type | Notes |
|-------|------|-------|
| `conflict_id` | `str` | Stable identifier for this conflict |
| `logical_entity_name` | `str` | The entity both definitions claim to represent |
| `definitions` | `list[EntityDefinition]` | The conflicting definitions (≥2) |
| `disagreements` | `list[Disagreement]` | Specific points of conflict |
| `confirmed` | `bool` | `False` until user confirms (edge case: candidate conflicts require user confirmation) |

### Disagreement

| Field | Type | Notes |
|-------|------|-------|
| `dimension` | `str` | `"primary_key"` \| `"join_logic"` \| `"filter_context"` \| `"measure_definition"` \| `"source_columns"` |
| `description` | `str` | Human-readable description of the disagreement |

---

### SourceAttributionGap

A detected absence of source-attribution properties on an entity type or its bindings. The unit of Field-Level Lineage debt (FR-007).

| Field | Type | Notes |
|-------|------|-------|
| `gap_id` | `str` | Stable identifier |
| `ontology_id` | `str` | Source ontology GUID |
| `entity_type_name` | `str` | The entity type missing attribution |
| `missing_attribution_types` | `list[str]` | e.g., `["source_system_identifier", "extraction_timestamp"]` |
| `binding_count` | `int` | Number of bindings on this entity type |

---

### Finding

A single observation about the workspace, mapped to one of the four disciplines, anchored to source artifacts, with severity and remediation hint. Persisted in `findings.json` (FR-019).

| Field | Type | Notes |
|-------|------|-------|
| `finding_id` | `str` | Stable, sortable identifier (e.g., `"cem-001"`) |
| `discipline` | `str` | Exactly one of: `"canonical_entity_modeling"`, `"field_level_lineage"`, `"layered_modeling"`, `"steward_loop_modeling"` |
| `severity` | `str` | `"high"` \| `"medium"` \| `"low"` |
| `entity_name` | `str \| None` | Logical entity name, if applicable |
| `description` | `str` | Human-readable finding description |
| `source_artifacts` | `list[SourceArtifactRef]` | Required (FR-010); ≥1 ref |
| `remediation_hint` | `str` | Short remediation pointer |
| `pattern_reference` | `str \| None` | Key into `docs/patterns.md` |

### SourceArtifactRef

| Field | Type | Notes |
|-------|------|-------|
| `artifact_type` | `str` | `"semantic_model"` \| `"ontology"` \| `"lakehouse_table"` |
| `artifact_id` | `str` | GUID or path |
| `artifact_name` | `str` | Display name |

---

### MaturityScore

A 0–4 score per discipline, derived deterministically from the scoring rubric (FR-008).

| Field | Type | Notes |
|-------|------|-------|
| `discipline` | `str` | One of the four canonical discipline names |
| `score` | `int \| None` | 0–4, or `None` if not assessed |
| `assessment_status` | `str` | `"assessed"` \| `"partially_assessed"` \| `"not_assessed"` |
| `finding_count` | `int` | Number of findings in this discipline |
| `rationale` | `str` | One sentence citing specific findings (or explaining non-assessment) |
| `rubric_version` | `str` | Version of the scoring rubric used |

---

### FindingsArtifact

The top-level container written by the scanner to OneLake. Schema-versioned contract between scanner and narrator (FR-019).

**`manifest.json`**:

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | `str` | e.g., `"1.0"` |
| `run_id` | `str` | Sortable timestamp + random suffix (e.g., `"20260520-143022-a3f7"`) |
| `timestamp` | `str` | ISO 8601 UTC |
| `scanner_version` | `str` | Semantic version of the scanner notebook |
| `workspace_id` | `str` | Assessed workspace GUID |
| `workspace_url` | `str` | Assessed workspace URL |
| `scope` | `ScanScope` | What was included/excluded |
| `artifact_counts` | `dict` | `{"semantic_models": N, "ontologies": N}` |

**`findings.json`**:

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | `str` | Must match `manifest.json` |
| `findings` | `list[Finding]` | All findings |
| `maturity_scores` | `list[MaturityScore]` | One per discipline |

**`raw/`** subfolder:
- `raw/semantic_models/<model-id>.json` — full REST API response for each semantic model
- `raw/ontologies/<ontology-id>.json` — full REST API response for each ontology

---

### RunSummary

Lightweight summary returned by the `list_runs` MCP tool; avoids loading full findings artifact until needed.

| Field | Type | Notes |
|-------|------|-------|
| `run_id` | `str` | |
| `timestamp` | `str` | ISO 8601 UTC |
| `scanner_version` | `str` | |
| `workspace_id` | `str` | |
| `artifact_counts` | `dict` | |

---

### ScanScope

| Field | Type | Notes |
|-------|------|-------|
| `type` | `str` | `"full"` \| `"single_discipline"` \| `"single_artifact"` |
| `discipline_filter` | `str \| None` | If scoped to one discipline |
| `artifact_filter` | `str \| None` | If scoped to one artifact |

---

## State Transitions

### Assessment Lifecycle

```
[User imports scanner notebook]
        ↓
[Scanner: enumerate artifacts → extract → analyze → compute scores]
        ↓
[Scanner writes FindingsArtifact to OneLake]
        ↓
[User clones narrator repo, bootstraps, signs in via device code]
        ↓
[Narrator: list_runs → load_run → extract_entity_definitions / audit_source_attribution]
        ↓
[LLM persona narrates findings in chat]
        ↓
[User requests deliverables → agent writes 4 Markdown files to assessments/<timestamp>/]
```

### CanonicalEntityConflict Confirmation

```
detected (confirmed=False) → [user confirms] → confirmed (confirmed=True) → scored
detected (confirmed=False) → [user rejects]  → discarded (not scored)
```
