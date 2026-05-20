# Implementation Plan: Modeling Readiness Assessor

**Branch**: `001-modeling-readiness-assessor` | **Date**: 2026-05-20 | **Spec**: `specs/001-modeling-readiness-assessor/spec.md`

**Input**: Feature specification from `/specs/001-modeling-readiness-assessor/spec.md`

## Summary

Build a two-component Modeling Readiness Assessor that lets customers (guided by a Microsoft architect) diagnose modeling debt in their Fabric tenant before deploying Fabric IQ and Data Agents. The **scanner** is a Python Fabric notebook that reads metadata from Power BI semantic models and Fabric IQ ontologies under the customer's own Fabric workspace identity, writes a schema-versioned findings artifact to OneLake, and never calls an LLM. The **narrator** is a cloneable Git repository containing an MCP server (Python, MSAL device-code auth, OneLake-read scope only) plus agent-customization files; the LLM-driven persona invokes findings exclusively through MCP tools that read the artifact — it never synthesizes findings from prose. A synthetic-data provisioner (Fabric notebooks) enables end-to-end demos without a real customer tenant.

## Technical Context

**Language/Version**:
- Scanner library & MCP server: Python 3.11
- Bootstrap scripts: PowerShell 5.1+ (Windows) + bash (macOS/Linux)
- Fabric notebooks: Python Fabric runtime (NOT PySpark)

**Primary Dependencies**:
- Scanner: `sempy` (Fabric semantic model SDK), `notebookutils`/`mssparkutils` (Fabric built-ins), `azure-identity` (Fabric runtime built-in), `rapidfuzz` (name similarity)
- Narrator MCP server: `fastmcp` (MCP SDK), `msal` (MSAL for Python), `azure-storage-file-datalake` (OneLake read)
- Testing: `pytest`, `pytest-cov`

**Storage**:
- OneLake findings artifact: `Files/modeling-readiness/<run-id>/` in the assessed Fabric workspace
- Repo config YAML: `narrator.config.yaml` in repo root (workspace URL cache, token_cache opt-in, similarity threshold)
- Optional token cache: `.narrator-token-cache` in repo root (gitignored, only created when `token_cache: enabled`)
- Scoring rubric: `scoring-rubric.yaml` in repo root (versioned, human-readable)

**Testing**: `pytest` with `pytest-cov` (≥80% unit coverage on deterministic modules, NFR-005). Scanner tests use fixture JSON; narrator tests use fixture findings artifact. No live Fabric tenant required for unit or integration tests.

