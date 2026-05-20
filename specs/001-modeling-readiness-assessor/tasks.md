# Tasks: Modeling Readiness Assessor

**Input**: Design documents from `specs/001-modeling-readiness-assessor/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅ | quickstart.md ✅

**Tests**: Included — the constitution's Development Workflow mandates tests for deterministic analysis modules before implementation. NFR-005 requires ≥80% unit test coverage on deterministic modules.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US7)
- Exact file paths are required in every task description

## User Story Map

| Story | Priority | Description | Key FRs |
|-------|----------|-------------|---------|
| US1 | P1 🎯 | Scanner: enumerate artifacts, write findings artifact | FR-003, FR-004, FR-018, FR-019 |
| US2 | P1 | Canonical Entity Modeling analysis | FR-005, FR-006, FR-008 |
| US3 | P1 | Field-Level Lineage analysis | FR-007, FR-008 |
| US4 | P1 | Narrator MCP server: auth, artifact read, tool surface | FR-001, FR-016, FR-020–FR-023 |
| US5 | P1 | Deliverables, scan plan, scope honesty | FR-002, FR-008–FR-010, FR-013, FR-014 |
| US6 | P2 | Bootstrap & multi-host MCP registration | FR-015, FR-017 |
| US7 | P2 | Synthetic-data provisioner + teardown | FR-011, FR-012 |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, directory structure, packaging, and shared configuration files.

- [ ] T001 Create directory structure per plan.md project structure tree: `scanner/lib/scanner/`, `narrator/mcp_server/tools/`, `tests/scanner/fixtures/`, `tests/narrator/fixtures/`, `assessments/`, `specs/001-modeling-readiness-assessor/contracts/`
- [ ] T002 Create `scanner/lib/scanner/pyproject.toml` — Python 3.11 package `modeling-readiness-scanner` with dependencies: `rapidfuzz`, `pyyaml`; no `azure-*` or `sempy` deps (Fabric runtime provides those)
- [ ] T003 [P] Create `narrator/mcp_server/pyproject.toml` — Python 3.11 package `modeling-readiness-narrator` with dependencies: `fastmcp`, `msal`, `azure-storage-file-datalake`, `pyyaml`
- [ ] T004 [P] Create root `pyproject.toml` test config with `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `addopts = "--cov=scanner/lib/scanner --cov=narrator/mcp_server --cov-report=term-missing --cov-fail-under=80"`
- [ ] T005 [P] Create `.gitignore` — include `assessments/`, `.narrator-token-cache`, `__pycache__/`, `*.egg-info/`, `.pytest_cache/`, `htmlcov/`, `dist/`
- [ ] T006 [P] Create `narrator.config.yaml` starter in repo root per `contracts/narrator-config.md` schema with all fields at defaults (`workspace_url: ""`, `token_cache: false`, `similarity_threshold: 0.85`, `demo_workspace: false`)
- [ ] T007 Create `scoring-rubric.yaml` in repo root per `contracts/narrator-config.md` schema: `schema_version: "1.0"`, thresholds 0→4, 1-2→3, 3-5→2, 6-10→1, 11+→0 for all four disciplines
- [ ] T008 [P] Create `scanner/lib/scanner/entity-synonyms.yaml` — synonym seed: Customer↔Account, Product↔Material, Vendor↔Supplier, Order↔Invoice, Asset↔Site

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared data types and scoring infrastructure required by ALL user stories. No user story work can begin until this phase is complete.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T009 Create `scanner/lib/scanner/findings.py` — Python dataclasses for all entities in `data-model.md`: `Finding`, `SourceArtifactRef`, `MaturityScore`, `CanonicalEntityConflict`, `Disagreement`, `SourceAttributionGap`, `EntityDefinition`, `SemanticModel`, `Table`, `Relationship`, `Measure`, `Ontology`, `EntityType`, `OntologyProperty`, `DataBinding`, `ScanScope`, `RunSummary`
- [ ] T010 [P] Create `scanner/lib/scanner/scoring.py` — load `scoring-rubric.yaml` at runtime; `compute_score(discipline, finding_count, rubric) -> MaturityScore`; raise `RuntimeError` if rubric file is missing or `schema_version` is unrecognized; handle `"assessed"`, `"partially_assessed"`, `"not_assessed"` status
- [ ] T011 Write `tests/scanner/test_scoring.py` — test all threshold bands (0, 1, 2, 3, 5, 6, 10, 11 findings), test `not_assessed` for Layered Modeling and Steward-Loop Modeling when no signals, test `RuntimeError` on missing rubric, test `RuntimeError` on unknown schema_version; tests MUST FAIL before T010 is implemented
- [ ] T012 [P] Create `scanner/lib/scanner/artifact.py` — `FindingsArtifactWriter`: write `manifest.json`, `findings.json`, and `raw/` subfolder to a local path; enforce `schema_version: "1.0"`; generate `run_id` as `YYYYMMDD-HHmmss-<4-char-hex>`; per `contracts/findings-artifact.schema.md`
- [ ] T013 Write `tests/scanner/test_artifact.py` — test manifest structure (all required fields present), test `run_id` format regex, test `findings.json` schema_version matches manifest, test `raw/` subfolder is created; tests MUST FAIL before T012 is implemented

