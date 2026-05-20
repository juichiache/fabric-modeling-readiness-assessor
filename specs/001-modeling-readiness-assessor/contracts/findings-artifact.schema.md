# Contract: OneLake Findings Artifact Schema

**Schema Version**: 1.0  
**Owner**: Scanner (writer) → Narrator (reader)  
**Path**: `Files/modeling-readiness/<run-id>/` in the assessed Fabric workspace OneLake  
**Enforcement**: FR-019, FR-023 (narrator must be forward-tolerant)

---

## Run ID Format

```
<run-id> = YYYYMMDD-HHmmss-<4-char-random-hex>
Example:  20260520-143022-a3f7
```

Run IDs are lexicographically sortable by timestamp. The narrator selects the most recent run by default (FR-022).

---

## Directory Layout

```
Files/modeling-readiness/
└── <run-id>/
    ├── manifest.json        # Run metadata — read first by narrator
    ├── findings.json        # All findings and maturity scores
    └── raw/
        ├── semantic_models/
        │   └── <model-id>.json    # Full REST API response per model
        └── ontologies/
            └── <ontology-id>.json # Full REST API response per ontology
```

---

## `manifest.json`

```json
{
  "schema_version": "1.0",
  "run_id": "20260520-143022-a3f7",
  "timestamp": "2026-05-20T14:30:22Z",
  "scanner_version": "0.1.0",
  "workspace_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "workspace_url": "https://app.fabric.microsoft.com/groups/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "scope": {
    "type": "full",
    "discipline_filter": null,
    "artifact_filter": null
  },
  "artifact_counts": {
    "semantic_models": 5,
    "ontologies": 2
  }
}
```

### Field definitions

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `schema_version` | string | ✅ | Semver string. Narrator refuses only when required fields in its known version are missing (corruption signal, not version skew). |
| `run_id` | string | ✅ | Matches directory name |
| `timestamp` | string | ✅ | ISO 8601 UTC |
| `scanner_version` | string | ✅ | Semantic version of scanner notebook |
| `workspace_id` | string | ✅ | Fabric workspace GUID |
| `workspace_url` | string | ✅ | Full workspace URL |
| `scope.type` | string | ✅ | `"full"` \| `"single_discipline"` \| `"single_artifact"` |
| `scope.discipline_filter` | string \| null | ✅ | Canonical discipline name or null |
| `scope.artifact_filter` | string \| null | ✅ | Artifact GUID or null |
| `artifact_counts` | object | ✅ | `{"semantic_models": N, "ontologies": N}` |

---

## `findings.json`

```json
{
  "schema_version": "1.0",
  "findings": [
    {
      "finding_id": "cem-001",
      "discipline": "canonical_entity_modeling",
      "severity": "high",
      "entity_name": "Customer",
      "description": "Three semantic models (CRM-Sales, ERP-Finance, Invoicing-Legacy) define a 'Customer' entity with inconsistent primary key choices: CRM uses CustomerGUID, ERP uses AccountNumber, Invoicing uses InvoiceCustomerID.",
      "source_artifacts": [
        {"artifact_type": "semantic_model", "artifact_id": "uuid-1", "artifact_name": "CRM-Sales"},
        {"artifact_type": "semantic_model", "artifact_id": "uuid-2", "artifact_name": "ERP-Finance"},
        {"artifact_type": "semantic_model", "artifact_id": "uuid-3", "artifact_name": "Invoicing-Legacy"}
      ],
      "remediation_hint": "Define a canonical Customer entity with a reconciliation rule documenting the authoritative primary key and the mapping from each source system.",
      "pattern_reference": "reconciliation-rule-documentation"
    }
  ],
  "maturity_scores": [
    {
      "discipline": "canonical_entity_modeling",
      "score": 1,
      "assessment_status": "assessed",
      "finding_count": 7,
      "rationale": "Seven canonical entity conflicts detected across Customer, Product, and Vendor entities; primary key disagreements in all three.",
      "rubric_version": "1.0"
    },
    {
      "discipline": "field_level_lineage",
      "score": 0,
      "assessment_status": "assessed",
      "finding_count": 12,
      "rationale": "No source-attribution properties found on any entity type in the assessed ontology.",
      "rubric_version": "1.0"
    },
    {
      "discipline": "layered_modeling",
      "score": null,
      "assessment_status": "not_assessed",
      "finding_count": 0,
      "rationale": "No unambiguous Layered Modeling signals (multi-workspace shared ontology dependencies) detected in this workspace. Assessment reserved for v2.",
      "rubric_version": "1.0"
    },
    {
      "discipline": "steward_loop_modeling",
      "score": null,
      "assessment_status": "not_assessed",
      "finding_count": 0,
      "rationale": "No unambiguous Steward-Loop Modeling signals (rules and actions wired to user input) detected in this workspace. Assessment reserved for v2.",
      "rubric_version": "1.0"
    }
  ]
}
```

### `findings[]` field definitions

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `finding_id` | string | ✅ | Stable, sortable (e.g., `"cem-001"`) |
| `discipline` | string | ✅ | Exactly one of the four canonical discipline names (snake_case) |
| `severity` | string | ✅ | `"high"` \| `"medium"` \| `"low"` |
| `entity_name` | string \| null | ✅ | Logical entity name, null for non-entity findings |
| `description` | string | ✅ | Human-readable finding |
| `source_artifacts` | array | ✅ | ≥1 item; each has `artifact_type`, `artifact_id`, `artifact_name` |
| `remediation_hint` | string | ✅ | Short remediation pointer |
| `pattern_reference` | string \| null | ✅ | Key into `docs/patterns.md` or null |

### `maturity_scores[]` field definitions

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `discipline` | string | ✅ | One of the four canonical discipline names |
| `score` | integer \| null | ✅ | 0–4, or null if `assessment_status` is `"not_assessed"` |
| `assessment_status` | string | ✅ | `"assessed"` \| `"partially_assessed"` \| `"not_assessed"` |
| `finding_count` | integer | ✅ | Total findings for this discipline |
| `rationale` | string | ✅ | One sentence citing specific findings (or explaining non-assessment) |
| `rubric_version` | string | ✅ | Version of scoring rubric used |

---

## Forward Compatibility (FR-023)

When the narrator encounters a `manifest.json` or `findings.json` with a `schema_version` newer than its known version:

1. It reads all fields it recognizes.
2. It marks unknown top-level sections as `"produced by a newer scanner (schema vX.Y); not interpreted in this version"` in both in-chat output and generated deliverables.
3. It proceeds — it does NOT refuse or raise an error.
4. It refuses ONLY when required fields declared mandatory in its known schema version are absent (corruption signal).