**Target Platform**:
- Scanner: Fabric notebook runtime (Ubuntu-based, Python 3.11, no Spark)
- Narrator MCP server: Windows 10+, macOS 13+, Ubuntu 22.04+ (user's laptop)
- Bootstrap: Windows (PowerShell 5.1+) + macOS/Linux (bash)

**Project Type**: Two-component system — Fabric notebook (scanner) + Python MCP server + agent-customization files (narrator)

**Performance Goals**:
- Full assessment ≤5 min wall-clock for ≤50 semantic models + ≤5 ontologies (NFR-001)
- Provisioner run ≤10 min on F2 capacity (NFR-002)
- Cold-start to first deliverable ≤15 min (NFR-004)

**Constraints**:
- Scanner: no Spark, no admin, no new Entra app registration, Fabric Viewer+Run permissions only
- Narrator MCP server: OneLake read scope only — MUST NOT call Fabric or Power BI APIs directly
- Bootstrap: no admin privileges, no global state outside repo and AI-host config files
- All findings must cite source artifacts (model ID, ontology ID, table name)

**Scale/Scope**: Up to 50 semantic models and 5 ontologies per assessment run. Synthetic demo: 8–12 entities, 3–5 with deliberate debt across all four disciplines.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Check | Status |
|-----------|-------|--------|
| I. Diagnostic determinism | Scanner has zero LLM calls. Narrator LLM invokes findings only via MCP tools reading the artifact. No prose-level finding synthesis permitted. | ✅ PASS |
| II. Honesty about scope | FR-008 requires explicit "not assessed in this version" for Layered Modeling and Steward-Loop Modeling when signals absent. FR-023 requires marking unknown schema fields explicitly. | ✅ PASS |
| III. Read-only by default | Scanner writes only to `Files/modeling-readiness/<run-id>/`. Narrator reads only. Provisioner writes only to demo-tenant-flagged workspaces with cell-level confirmation. | ✅ PASS |
| IV. Findings reproducible | FR-010: every finding cites source artifact ID. FR-019: `raw/` subfolder enables manual verification. | ✅ PASS |
| V. Conversation as primary UX | Deliverables are Markdown files in `assessments/<timestamp>/`. In-chat output is concise. | ✅ PASS |
| VI. Framework is the framework | Scoring rubric YAML maps findings to four named disciplines only. FR-014 forbids abbreviations. | ✅ PASS |
| VII. Synthetic data canonical | FR-011/012 make provisioner a first-class spec item with acceptance criteria and teardown notebook. | ✅ PASS |
| VIII. Vocabulary is canonical | All code identifiers, docs, and deliverables use the four exact discipline names. | ✅ PASS |

**Post-design re-check**: MCP tool surface (FR-016) is strictly read-from-artifact; `scoring.py` raises on missing rubric to prevent silent hallucination; `artifact_reader.py` explicitly marks unknown fields. ✅ All gates pass.

## Project Structure

### Documentation (this feature)

```text
specs/001-modeling-readiness-assessor/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── findings-artifact.schema.md   # OneLake artifact schema (FR-019)
│   ├── mcp-tools.md                  # MCP tool surface (FR-016)
│   └── narrator-config.md            # Repo config YAML schema
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
scanner/
├── modeling-readiness-scanner.ipynb   # Main scanner notebook (FR-018)
├── provisioner.ipynb                  # Synthetic-data provisioner (FR-011)
├── provisioner-teardown.ipynb         # Teardown notebook (FR-012)
└── lib/
    └── scanner/
        ├── __init__.py
        ├── semantic_models.py         # FR-003: Power BI semantic model extraction
        ├── ontologies.py              # FR-004: Fabric IQ ontology extraction
        ├── canonical_entity.py        # FR-005/006: CEM conflict detection + similarity
        ├── field_lineage.py           # FR-007: Field-Level Lineage attribution audit
        ├── scoring.py                 # FR-008: maturity score computation from rubric
        ├── findings.py                # Finding, MaturityScore data types
        └── artifact.py               # FR-019: findings artifact writer

narrator/
└── mcp_server/
    ├── __init__.py
    ├── server.py                      # MCP server entry point (fastmcp)
    ├── auth.py                        # FR-001: MSAL device code + optional token cache
    ├── artifact_reader.py             # FR-023: forward-tolerant artifact reader
    ├── onelake.py                     # OneLake path resolution from workspace URL (FR-021)
    └── tools/
        ├── __init__.py
        ├── list_runs.py               # list_runs MCP tool
        ├── load_run.py                # load_run MCP tool
        ├── list_semantic_models.py    # list_semantic_models MCP tool
        ├── extract_entity_definitions.py
        ├── audit_source_attribution.py
        └── enumerate_ontologies.py

tests/
├── scanner/
│   ├── fixtures/                      # Synthetic findings fixture data
│   ├── test_semantic_models.py
│   ├── test_ontologies.py
│   ├── test_canonical_entity.py
│   ├── test_field_lineage.py
│   ├── test_scoring.py
│   └── test_artifact.py
└── narrator/
    ├── fixtures/                      # Captured findings artifact for narrator tests
    │   ├── manifest.json
    │   ├── findings.json
    │   └── raw/
    ├── test_tools.py
    ├── test_auth.py
    ├── test_artifact_reader.py
    └── test_onelake.py

assessments/                           # Deliverables written here by narrator (gitignored)

bootstrap.ps1                          # Windows bootstrap (FR-015)
bootstrap.sh                           # macOS/Linux bootstrap (FR-015)
narrator.config.yaml                   # Repo config (workspace URL, token cache, threshold)
scoring-rubric.yaml                    # FR-008 versioned scoring rubric
.gitignore                             # includes .narrator-token-cache, assessments/
.vscode/mcp.json                       # VS Code + GitHub Copilot MCP registration (FR-017)
```

**Structure Decision**: Two top-level packages (`scanner/`, `narrator/`) reflect the two-component distribution model. The scanner library (`scanner/lib/scanner/`) is imported by notebook cells; the narrator MCP server (`narrator/mcp_server/`) is the Python process registered with AI hosts by the bootstrap. Tests mirror this split so scanner tests run without an MCP server and narrator tests run without Fabric.

## Complexity Tracking

No constitution violations requiring justification. Architecture is the minimum viable structure for the two-component distribution model.

---

## Phase 0: Research

*See `research.md` for full decision log.*

Key decisions resolved:

| Decision | Resolution |
|----------|-----------|
| MCP Python SDK | `fastmcp` (stable tool decorator API, handles stdio/SSE transports) |
| OneLake read access | `azure-storage-file-datalake` + MSAL `PublicClientApplication` device code flow |
| Fabric semantic model extraction | `sempy.fabric` + Power BI REST API via `notebookutils.credentials.getToken` |
| Ontology extraction | Fabric IQ REST API (preview) via `notebookutils.credentials.getToken("fabric")` + `requests` |
| Name similarity algorithm | `rapidfuzz.fuzz.ratio()` (normalized Levenshtein); default threshold 0.85, config YAML overridable |
| Bootstrap host detection | Probe known config paths for VS Code, Claude Code, Cursor; configure all found silently |
| Scoring rubric format | YAML with `schema_version` key; `scoring.py` raises on missing/unparseable rubric |

## Phase 1: Design & Contracts

*See `data-model.md` for entity model. See `contracts/` for interface contracts.*

### Constitution Check (post-design)

All Phase 1 design decisions preserve all eight constitution principles:

- MCP tool surface is strictly read-from-artifact; no Fabric/Power BI API calls in narrator at contract level.
- `scoring.py` raises `RuntimeError` if rubric is missing — prevents silent hallucination.
- `artifact_reader.py` forward-tolerance contract explicitly marks unknown fields rather than silently ignoring.

**Gate**: ✅ PASS — no violations introduced in Phase 1 design.