**Checkpoint**: Foundational phase complete — all user stories can now begin.

---

## Phase 3: User Story 1 — Scanner Core: Enumerate & Write (Priority: P1) 🎯 MVP

**Goal**: Scanner notebook enumerates Power BI semantic models and Fabric IQ ontologies in a Fabric workspace and writes a valid findings artifact to OneLake. No analysis yet — just enumeration and artifact write.

**Independent Test**: Import `modeling-readiness-scanner.ipynb` into a Fabric workspace, run all cells, verify a `Files/modeling-readiness/<run-id>/` folder appears in OneLake containing `manifest.json`, `findings.json`, and `raw/` subfolder.

### Tests for User Story 1

> **Write these tests FIRST — they MUST FAIL before T016–T017 are implemented**

- [ ] T014 [US1] Write `tests/scanner/test_semantic_models.py` — load fixture JSON from `tests/scanner/fixtures/power_bi_rest_responses/`; test `SemanticModel` extraction: table count, relationship list, measure names, primary key columns, source columns; test graceful handling of models with no declared primary keys
- [ ] T015 [P] [US1] Write `tests/scanner/test_ontologies.py` — load fixture JSON from `tests/scanner/fixtures/fabric_iq_responses/`; test `Ontology` extraction: entity type count, property list, `is_source_attribution` classification, DataBinding `has_temporal_source_marker` field; test graceful degradation when ontology API returns 404 (preview feature absent)

### Implementation for User Story 1

- [ ] T016 [US1] Create `scanner/lib/scanner/semantic_models.py` — `extract_semantic_models(workspace_id, token_fn) -> list[SemanticModel]`; uses Power BI REST API (`GET /datasets`, `GET /datasets/{id}/tables`, `GET /datasets/{id}/relationships`, `GET /datasets/{id}/measures`) via `notebookutils.credentials.getToken("pbi")`; writes raw responses to `raw/semantic_models/<model-id>.json`
- [ ] T017 [P] [US1] Create `scanner/lib/scanner/ontologies.py` — `extract_ontologies(workspace_id, token_fn) -> list[Ontology]`; uses Fabric IQ REST API (preview) via `notebookutils.credentials.getToken("fabric")`; wraps all calls in try/except and marks failed scopes as `"not_assessed"` per NFR-003; writes raw responses to `raw/ontologies/<ontology-id>.json`
- [ ] T018 [US1] Generate synthetic fixture data in `tests/scanner/fixtures/` — `power_bi_rest_responses/` with 3 semantic model API responses (CRM-Sales, ERP-Finance, Invoicing-Legacy), `fabric_iq_responses/` with 1 ontology API response; model the Contoso mid-market manufacturer scenario with Customer + Product entities exhibiting deliberate naming inconsistencies across the 3 models
- [ ] T019 [US1] Create `scanner/modeling-readiness-scanner.ipynb` — Python Fabric notebook (NOT PySpark); cells: (1) imports + load config, (2) FR-013 preview-feature dependency check with user warning if Fabric IQ absent, (3) enumerate semantic models → call T016, (4) enumerate ontologies → call T017, (5) placeholder cells for CEM (wired in T023) and FLL (wired in T026), (6) compute maturity scores, (7) write findings artifact via T012; human-readable progress printed in each cell's output

**Checkpoint**: Scanner notebook importable into Fabric, runnable, writes valid artifact to OneLake.

