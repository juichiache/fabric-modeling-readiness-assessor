# Research: Modeling Readiness Assessor

**Branch**: `001-modeling-readiness-assessor` | **Date**: 2026-05-20

## 1. MCP Python SDK

**Decision**: Use `fastmcp` (wraps the `mcp` Python SDK)

**Rationale**: `fastmcp` exposes a stable `@mcp.tool()` decorator API that maps cleanly to the named MCP tools required by FR-016. It handles the MCP protocol (stdio transport for VS Code + Copilot; SSE transport for remote hosts) without requiring manual protocol wiring. The `mcp` SDK alone requires more boilerplate for tool registration. `fastmcp` is the de facto standard for Python MCP servers as of 2026.

**Alternatives considered**:
- Raw `mcp` SDK: more control, more boilerplate, same outcome — rejected for development velocity.
- TypeScript/Node MCP server: would create a Node.js runtime dependency on the user's machine, conflicting with the Python-only narrator stack and the OneLake read libraries.

## 2. OneLake Authentication & Read Access

**Decision**: `msal` `PublicClientApplication` with device code flow; `azure-storage-file-datalake` for blob/file reads; optional MSAL token cache serialized to `.narrator-token-cache` in repo root.

**Rationale**: 
- MSAL `PublicClientApplication.acquire_token_by_device_flow()` is the standard pattern for user-delegated device code; it requires no app secret and no redirect URI, which fits the narrator's constraint of no separate Entra app registration.
- `azure-storage-file-datalake` (`DataLakeServiceClient`) supports OneLake's ADLS Gen2 endpoint with a `BearerToken` credential; this is the officially supported path for OneLake programmatic read.
- The required OAuth scope is `https://storage.azure.com/user_impersonation` (OneLake uses Azure Storage endpoints), which is a low-privilege user-delegated scope — no admin consent required. This is the deliberate friction-reduction outcome of the two-component architecture.

**Alternatives considered**:
- Azure CLI passthrough: rejected — FR-001 and Session 1 clarification explicitly forbid requiring Azure CLI.
- Service principal / client secret: rejected — requires admin to register an Entra app, which contradicts the distribution model.
- `azure-identity` `DeviceCodeCredential`: functionally equivalent to MSAL direct; MSAL direct is preferred because it gives explicit control over the token cache serialization hook needed for the optional `.narrator-token-cache` feature.

## 3. Scanner: Semantic Model Extraction

**Decision**: Use `sempy.fabric` (Microsoft SemPy) REST wrappers inside the Fabric notebook, supplemented by direct Power BI REST API calls via `notebookutils.credentials.getToken("pbi")` for fields SemPy does not expose.

**Rationale**:
- `sempy.fabric.FabricRestClient` (or `sempy.fabric.PowerBIRestClient`) is the officially supported SDK for interacting with Power BI REST endpoints from inside a Fabric notebook under the delegated session identity. No separate auth required.
- SemPy exposes `list_datasets()`, `read_table()`, and `evaluate_dax()` that cover table and measure enumeration. TMSL/TMDL extraction for relationship and primary key details requires the Power BI REST API directly (`GET /datasets/{id}/relationships`, `GET /datasets/{id}/tables`).
- Both paths use the Fabric notebook's in-runtime identity — no new Entra registration.

**Alternatives considered**:
- `mssparkutils.credentials.getToken` + raw requests: works but bypasses SemPy's helpful retry/error handling.
- `azure-devops` or external SDK: not applicable to Power BI REST.

## 4. Scanner: Ontology Extraction

**Decision**: Fabric IQ REST API (preview) via `notebookutils.credentials.getToken("fabric")` + `requests` inside the notebook.

**Rationale**:
- Fabric IQ ontology endpoints are preview REST APIs accessible from inside a Fabric notebook with the delegated session token. No separate SDK exists yet; raw REST via `requests` with the bearer token is the only supported path.
- The scanner MUST tolerate API changes gracefully (NFR-003): all ontology API calls are wrapped in try/except with explicit "not assessed" fallback per FR-013.
- Raw JSON responses are written to `raw/ontologies/<ontology-id>.json` in the findings artifact so the narrator can re-derive findings without re-querying Fabric.

