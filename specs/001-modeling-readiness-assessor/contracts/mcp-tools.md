# Contract: MCP Tool Surface

**Owner**: Narrator MCP server (`narrator/mcp_server/`)  
**Enforcement**: FR-016, FR-020  
**Key constraint**: All tools read exclusively from the OneLake findings artifact. No tool may call Fabric or Power BI APIs. This is the physical enforcement of Principle I (diagnostic determinism) for the narrator.

---

## Tool: `list_runs`

**File**: `narrator/mcp_server/tools/list_runs.py`

Lists available assessment runs in a Fabric workspace's findings folder.

### Input

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `workspace_url` | string | ✅ | Full Fabric workspace URL (e.g., `https://app.fabric.microsoft.com/groups/<id>`) |

### Output

```json
{
  "runs": [
    {
      "run_id": "20260520-143022-a3f7",
      "timestamp": "2026-05-20T14:30:22Z",
      "scanner_version": "0.1.0",
      "workspace_id": "uuid",
      "artifact_counts": {"semantic_models": 5, "ontologies": 2}
    }
  ],
  "selected_run_id": "20260520-143022-a3f7",
  "note": "2 prior runs available. Ask to compare or select a specific run."
}
```

`selected_run_id` is the most recent run (lexicographic sort on `run_id`). `note` is omitted when only one run exists.

---

## Tool: `load_run`

**File**: `narrator/mcp_server/tools/load_run.py`

Loads the manifest and top-level summary from a specific run. Does not load the full findings list (use `extract_entity_definitions` / `audit_source_attribution` for that).

### Input

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `run_id` | string | ✅ | From `list_runs` output |
| `workspace_url` | string | ✅ | |

### Output

```json
{
  "manifest": { /* full manifest.json contents */ },
  "maturity_scores": [ /* maturity_scores array from findings.json */ ],
  "unknown_fields": []
}
```

`unknown_fields` lists any top-level keys in the artifact not recognized by this narrator version (forward-compatibility signal per FR-023).

---

## Tool: `list_semantic_models`

**File**: `narrator/mcp_server/tools/list_semantic_models.py`

Returns the list of semantic models observed in the run, derived from the findings artifact.

### Input

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `run_id` | string | ✅ | |
| `workspace_url` | string | ✅ | |

### Output

```json
{
  "semantic_models": [
    {
      "model_id": "uuid",
      "name": "CRM-Sales",
      "table_count": 12,
      "measure_count": 34,
      "relationship_count": 8
    }
  ]
}
```

---

## Tool: `extract_entity_definitions`

**File**: `narrator/mcp_server/tools/extract_entity_definitions.py`

Returns entity definitions extracted by the scanner, optionally filtered to a specific logical entity name.

### Input

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `run_id` | string | ✅ | |
| `workspace_url` | string | ✅ | |
| `entity_name` | string | ❌ | Filter to one logical entity; omit for all |

### Output

```json
{
  "entity_definitions": [
    {
      "logical_entity_name": "Customer",
      "source_type": "semantic_model",
      "source_id": "uuid-1",
      "source_name": "CRM-Sales",
      "primary_key_columns": ["CustomerGUID"],
      "measure_names": ["Total Revenue", "Order Count"],
      "source_columns": ["CustomerGUID", "CustomerName", "Region"],
      "confidence": 1.0
    }
  ],
  "conflicts": [
    {
      "conflict_id": "cem-conflict-001",
      "logical_entity_name": "Customer",
      "definition_count": 3,
      "confirmed": false,
      "disagreements": [
        {
          "dimension": "primary_key",
          "description": "CRM uses CustomerGUID; ERP uses AccountNumber; Invoicing uses InvoiceCustomerID"
        }
      ]
    }
  ]
}
```

---

## Tool: `audit_source_attribution`

**File**: `narrator/mcp_server/tools/audit_source_attribution.py`

Returns Field-Level Lineage source-attribution gaps found in the run.

### Input

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `run_id` | string | ✅ | |
| `workspace_url` | string | ✅ | |
| `entity_type_name` | string | ❌ | Filter to one entity type; omit for all |

### Output

```json
{
  "gaps": [
    {
      "gap_id": "fll-gap-001",
      "ontology_id": "uuid",
      "entity_type_name": "Customer",
      "missing_attribution_types": ["source_system_identifier", "extraction_timestamp"],
      "binding_count": 3
    }
  ],
  "total_entity_types_assessed": 8,
  "entity_types_with_full_attribution": 1
}
```

---

## Tool: `enumerate_ontologies`

**File**: `narrator/mcp_server/tools/enumerate_ontologies.py`

Returns the list of Fabric IQ ontologies observed in the run.

### Input

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `run_id` | string | ✅ | |
| `workspace_url` | string | ✅ | |

### Output

```json
{
  "ontologies": [
    {
      "ontology_id": "uuid",
      "name": "Manufacturing-Ontology",
      "entity_type_count": 8,
      "binding_count": 14,
      "entity_types_with_source_attribution": 1,
      "entity_types_without_source_attribution": 7
    }
  ]
}
```

---

## Error Responses

All tools return a consistent error envelope when the artifact cannot be read or a required field is missing:

```json
{
  "error": {
    "code": "ARTIFACT_NOT_FOUND" | "SCHEMA_CORRUPTION" | "AUTH_REQUIRED" | "PERMISSION_DENIED",
    "message": "Human-readable description",
    "run_id": "...",
    "workspace_url": "..."
  }
}
```

`AUTH_REQUIRED` is returned when the MSAL token has expired and the narrator needs to re-prompt the user for device code sign-in.