---

## Phase 4: User Story 2 — Canonical Entity Modeling Analysis (Priority: P1)

**Goal**: Scanner detects candidate canonical entity conflicts across semantic models and ontologies using 0.85 similarity threshold; surfaces specific disagreements per dimension.

**Independent Test**: Run scanner against Contoso fixture data; verify at least 2 canonical entity conflicts detected for Customer and Product entities, each with ≥1 Disagreement entry citing specific source artifacts.

### Tests for User Story 2

> **Write these tests FIRST — they MUST FAIL before T021 is implemented**

- [ ] T020 [US2] Write `tests/scanner/test_canonical_entity.py` — test `rapidfuzz.fuzz.ratio` matching at threshold 0.85 (match) and 0.84 (no match); test conflict assembly from 3 fixture models; test all 5 disagreement dimensions (`primary_key`, `join_logic`, `filter_context`, `measure_definition`, `source_columns`); test synonym seed matching (Customer↔Account); test `confirmed=False` on new conflicts; test config override of threshold

### Implementation for User Story 2

- [ ] T021 [US2] Create `scanner/lib/scanner/canonical_entity.py` — `detect_canonical_entity_conflicts(models, ontologies, synonyms, threshold) -> list[CanonicalEntityConflict]`; load synonym seed from `entity-synonyms.yaml`; use `rapidfuzz.fuzz.ratio` for name matching; compare all entity name pairs; assemble `CanonicalEntityConflict` with `Disagreement` entries for each of the 5 dimensions; set `confirmed=False` on all new conflicts
- [ ] T022 [US2] Extend `scanner/lib/scanner/canonical_entity.py` with `extract_entity_definition(model_or_ontology, entity_name) -> EntityDefinition` — extract `primary_key_columns`, `join_relationships`, `measure_names`, `source_columns`, and `confidence` score
- [ ] T023 [US2] Wire `canonical_entity.py` into `scanner/modeling-readiness-scanner.ipynb` CEM analysis cell (updates T019 notebook) — call `detect_canonical_entity_conflicts`, append findings to artifact, print per-entity conflict summary to cell output

**Checkpoint**: Scanner detects CEM conflicts; findings.json contains `"discipline": "canonical_entity_modeling"` entries with source citations.

---

## Phase 5: User Story 3 — Field-Level Lineage Analysis (Priority: P1)

**Goal**: Scanner audits Fabric IQ ontology entity types for source-attribution property gaps; produces Field-Level Lineage findings and maturity score.

**Independent Test**: Run scanner against Contoso fixture ontology (zero source-attribution properties); verify `SourceAttributionGap` findings for all entity types, maturity score 0 for Field-Level Lineage.

### Tests for User Story 3

> **Write these tests FIRST — they MUST FAIL before T025 is implemented**

- [ ] T024 [US3] Write `tests/scanner/test_field_lineage.py` — test gap detection when all attribution types absent; test partial gap (some attribution types present, some missing); test entity type with full attribution scores as no gap; test that property name matching does NOT prescribe specific names (Framework principle — checks semantics, not exact names); test temporal marker detection in DataBinding

### Implementation for User Story 3

- [ ] T025 [US3] Create `scanner/lib/scanner/field_lineage.py` — `audit_field_level_lineage(ontologies) -> list[SourceAttributionGap]`; for each `EntityType`, check presence of: source-system identifier, source-record identifier, extraction-timestamp, confidence score (semantic check on `is_source_attribution` flag — no prescribed property names); check `DataBinding.has_temporal_source_marker`; produce one `SourceAttributionGap` per entity type with gaps
- [ ] T026 [US3] Wire `field_lineage.py` into `scanner/modeling-readiness-scanner.ipynb` FLL analysis cell (updates T019 notebook) — call `audit_field_level_lineage`, append findings to artifact, print per-ontology attribution coverage summary to cell output

**Checkpoint**: Scanner produces FLL findings; findings.json contains `"discipline": "field_level_lineage"` entries with source citations.

---

## Phase 6: User Story 4 — Narrator MCP Server (Priority: P1)

**Goal**: Narrator MCP server authenticates to OneLake via MSAL device code, resolves workspace URL to OneLake path, and exposes all 6 MCP tools that read exclusively from the findings artifact.