**Alternatives considered**:
- SemPy: does not expose Fabric IQ ontology endpoints as of 2026.
- Fabric SDK (preview): not yet stable enough for dependency pinning; `requests` + token is more portable across API surface changes.

## 5. Name Similarity Algorithm

**Decision**: Normalized Levenshtein ratio via `rapidfuzz.fuzz.ratio()`, with a synonym seed dictionary; default threshold 0.85 (config YAML overridable).

**Rationale**:
- Normalized Levenshtein handles abbreviation drift (e.g., `cust_master` vs. `Customer`) better than cosine similarity on raw strings, because cosine requires a shared vocabulary.
- `rapidfuzz` is a C-extension Levenshtein library that is 10–100× faster than pure-Python `difflib.SequenceMatcher`, important for comparing O(n²) entity name pairs across 50 models.
- The synonym seed list (Customer↔Account, Product↔Material, Vendor↔Supplier, etc.) is loaded from a YAML file in the repo so architects can extend it per-engagement.
- Threshold 0.85 was selected to minimize false positives on first use (constitution Principle I: fabricated findings are a credibility-ending failure mode).

**Alternatives considered**:
- Cosine similarity on TF-IDF vectors: requires a corpus large enough to produce meaningful IDF weights; not viable for 8–50 entity names.
- Exact match + synonym map only: too rigid for real-world naming drift; misses `cust_master` ↔ `Customer`.
- spaCy semantic similarity: too heavy a dependency for the scanner notebook runtime; adds significant cold-start time.

## 6. Bootstrap Host Detection

**Decision**: Probe known configuration file paths for each supported AI host; write MCP registration JSON/YAML to each found; print a summary table. No admin required.

**Rationale**:
- Auto-detecting all installed hosts (FR-015 as clarified) eliminates the need for the user to know which host they are "supposed to" use — aligns with the 15-minute cold-start bar (NFR-004).
- Probe paths are deterministic and well-known:
  - VS Code + GitHub Copilot: `~/.vscode/` presence + `<repo>/.vscode/mcp.json`
  - Claude Code: `~/.claude/` presence + `<repo>/claude_mcp_config.json`
  - Cursor: `~/.cursor/` presence + `<repo>/.cursor/mcp.json`
- MCP registration files are written to the **repo root** (inside the clone), not to global config paths, so the bootstrap does not touch state outside the clone and AI-host config files (FR-015 constraint).
- If a host's config directory does not exist, the host is not installed; the bootstrap silently skips it and notes "not detected."

**Alternatives considered**:
- Interactive prompt to select one host: rejected — increases friction, conflicts with NFR-004.
- Configure GitHub Copilot in VS Code only: rejected — spec explicitly requires surface-agnostic distribution (FR-017).

## 7. Scoring Rubric Format

**Decision**: YAML file (`scoring-rubric.yaml`) with a `schema_version` key and per-discipline threshold tables; loaded at runtime by `scoring.py`.

**Rationale**:
- YAML is human-readable and architect-reviewable (NFR-006 requires architect review before v1 ships).
- `schema_version` key enables forward compatibility: future rubric changes can be versioned without breaking older narrators reading older findings artifacts.
- `scoring.py` raises `RuntimeError` if the rubric file is missing or unparseable — prevents silent fallback to unspecified behavior, preserving diagnostic determinism (Principle I).
- Default thresholds: 0 findings = 4, 1–2 = 3, 3–5 = 2, 6–10 = 1, 11+ = 0 (per clarification Q3).

**Alternatives considered**:
- Hard-coded thresholds: not reviewable or adjustable without code changes; rejected.
- JSON schema: less readable for non-engineers; YAML is preferred for architect-facing config.
- Per-severity weighting: would require defining severity levels and weights — additional surface for miscalibration; deferred to v2.
