# Contract: Narrator Configuration Schema

**File**: `narrator.config.yaml` (repo root)  
**Enforcement**: FR-015 (bootstrap), FR-001 (token cache), FR-005 (similarity threshold), FR-011 (demo workspace gate)

This file is plain-text, human-editable, and scoped to the cloned repository — not a global user setting.

---

## Schema

```yaml
# narrator.config.yaml
# See specs/001-modeling-readiness-assessor/quickstart.md for usage.

# Fabric workspace URL — cached after first use; paste to override.
# The narrator infers the OneLake findings folder path from this URL.
workspace_url: ""

# Set to true to persist the Entra device-code auth token across sessions.
# When enabled, the token is written to .narrator-token-cache (gitignored).
# Delete .narrator-token-cache to force re-authentication.
token_cache: false

# Name-similarity threshold for candidate canonical entity conflict detection.
# Range: 0.0–1.0. Default 0.85 minimizes false positives.
# Lower for tenants with heavily abbreviated naming conventions.
similarity_threshold: 0.85

# Set to true to allow the synthetic-data provisioner to write to this workspace.
# The provisioner checks this flag before any creation operation.
# NEVER set to true for a production or customer workspace.
demo_workspace: false
```

---

## Field Definitions

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `workspace_url` | string | `""` | Full Fabric workspace URL. Set automatically after first successful `list_runs` call. |
| `token_cache` | boolean | `false` | When `true`, MSAL token serialized to `.narrator-token-cache` in repo root. |
| `similarity_threshold` | float | `0.85` | Normalized Levenshtein ratio threshold for entity name matching (FR-005). |
| `demo_workspace` | boolean | `false` | Gate for provisioner writes (FR-011). Must be `true` for provisioner to proceed. |

---

## Validation Rules

- `similarity_threshold` must be in range `[0.5, 1.0]`; values outside this range are rejected with a human-readable error at startup.
- `demo_workspace: true` is logged as a warning in the bootstrap output and in every provisioner notebook cell to prevent accidental production writes.
- Unknown keys in `narrator.config.yaml` are silently ignored for forward compatibility.

---

## `.narrator-token-cache`

Created only when `token_cache: true`.  
**Location**: repo root (alongside `narrator.config.yaml`)  
**Format**: MSAL token cache JSON (serialized by `msal.SerializableTokenCache`)  
**Gitignore**: Listed in `.gitignore` by default — must never be committed.  
**Deletion**: Deleting this file forces re-authentication on next narrator session.

---

## Scoring Rubric (`scoring-rubric.yaml`)

Separate from `narrator.config.yaml`. Shipped in the repo root. Loaded at runtime by `scanner/lib/scanner/scoring.py`.

```yaml
# scoring-rubric.yaml
schema_version: "1.0"

# Thresholds apply to finding_count per discipline.
# Scores are assigned by the first matching threshold (ascending order).
disciplines:
  canonical_entity_modeling:
    thresholds:
      - max_findings: 0
        score: 4
      - max_findings: 2
        score: 3
      - max_findings: 5
        score: 2
      - max_findings: 10
        score: 1
      - score: 0          # catch-all: 11+ findings

  field_level_lineage:
    thresholds:
      - max_findings: 0
        score: 4
      - max_findings: 2
        score: 3
      - max_findings: 5
        score: 2
      - max_findings: 10
        score: 1
      - score: 0

  layered_modeling:
    # Scored only when unambiguous signals present; otherwise not_assessed.
    thresholds:
      - max_findings: 0
        score: 4
      - max_findings: 2
        score: 3
      - max_findings: 5
        score: 2
      - max_findings: 10
        score: 1
      - score: 0

  steward_loop_modeling:
    # Scored only when unambiguous signals present; otherwise not_assessed.
    thresholds:
      - max_findings: 0
        score: 4
      - max_findings: 2
        score: 3
      - max_findings: 5
        score: 2
      - max_findings: 10
        score: 1
      - score: 0
```

`scoring.py` raises `RuntimeError` if `scoring-rubric.yaml` is missing or has an unrecognized `schema_version`.