**Independent Test**: Register server with VS Code + GitHub Copilot, paste a workspace URL into chat, verify `list_runs` returns at least one run, `load_run` returns maturity scores, `extract_entity_definitions` returns conflicts, `audit_source_attribution` returns gaps — all without calling any Fabric or Power BI APIs.

### Tests for User Story 4

> **Write these tests FIRST — they MUST FAIL before T030–T039 are implemented**

- [ ] T027 [US4] Write `tests/narrator/test_artifact_reader.py` — test forward-tolerant read of v1.0 artifact (all known fields parsed); test artifact with unknown top-level keys (marked, not errored); test artifact missing a required field (RuntimeError / refuse); test schema_version 1.0 full parse; generate `tests/narrator/fixtures/manifest.json` and `tests/narrator/fixtures/findings.json` from synthetic scenario
- [ ] T028 [P] [US4] Write `tests/narrator/test_auth.py` — mock MSAL `acquire_token_by_device_flow`; test token returned to caller; test `token_cache: false` (no file written); test `token_cache: true` (`.narrator-token-cache` file created); test `SerializableTokenCache` round-trip
- [ ] T029 [P] [US4] Write `tests/narrator/test_onelake.py` — test `https://app.fabric.microsoft.com/groups/<uuid>/...` → `abfss://<workspace-id>@onelake.dfs.fabric.microsoft.com/` path resolution; test `abfss://` direct path passthrough; test workspace URL written to `narrator.config.yaml` cache after first successful resolution

### Implementation for User Story 4

- [ ] T030 [US4] Create `narrator/mcp_server/auth.py` — `get_token() -> str`; `msal.PublicClientApplication` device code flow; check `narrator.config.yaml` `token_cache` setting; if enabled, serialize/deserialize `msal.SerializableTokenCache` from `.narrator-token-cache` in repo root; scope: `https://storage.azure.com/user_impersonation`
- [ ] T031 [P] [US4] Create `narrator/mcp_server/onelake.py` — `resolve_workspace_url(url_or_abfss: str) -> str`; parse Fabric workspace URL to `abfss://` OneLake path; pass through `abfss://` paths unchanged; cache resolved workspace URL to `narrator.config.yaml` `workspace_url` field on first success
- [ ] T032 [US4] Create `narrator/mcp_server/artifact_reader.py` — `ArtifactReader`: uses `azure-storage-file-datalake` `DataLakeServiceClient` with bearer token from `auth.py`; reads `manifest.json` + `findings.json` from `Files/modeling-readiness/<run-id>/`; forward-tolerant: records unknown top-level keys in `unknown_fields` list; raises on missing required fields per schema v1.0; reads `raw/` subfolder entries as bytes
- [ ] T033 [US4] Create `narrator/mcp_server/tools/list_runs.py` — `list_runs(workspace_url: str)` MCP tool; uses `ArtifactReader` to enumerate `Files/modeling-readiness/` directories; returns `RunSummary` list sorted descending by `run_id`; sets `selected_run_id` to most recent; includes `"note"` field when N > 1 runs; per `contracts/mcp-tools.md`
- [ ] T034 [P] [US4] Create `narrator/mcp_server/tools/load_run.py` — `load_run(run_id: str, workspace_url: str)` MCP tool; returns full manifest + maturity_scores + unknown_fields; per `contracts/mcp-tools.md`
- [ ] T035 [P] [US4] Create `narrator/mcp_server/tools/list_semantic_models.py` — `list_semantic_models(run_id: str, workspace_url: str)` MCP tool; reads `raw/semantic_models/` entries from artifact; returns model summaries with table/measure/relationship counts; per `contracts/mcp-tools.md`
- [ ] T036 [P] [US4] Create `narrator/mcp_server/tools/extract_entity_definitions.py` — `extract_entity_definitions(run_id: str, workspace_url: str, entity_name: str | None)` MCP tool; returns `entity_definitions` and `conflicts` (with `confirmed` flag); supports optional `entity_name` filter; per `contracts/mcp-tools.md`
- [ ] T037 [P] [US4] Create `narrator/mcp_server/tools/audit_source_attribution.py` — `audit_source_attribution(run_id: str, workspace_url: str, entity_type_name: str | None)` MCP tool; returns `gaps` list + `total_entity_types_assessed` + `entity_types_with_full_attribution`; per `contracts/mcp-tools.md`
- [ ] T038 [P] [US4] Create `narrator/mcp_server/tools/enumerate_ontologies.py` — `enumerate_ontologies(run_id: str, workspace_url: str)` MCP tool; returns ontology summaries with attribution coverage counts; per `contracts/mcp-tools.md`
- [ ] T039 [US4] Create `narrator/mcp_server/server.py` — `fastmcp` server; wire all 6 tools with `@mcp.tool()` decorator; load `narrator.config.yaml` on startup; validate `similarity_threshold` in `[0.5, 1.0]` (reject outside range with error message); return consistent error envelope per `contracts/mcp-tools.md` on all tool failures; `AUTH_REQUIRED` error when token expired
- [ ] T040 [US4] Write `tests/narrator/test_tools.py` — integration tests for all 6 MCP tools against `tests/narrator/fixtures/` artifact; test `list_runs` selects most recent run; test `load_run` unknown_fields for future-schema fixture; test `audit_source_attribution` gap counts against fixture; tests MUST FAIL before T033–T038 are implemented

**Checkpoint**: MCP server starts, registers with VS Code + Copilot, all 6 tools return correct JSON from fixture artifact without any live Fabric calls.

---

## Phase 7: User Story 5 — Deliverables, Scan Plan & Scope Honesty (Priority: P1)

**Goal**: Agent presents a scan plan before executing; generates 4 Markdown deliverable files in a timestamped folder; all output uses exact canonical discipline names; partially/not-assessed disciplines are explicitly marked.

**Independent Test**: In VS Code + Copilot with MCP server running against fixture artifact, ask agent to generate deliverables; verify 4 files appear in `assessments/<timestamp>/`; verify all 4 use exact discipline names; verify Layered Modeling and Steward-Loop Modeling are marked "not assessed in this version."

- [ ] T041 [US5] Create `assessments/` directory with `.gitkeep` (directory committed but contents gitignored)
- [ ] T042 [P] [US5] Create deliverable templates in `templates/` — `executive-summary.md.jinja`, `findings-detail.md.jinja`, `remediation-plan.md.jinja`, `workshop-agenda.md.jinja`; each template includes: exact four discipline name placeholders, source citation placeholders (`{{ artifact_id }}`), "assessed / partially assessed / not assessed in this version" status sections; vocabulary: zero abbreviations, zero informal variants
- [ ] T043 [US5] Create `narrator/mcp_server/deliverables.py` — `generate_deliverables(run_data, output_dir) -> list[Path]`; renders 4 Jinja templates with findings data; writes to `assessments/<YYYY-MM-DD>-<workspace-name>/`; every finding rendered with `source_artifacts` citations
- [ ] T044 [US5] Update `.github/agents/` persona/instruction files — add FR-002 scan plan behavior (present scan plan naming all 4 disciplines and assessment status before running any tool); add FR-009 deliverable generation trigger; add FR-014 vocabulary enforcement rule (exact discipline names in all output); add FR-013 preview-feature warning surfacing in conversation

**Checkpoint**: Complete end-to-end narration flow: workspace URL → scan plan → findings in chat → 4 deliverable files.

---

## Phase 8: User Story 6 — Bootstrap & Multi-Host Registration (Priority: P2)

**Goal**: Single bootstrap step (PowerShell or bash) installs narrator dependencies and registers MCP server with all detected AI hosts; no admin required; prints summary.

**Independent Test**: Run `./bootstrap.ps1` on a machine with VS Code installed; verify `narrator/mcp_server/` deps are installed; verify `.vscode/mcp.json` is present and correctly points to the narrator MCP server; verify no admin elevation occurred.

- [ ] T045 [US6] Create `bootstrap.ps1` (Windows, PowerShell 5.1+) — (1) install narrator Python deps via `pip install -e narrator/mcp_server/`; (2) probe `~/.vscode/` (VS Code), `~/.claude/` (Claude Code), `~/.cursor/` (Cursor); (3) for each detected host write host-specific MCP registration JSON to repo root (`.vscode/mcp.json`, `claude_mcp_config.json`, `.cursor/mcp.json`); (4) print summary table of configured/not-detected hosts; no admin; no global state outside repo and host config files
- [ ] T046 [P] [US6] Create `bootstrap.sh` (macOS/Linux bash) — same logic as T045 adapted for bash; probe same config dirs; write same MCP registration files; print summary
- [ ] T047 [US6] Create `.vscode/mcp.json` — MCP server registration for VS Code + GitHub Copilot: `{"servers": {"modeling-readiness-narrator": {"command": "python", "args": ["-m", "narrator.mcp_server.server"], "cwd": "${workspaceFolder}"}}}`; per FR-017
- [ ] T048 [P] [US6] Create `claude_mcp_config.json` and `.cursor/mcp.json` registration file stubs for Claude Code and Cursor, using same server command pattern as T047

**Checkpoint**: `./bootstrap.ps1` or `./bootstrap.sh` runs clean, all detected hosts configured, no admin prompt.

---

## Phase 9: User Story 7 — Synthetic-Data Provisioner (Priority: P2)

**Goal**: Fabric notebook creates a reproducible demo workspace (3 source system semantic models, 1 ontology, OneLake tables) with deliberate modeling debt across CEM and FLL disciplines; idempotent; teardown notebook reverses it.

**Independent Test**: Set `demo_workspace: true` in `narrator.config.yaml`, import + run `provisioner.ipynb` in a blank Fabric workspace, then import + run `modeling-readiness-scanner.ipynb`; verify CEM score ≤ 2 and FLL score ≤ 1, and at least 1 entity scores well (positive example in findings).

- [ ] T049 [US7] Create `scanner/provisioner.ipynb` — Python Fabric notebook cells: (1) read `narrator.config.yaml`, abort if `demo_workspace: false` with clear error; (2) explicit user confirmation cell (`input("Type 'yes' to proceed...")`) before any creation; (3) create or verify-already-exists 3 semantic models: `CRM-Sales` (Customer entity, primary key `CustomerGUID`), `ERP-Finance` (Account entity = same Customer, primary key `AccountNumber`), `Invoicing-Legacy` (Customer entity, primary key `InvoiceCustomerID`); (4) create Fabric IQ ontology `Manufacturing-Ontology` with Customer + Product entity types, zero source-attribution properties; (5) create OneLake tables and sample Data Agent config; (6) create `Vendor` entity well-modeled in all assessed disciplines (positive example per FR-011d); idempotent: check resource existence before creating, skip if already present
- [ ] T050 [US7] Create `scanner/provisioner-teardown.ipynb` — Python Fabric notebook: (1) verify `demo_workspace: true` gate; (2) explicit confirmation cell before deletion; (3) delete only artifacts provisioner created (by name convention); (4) idempotent: skip missing resources; (5) print teardown summary per resource type removed

**Checkpoint**: Provisioner notebook creates demo workspace with meaningful debt; scanner run against it produces maturity scores matching FR-011 acceptance criteria.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Verification, vocabulary compliance, performance instrumentation, and documentation.

- [ ] T051 Run `pytest --cov=scanner/lib/scanner --cov=narrator/mcp_server --cov-fail-under=80` — verify ≥80% unit test coverage on deterministic modules (NFR-005); fix any gaps before closing this task
- [ ] T052 [P] Vocabulary review — `grep -rn` across all source files (`*.py`), notebooks (`*.ipynb`), templates (`templates/`), agent files (`.github/agents/`, `.github/prompts/`), and `docs/` for discipline name drift; check for any of the 8 forbidden variants (ECM, FLL, Layered, Extension, Steward, Closed Loop, SLM, Feedback); fix all regressions
- [ ] T053 [P] Add NFR-001 performance instrumentation to `scanner/modeling-readiness-scanner.ipynb` — wall-clock timing per scan phase using `time.perf_counter()`; print warning to cell output if any phase exceeds 60 seconds (budget alert, not hard stop); print total elapsed time in final cell
- [ ] T054 [P] Update `README.md` — add quickstart link to `specs/001-modeling-readiness-assessor/quickstart.md`, bootstrap instructions, scanner import instructions, supported AI host table, and `.narrator-token-cache` documentation (per FR-001 opt-in token cache contract)
- [ ] T055 Run end-to-end validation using `specs/001-modeling-readiness-assessor/quickstart.md` against `tests/narrator/fixtures/` synthetic artifact — verify all steps execute without live Fabric; verify 4 deliverable files are written to `assessments/`; verify vocabulary in output (zero regressions)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1–US3 (Phases 3–5)**: All depend on Foundational; US2 and US3 depend on US1 (scanner notebook wiring); US2 and US3 can run in parallel with each other
- **US4 (Phase 6)**: Depends on Foundational; independent of US1–US3 (reads from fixture artifact during development); integrates with US1–US3 artifact schema
- **US5 (Phase 7)**: Depends on US4 (MCP tools) and US1–US3 (findings data in artifact)
- **US6 (Phase 8)**: Depends on US4 (MCP server exists to register); can parallelize with US5
- **US7 (Phase 9)**: Depends on US1–US3 (scanner notebook must be complete to validate provisioner output)
- **Polish (Phase 10)**: Depends on all user stories complete

### User Story Dependencies

```
Phase 1 (Setup)
  └─► Phase 2 (Foundational)
        ├─► US1 (scanner enumerate)
        │     ├─► US2 (CEM, wires into US1 notebook)
        │     └─► US3 (FLL, wires into US1 notebook)
        │           └─► US7 (provisioner, validated against complete scanner)
        └─► US4 (narrator MCP — parallel to US1–US3)
              └─► US5 (deliverables, depends on US4 tools)
                    └─► US6 (bootstrap, registers US4 server)
```

### Within Each User Story

- Test tasks MUST be written and FAIL before corresponding implementation tasks begin
- Foundational data types (T009) before scanner extraction modules (T016–T017)
- `artifact.py` (T012) before scanner notebook (T019)
- `auth.py` (T030) and `onelake.py` (T031) before `artifact_reader.py` (T032)
- `artifact_reader.py` (T032) before all MCP tools (T033–T038)
- MCP tools (T033–T038) before server wiring (T039)

---

## Parallel Opportunities

### Phase 1 (all parallel after T001)

```
T001 → T002, T003, T004, T005, T006, T007, T008 (all in parallel)
```

### Phase 2

```
T009 → T010, T012 (in parallel)
T010 → T011 (test)
T012 → T013 (test)
```

### US1 (Phase 3)

```
T014, T015, T018 (parallel — fixture data + tests)
T014 → T016
T015 → T017
T016, T017 → T019 (notebook wiring)
```

### US4 (Phase 6)

```
T027, T028, T029 (tests in parallel)
T030, T031 (auth + onelake in parallel)
T030, T031 → T032 (artifact reader)
T032 → T033–T038 (all 6 tools in parallel)
T033–T038 → T039 (server wiring)
T039 → T040 (integration tests)
```

---

## Implementation Strategy

### MVP (US1 + US2 + US4 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete US1: Scanner enumerates and writes artifact
4. Complete US2: CEM analysis wired into scanner
5. Complete US4: Narrator MCP server reads artifact, 6 tools functional
6. **STOP AND VALIDATE**: Scanner → artifact → narrator → CEM findings in chat
7. This is the minimum viable loop that demonstrates diagnostic determinism end-to-end

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → Scanner writes valid artifact → validate with quickstart Step 1
3. US2 → CEM findings in artifact → validate in chat via US4
4. US3 → FLL findings in artifact → validate in chat
5. US5 → Full deliverables generated → validate 4 files
6. US6 → Bootstrap works cold → validate 15-min bar (NFR-004)
7. US7 → Provisioner creates demo workspace → demo-ready
8. Polish → vocabulary review, coverage, perf instrumentation

### Parallel Team Strategy

With 2+ developers after Foundational is complete:
- **Developer A**: US1 → US2 → US3 (scanner stack)
- **Developer B**: US4 → US5 (narrator MCP stack, uses fixture artifact)
- **Developer C**: US6 + US7 (bootstrap + provisioner, depends on scanner complete)

---

## Notes

- `[P]` tasks target different files with no incomplete-task dependencies — safe to parallelize
- `[Story]` label maps every implementation task to a specific user story for traceability
- Tests marked "MUST FAIL before implementation" enforce the constitution's TDD mandate for deterministic modules
- Every task that writes a Finding must include a `source_artifacts` list — no citations = not acceptable (FR-010)
- Never use discipline name abbreviations or variants in any file touched by these tasks (vocabulary review in T052 catches regressions)
- Commit after each phase checkpoint using the git extension (`/speckit.git.commit`)
