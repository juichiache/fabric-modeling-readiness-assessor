# Feature Specification: Modeling Readiness Assessor Agent

**Feature Branch**: `001-modeling-readiness-assessor`
**Status**: Draft
**Input**: A two-component system that helps a customer (guided by a
Microsoft architect) diagnose modeling readiness for Microsoft Fabric
IQ deployment in their own Fabric tenant.

  1. **Scanner** — a Fabric notebook the customer imports into their
     Fabric workspace and runs there. The notebook executes the
     deterministic Modeling Readiness scans against Fabric/Power BI APIs
     from inside the tenant under the running user's Fabric session
     identity (the standard Fabric notebook delegated context, exposed
     by the platform through `notebookutils` / `mssparkutils` and the
     in-runtime authenticated SDK clients), and writes a structured
     findings artifact (JSON plus raw evidence) to a namespaced
     OneLake folder in the assessed workspace.
  2. **Narrator** — a cloneable Git repository constituted by
     agent-customization files (skills, agent personas, instructions)
     and a Model Context Protocol (MCP) server. The narrator runs on
     the customer's machine inside any MCP-capable AI host the
     customer already has (GitHub Copilot in VS Code, Claude Code,
     Cursor, JetBrains AI, github.com chat with MCP, etc.). The MCP
     server's tools read the OneLake findings artifact written by the
     scanner and surface findings to the LLM-driven persona, which
     conducts the conversation and generates structured deliverables
     (executive summary, findings detail, remediation plan, workshop
     agenda) committed as files in the customer's clone of the
     repository.

The agent applies the Modeling Readiness Framework across four
disciplines (Canonical Entity Modeling, Field-Level Lineage, Layered
Modeling, Steward-Loop Modeling). The repository ships with a
synthetic-data provisioner that creates a demo workspace modeled on a
mid-market industrial manufacturer with deliberate modeling debt, so
demos and onboarding work without a real customer tenant.

## Clarifications

### Session 1 — resolved

- **Distribution surface**: RESOLVED — the agent ships as a cloneable
  Git repository, not as a GitHub Copilot extension or VS Code
  extension. The repository contains agent-customization files
  (`AGENTS.md`, skill files, prompt files) and an MCP server that
  exposes deterministic Fabric scanners as tools. Customers clone the
  repo and run it inside any MCP-capable AI host they already use
  (GitHub Copilot in VS Code is the documented happy path; Claude
  Code, Cursor, JetBrains AI, and github.com chat with MCP are
  supported as long as they honor the agent-customization files and
  MCP registrations in the repo). The customer-run distribution model
  drove this decision: marketplace install friction is unacceptable
  for data stewards and BI leads who are not VS Code-native, and
  surface-agnostic distribution lets architects guide customers
  regardless of the AI host the customer's organization has
  standardized on.
- **Authentication**: RESOLVED — Microsoft Entra ID device code flow
  only, brokered by MSAL. Azure CLI passthrough is NOT a requirement
  for customer users; the device code flow works on any machine with
  a browser and does not assume Azure CLI is installed or configured.
  Microsoft architects running the agent in their own dev loops MAY
  opt into an Azure CLI shortcut via an environment variable, but the
  shortcut MUST NOT be required by any user-facing flow or demo path.

### Session 2 — resolved

- **Synthetic source systems**: RESOLVED — the demo manufacturer
  uses three source systems: Dynamics 365 CRM (customer-facing system
  of record), SAP S/4HANA ERP (operations and finance system of
  record), and a homegrown invoicing application represented as a
  SQL database mirrored to OneLake (legacy system with no governance
  discipline, the natural home for the most pedagogically useful
  modeling debt). This combination is representative of real
  mid-market industrial manufacturers, exercises cross-vendor
  reconciliation scenarios (Microsoft vs. SAP vs. homegrown), and
  lets the synthetic Customer/Product entities collide in plausible
  ways across the three sources. The synthetic semantic models MUST
  use table and column naming conventions consistent with each
  source system's real conventions so that architects demoing the
  scenario can answer "is this representative of what we'd see?" in
  the affirmative.

### Session 3 — resolved

- **Onboarding friction architecture**: RESOLVED — the agent splits into
  a scanner (Fabric notebook running inside the customer's workspace
  under workspace identity) and a narrator (cloneable repo with MCP
  server running on the customer's machine, reading the scanner's
  OneLake findings artifact). This pivot eliminates the customer-side
  Entra admin-consent burden for broad Fabric and Power BI scopes:
  the scanner uses the customer's existing Fabric workspace identity
  with no new app registration, and the narrator only needs OneLake
  read scope on the namespaced findings folder. Lever explicitly
  chosen over (a) a pure-notebook variant that would abandon the
  conversational UX, and (b) a first-party Fabric workload, which
  remains the v3 destination once Fabric's MCP/agent hosting story
  matures.

### Session 4 — resolved

- **Synthetic-data provisioner location**: RESOLVED — the provisioner
  is also a Fabric notebook (or set of notebooks), imported by the
  architect into a designated demo tenant and run there under the
  same delegated-Fabric-session-identity auth model as the scanner.
  Rejected alternatives: a CLI provisioner with a separate Entra app
  registration (would introduce a third auth path the constitution
  must defend), and a CLI with broader device-code scopes
  (contradicts FR-020). The provisioner is therefore an
  architect-facing demo tool, runnable only by users who have
  workspace-admin permissions on a tenant they have explicitly
  designated as a demo tenant via repository configuration.

- **Scanner notebook runtime**: RESOLVED — the scanner is a Python
  Fabric notebook, NOT a PySpark notebook. The scans walk metadata
  (semantic-model TMSL/TMDL, ontology JSON, lakehouse table
  schemas), which is not a data-volume problem and does not benefit
  from Spark. Python notebooks have substantially faster cold start,
  fit the NFR-001 5-minute budget more comfortably, and avoid
  unnecessary capacity consumption on the customer's Fabric tenant.

- **Narrator workspace scoping**: RESOLVED — primary user gesture is
  to paste a Fabric workspace URL into the chat; the narrator infers
  the OneLake findings folder path from the workspace URL and lists
  available runs. The repository configuration file caches the
  most-recently-used workspace URL so subsequent assessments can
  proceed without re-pasting. Direct OneLake / `abfss://` paths are
  also accepted as a fallback for advanced users.

- **Multi-run handling**: RESOLVED — when the narrator opens a
  workspace with multiple findings runs, it selects the most recent
  run by default (run-ids are timestamp-sortable), narrates from it,
  and surfaces a one-line note that prior runs are available and
  comparison is supported on request. This default is non-blocking
  for first-time users and leaves room for trend-analysis features
  in future versions without re-architecting the artifact contract.

- **Schema version skew**: RESOLVED — the narrator is
  forward-tolerant: when it encounters an artifact written by a
  newer scanner schema than it knows, it reads what it understands,
  marks unknown sections or fields as "produced by a newer scanner;
  not interpreted in this version" in deliverables, and proceeds.
  This matches Principle II's scope-honesty discipline and prevents
  scanner-side improvements from breaking older narrator clones.
  Strict refusal on version mismatch is rejected because it creates
  artificial coupling that the customer-run distribution model can't
  sustain across drift in clone freshness.

### Session 2026-05-20

- Q: What is the default name-similarity threshold for candidate canonical entity conflict detection, and how should it be configurable? → A: 0.85 default (cosine similarity or equivalent normalized Levenshtein ratio), user-overridable via a repo configuration YAML file. High default minimizes false positives on first use; architects can lower it for tenants using abbreviated naming conventions.
- Q: What does the narrator token cache opt-in look like, and where does the cache file live? → A: `token_cache: enabled` in repo config YAML; cache written to `.narrator-token-cache` in the repo root, gitignored by default, documented in the README for user auditability.
- Q: How are maturity scores derived deterministically from findings? → A: Findings-count threshold table in a versioned scoring rubric YAML shipped in the repo (0 = 4, 1–2 = 3, 3–5 = 2, 6–10 = 1, 11+ = 0); human-readable and architect-reviewable before v1 ships.
- Q: How does the bootstrap handle multiple installed AI hosts and missing host config files? → A: Auto-detect all supported installed hosts, configure each silently (creating the host config file if absent), print a summary of what was configured. Minimum friction; aligns with the 15-minute cold-start bar.
- Q: When the provisioner finds a workspace name collision, does it fail or auto-suffix? → A: Fail clearly with a human-readable error and remediation suggestion pointing to the teardown notebook. Consistent workspace naming is required for pedagogical value; auto-suffixing is rejected.

## User Scenarios & Testing

### Primary user story
A Microsoft principal architect is preparing a strategic customer to
deploy Fabric IQ and Data Agent on top of Fabric. Rather than running
the assessment on the customer's behalf, the architect points the
customer's data lead at the Modeling Readiness Assessor repository.
The data lead opens the assessor's scanner notebook in the customer's
target Fabric workspace and runs it; the notebook scans the workspace
under the customer's own Fabric workspace identity and writes a
findings artifact to OneLake. The data lead then clones the
assessor repository on their own machine, opens it in whatever AI host
their organization uses (typically GitHub Copilot in VS Code), signs
into OneLake via Entra device code (read-only on the findings folder),
and asks the agent for a Modeling Readiness assessment. Within a few
minutes, the customer has an executive summary scoring their
environment against the four disciplines, a detailed findings list
with traceable sources, a prioritized remediation plan, and a
structured workshop agenda — all as files committed to their local
clone of the repository. The customer brings those files into the
workshop with the architect. Because the customer ran both components
themselves against their own tenant, no Microsoft personnel needed
customer-tenant credentials, no new Entra app registration was
required, and the customer sees exactly what the agent saw.

### Acceptance scenarios

1. **Given** the user has imported and run the scanner notebook in a
   Fabric workspace they have access to, producing a findings artifact
   in OneLake, **And** they have cloned the repository, started their
   AI host, and completed Entra device code sign-in for OneLake read
   access on that workspace, **When** they ask the agent to run a
   Modeling Readiness assessment, **Then** the agent (via MCP tool
   calls into the OneLake findings artifact) reports the inventory the
   scanner observed (semantic models, ontologies), the run timestamp,
   and offers to drill into specific findings under each of the four
   disciplines.

2. **Given** the workspace contains multiple semantic models defining a
   business entity (e.g., Customer, Product, Vendor), **When** the agent
   completes the Canonical Entity Modeling scan, **Then** it surfaces
   (a) the count of models defining the entity, (b) the specific points
   of disagreement between definitions (different primary keys, different
   join logic to related entities, different filter contexts, different
   measure definitions), and (c) a Canonical Entity Modeling maturity
   score with a one-sentence rationale citing specific findings.

3. **Given** the workspace contains one or more Fabric IQ ontologies,
   **When** the agent completes the Field-Level Lineage scan, **Then**
   it reports which entity types lack source-attribution properties,
   which bindings do not track source-system identifiers, which time-
   series bindings lack temporal-source markers, and a Field-Level
   Lineage maturity score with rationale citing specific entity types.

4. **Given** the workspace contains observable signals about Layered
   Modeling or Steward-Loop Modeling (multiple workspaces with shared
   ontology dependencies; rules and actions wired to user input), **When**
   the agent completes its scan, **Then** it scores those disciplines
   with a rationale. **Given** such signals are absent, **Then** the
   agent marks those disciplines as "not assessed in this version" with
   a brief explanation, and does NOT fabricate scores.

5. **Given** the user has reviewed the in-chat findings, **When**
   they ask the agent to generate the deliverables, **Then** the agent
   writes four files into a timestamped folder in the user's local
   clone of the repository (e.g., `assessments/2026-05-20-acme/`):
   an executive summary, a detailed findings document, a remediation
   plan, and a workshop agenda. Each file MUST cite specific source
   artifacts for every finding, MUST use the four discipline names
   exactly, and MUST distinguish between "assessed" and "not assessed
   in this version" disciplines. The files are plain Markdown so they
   can be committed, diffed across runs, and shared via the customer's
   normal Git workflow.

6. **Given** the user has no real Fabric tenant available or wants to
   try the agent before pointing it at production data, **When** they
   import the synthetic-data provisioner notebook into a Fabric
   workspace they have explicitly designated as a demo tenant via
   repo configuration and run it, **Then** the provisioner notebook
   creates the supporting artifacts (semantic models, ontology,
   OneLake tables, and a sample Data Agent configuration) modeled on
   a mid-market industrial manufacturer with three source systems
   and deliberate modeling failures across all four disciplines.
   **And** a subsequent run of the scanner notebook plus a narrator
   pass produces meaningful findings under at least Canonical Entity
   Modeling and Field-Level Lineage.

7. **Given** the agent encounters a Fabric API error, an unsupported
   artifact type, or a feature it cannot assess, **When** it reports
   findings, **Then** it MUST mark the affected scope as "not assessed"
   with the reason, and MUST NOT fabricate or infer findings for that
   scope.

### Edge cases

- The workspace is empty or contains only items the agent does not
  analyze (notebooks, pipelines, dashboards). The agent reports the
  workspace inventory and explains that no Modeling Readiness-assessable
  artifacts were found.

- The user lacks read permission for some artifacts. The agent reports
  which artifacts were skipped due to permissions and proceeds with the
  rest, marking the missed scope explicitly.

- The same logical entity is named inconsistently across models
  (Customer vs. customers vs. cust_master vs. Account). The agent uses
  fuzzy matching with a confidence threshold, surfaces near-matches as
  "candidate canonical entity conflicts" rather than confirmed ones, and
  asks the user to confirm before scoring them.

- Two semantic models define an entity with identical schemas. The agent
  reports them as consistent and does NOT score this as a Canonical
  Entity Modeling debt finding. (False positives erode Framework trust.)

- The customer's tenant has Fabric IQ ontologies but no semantic models,
  or vice versa. The agent assesses what's present and reports what's
  absent, scoping its scoring accordingly.

- The synthetic-data provisioner is run against a tenant that already
  has workspaces matching its target names. The provisioner MUST fail
  clearly with a human-readable error and a remediation suggestion
  (e.g., "A workspace named 'Contoso-CRM' already exists. Run the
  teardown notebook to remove previously provisioned artifacts, or
  update the demo workspace name in repo configuration."). The
  provisioner MUST NOT auto-suffix workspace names; consistent naming
  is required for pedagogical value in architect-led demos. The
  teardown notebook (FR-012) is the canonical reset path.

- A customer's ontology was generated automatically from a Power BI
  semantic model with known modeling debt. The agent surfaces this
  inheritance pattern explicitly under Canonical Entity Modeling, since
  it's the most common failure mode in production Fabric IQ deployments.

## Requirements

### Functional requirements

- **FR-001**: The narrator MUST authenticate to OneLake using Microsoft
  Entra ID device code flow, brokered by MSAL inside the MCP server,
  scoped to read access on OneLake only (no broad Fabric or Power BI
  scopes). It MUST NOT request or store the user's password. It MUST
  NOT require Azure CLI to be installed or pre-authenticated on the
  user's machine. Tokens MUST be cached only for the duration of the
  session and MUST NOT be persisted to disk in a form that survives
  process exit unless the user opts in explicitly via the repo
  configuration YAML file (`token_cache: enabled`). When enabled, the
  cache MUST be written to a `.narrator-token-cache` file in the repo
  root, which MUST be listed in the repository's `.gitignore` by
  default. The cache file location MUST be documented in the README
  so users can audit or delete it. The scanner MUST NOT require any separate
  authentication; it runs under the running user's Fabric session
  identity (the standard Fabric notebook delegated context exposed
  via `notebookutils` / `mssparkutils` and in-runtime authenticated
  SDK clients) and inherits the user's existing Fabric workspace
  permissions.

- **FR-002**: The agent MUST present a Modeling Readiness scan plan to
  the user before executing scans, naming the four disciplines and
  indicating which will be assessed fully, partially, or not at all in
  this version. The plan MUST allow the user to scope the scan (full
  sweep, single discipline, single artifact, etc.).

- **FR-003**: The scanner MUST enumerate Power BI semantic models in
  scope and extract: model ID, name, table list, relationship list,
  measure definitions, primary key declarations, and the source columns
  each table is built on. This data feeds Canonical Entity Modeling
  diagnosis and is written into the OneLake findings artifact.

- **FR-004**: The scanner MUST enumerate Fabric IQ ontologies in scope
  and extract: entity types, properties on each entity type,
  relationships between entity types, data bindings (which OneLake
  source backs each binding), presence/absence of source-attribution
  properties, and the semantic models or lakehouse tables each binding
  traces back to. This data feeds Canonical Entity Modeling and
  Field-Level Lineage diagnosis and is written into the OneLake
  findings artifact.

- **FR-005**: The agent MUST identify candidate canonical entity
  conflicts — same logical entity defined inconsistently across semantic
  models and ontologies — using configurable name-similarity rules
  seeded with synonyms for common entities (Customer, Account, Product,
  Material, Vendor, Supplier, Order, Invoice, Asset, Site). The default
  name-similarity threshold is **0.85** (cosine similarity or equivalent
  normalized Levenshtein ratio). The threshold MUST be overridable via a
  repo configuration YAML file so architects can lower it for tenants that
  use abbreviated naming conventions. Matches below the threshold MUST be
  silently discarded; matches at or above the threshold MUST be surfaced
  as "candidate canonical entity conflicts" pending user confirmation
  before being scored as confirmed findings (see Edge Cases).

- **FR-006**: For each candidate canonical entity conflict, the agent
  MUST surface specific points of disagreement: primary key choice, join
  logic to related entities, filter contexts, measure definitions,
  underlying source columns. These specifics are the substance of
  Canonical Entity Modeling findings.

- **FR-007**: For each Fabric IQ ontology, the agent MUST audit
  Field-Level Lineage by checking each entity type for source-attribution
  properties (source-system identifier, source-record identifier,
  extraction-timestamp, confidence score, or equivalents) and reporting
  the gap. The agent MUST NOT prescribe specific property names; the
  Framework is about the principle, not a Microsoft-specific schema.

- **FR-008**: The agent MUST score each fully-assessed discipline on a
  0–4 maturity scale with a one-sentence rationale tied to specific
  findings. Scores MUST be derived deterministically from a
  findings-count threshold table defined in a versioned scoring rubric
  YAML file shipped in the repository (e.g., 0 findings = 4,
  1–2 = 3, 3–5 = 2, 6–10 = 1, 11+ = 0). The rubric MUST be
  human-readable and reviewable by architects before v1 ships
  (NFR-006). The agent MUST score partially-assessed disciplines with
  explicit caveats noting which scope was not assessed. The agent MUST
  mark non-assessed disciplines as "not assessed in this version" with
  a brief explanation.

- **FR-009**: The agent MUST generate four deliverable files into the
  workspace on user request: an executive summary, a detailed findings
  document, a remediation plan, and a workshop agenda. Every file MUST
  use the four discipline names exactly as specified in the constitution.

- **FR-010**: Every finding in every deliverable MUST cite a source
  artifact (model ID, ontology ID, table name) such that a reader can
  verify it. Deliverables without source citations are not acceptable
  output.

- **FR-011**: The repository MUST ship a synthetic-data provisioner as
  one or more Fabric notebooks (NOT as a laptop CLI) that the
  architect imports into a Fabric workspace they have explicitly
  designated as a demo tenant via repository configuration. When run,
  the provisioner notebook(s) create:
    (a) at least three semantic models from three notional source
        systems containing inconsistent definitions of at least the
        Customer and Product entities (Canonical Entity Modeling debt);
    (b) at least one Fabric IQ ontology with no source-attribution
        properties bound to those semantic models (Field-Level Lineage
        debt);
    (c) supporting OneLake tables and a sample Data Agent configuration
        for end-to-end demo;
    (d) at least one entity that is well-modeled in all assessed
        disciplines, so the agent's findings include positive examples
        and not only debt.
  The provisioner notebook(s) MUST run under the same delegated Fabric
  session identity model as the scanner (no new Entra app
  registration), MUST verify the workspace is flagged as a demo tenant
  in repo configuration before writing, and MUST require explicit
  user confirmation in a notebook cell before any creation operation.

- **FR-012**: The synthetic-data provisioner notebook(s) MUST be
  idempotent (re-running against an already-provisioned demo workspace
  produces no duplicates and no errors) and MUST ship with a
  companion teardown notebook that removes only the artifacts the
  provisioner created.

- **FR-013**: The agent MUST surface preview-feature dependencies (Fabric
  IQ ontology, Data Agent, etc.) and warn the user if the target tenant
  does not have these features enabled, before attempting scans that
  depend on them.

- **FR-014**: All user-facing agent output (in-chat conversation,
  generated files, error messages) MUST use the four discipline names
  exactly: Canonical Entity Modeling, Field-Level Lineage, Layered
  Modeling, Steward-Loop Modeling. Abbreviations and informal variants
  are forbidden in user-facing surfaces.

- **FR-015**: The repository MUST be self-contained and runnable
  immediately after `git clone` plus a single documented bootstrap
  step (e.g., `./bootstrap.ps1` on Windows, `./bootstrap.sh` on
  macOS/Linux) that installs Python/Node dependencies and registers
  the MCP server with the user's AI host(s). The bootstrap MUST
  auto-detect all supported AI hosts already installed on the machine,
  configure each one silently (creating the host's MCP registration
  file if it does not exist), and print a summary of which hosts were
  configured. The bootstrap MUST NOT require admin privileges and MUST
  NOT modify state outside the cloned repo and the user's AI-host
  configuration files. The scanner notebook MUST live in the
  repository at a documented path and MUST be importable into Fabric
  via the standard Fabric notebook-import flow without modification.

- **FR-016**: The narrator's MCP server MUST expose tools with stable,
  documented names (e.g., `list_runs`, `load_run`,
  `list_semantic_models`, `extract_entity_definitions`,
  `audit_source_attribution`, `enumerate_ontologies`) that read
  exclusively from the OneLake findings artifact. These tools MUST
  NOT call Fabric or Power BI APIs directly. The LLM-driven agent
  persona MUST invoke findings only through these tools — it MUST NOT
  generate findings from prose-level reasoning. This is how the
  constitution's diagnostic-determinism principle is physically
  enforced for the narrator; for the scanner, determinism is enforced
  by the absence of LLM calls in the notebook.

- **FR-017**: The repository MUST support the major MCP-capable AI
  hosts a customer may have already standardized on. "Supported"
  means: the repo ships the configuration files the host needs
  (`.vscode/mcp.json` for VS Code + GitHub Copilot; the equivalent
  registration files for Claude Code, Cursor, and any other host
  named in the README) and the agent persona files are written in a
  host-neutral form that all supported hosts can consume. GitHub
  Copilot in VS Code is the primary documented path; other hosts are
  tested at best-effort and documented as such.

- **FR-018**: The scanner notebook MUST be self-contained and runnable
  inside any Fabric workspace where the user has at minimum Viewer +
  Run permissions, without requiring additional libraries beyond what
  Fabric notebooks supply by default. The scanner MUST be a Python
  Fabric notebook (NOT a PySpark notebook); the scans operate on
  metadata, not data volumes, and Spark would impose unnecessary
  cold-start cost and capacity consumption on the customer's Fabric
  tenant. The notebook MUST NOT require any new Entra app
  registration, MUST NOT prompt for credentials, and MUST run
  entirely under the running user's Fabric session identity using the
  platform-supplied delegated context (`notebookutils` /
  `mssparkutils` and in-runtime authenticated SDK clients). The
  notebook MUST emit human-readable progress to its own output cells
  in addition to writing the findings artifact.

- **FR-019**: The OneLake findings artifact written by the scanner is
  the contract between scanner and narrator. It MUST be written under
  a namespaced path of the form
  `Files/modeling-readiness/<run-id>/` where `<run-id>` is a sortable
  timestamp plus a short random suffix. The artifact MUST contain at
  minimum: a `manifest.json` (run metadata: timestamp, scanner
  version, workspace ID, scope), a `findings.json` (all findings in
  schema-versioned form, one finding per record, each citing source
  artifacts), and a `raw/` subfolder with raw extracted metadata
  sufficient for the narrator to verify or re-derive any finding
  without re-querying Fabric. The schema MUST be versioned and
  MUST be documented in the repository.

- **FR-020**: The narrator MUST NOT require any Fabric or Power BI
  API access scope. Its only required scope is OneLake read on the
  workspace folder containing the findings artifact. This is the
  consent surface customers see during Entra device code sign-in,
  and is the deliberate friction-reduction outcome of the two-
  component architecture.

- **FR-021**: The narrator MUST accept a Fabric workspace URL pasted
  into the chat as the primary user gesture for scoping an
  assessment, infer the OneLake findings folder path from the
  workspace URL, and list the runs it finds there. The narrator MUST
  also accept a direct OneLake / `abfss://` path as a fallback. The
  repository configuration file MUST cache the most-recently-used
  workspace target so subsequent assessments can proceed without
  re-pasting; the cache MUST be plain-text, human-editable, and
  scoped to the cloned repository (not a global user setting).

- **FR-022**: When the narrator finds multiple runs in a workspace's
  findings folder, it MUST select the most recent run by default
  (run-ids are sortable timestamps), narrate from that run, and
  surface a one-line in-chat note that N prior runs are available
  and comparison is supported on user request. The narrator MUST
  NOT block on a run-selection prompt for first-time users.
  Comparison across runs is permitted in v1 only as a thin pass
  ("what changed since last run"); deeper trend analysis is
  reserved for v2.

- **FR-023**: The narrator MUST be forward-tolerant to scanner schema
  versions. When it encounters an artifact written under a newer
  manifest schema than it knows, it MUST read the fields it
  recognizes, MUST mark unknown sections and fields as "produced by
  a newer scanner; not interpreted in this version" in both
  in-chat output and generated deliverables, and MUST proceed
  rather than refuse. The narrator MUST refuse only when the
  artifact is missing required fields its known schema version
  declares mandatory (a corruption signal, not a version-skew
  signal). This forward-tolerance is the contract that lets
  scanner-side improvements ship ahead of narrator-side updates
  without breaking customer clones.

### Non-functional requirements

- **NFR-001**: A full Modeling Readiness assessment of a workspace with
  up to 50 semantic models and up to 5 ontologies MUST complete within
  5 minutes wall-clock time.

- **NFR-002**: The synthetic-data provisioner MUST complete within 10
  minutes against a Fabric capacity of F2 or higher.

- **NFR-003**: The agent MUST work against Fabric IQ in its current
  preview state. When an API call fails because of a preview-feature
  change, the agent MUST log the error, mark the affected scope as
  "not assessed," and continue with the remaining scope.

- **NFR-004**: The agent MUST be runnable end-to-end against the
  synthetic demo tenant in under 15 minutes total, measured from
  cold start to the first generated deliverable. The 15 minutes
  encompasses: importing the scanner notebook into Fabric, running
  it, cloning the repository, running the bootstrap step, MCP
  registration, Entra device code sign-in for OneLake, and the
  narrator producing the first deliverable. This is the
  customer-onboarding acceptance bar; if a customer's data lead
  cannot reach a working demo in 15 minutes from a cold start, the
  distribution model has failed.

- **NFR-005**: The deterministic analysis modules MUST achieve at least
  80% unit test coverage. The conversation and report-generation layers
  MUST have integration tests using captured fixture data from the
  synthetic scenario.

- **NFR-006**: All generated deliverables MUST be reviewed by a
  Microsoft principal architect during testing for vocabulary compliance
  (the four discipline names used exactly) before the agent ships its
  v1 internal release. Vocabulary regressions are blocker bugs.

### Key entities

- **Workspace**: a Fabric workspace containing the artifacts under
  Modeling Readiness assessment. The unit of scope for a single run.

- **Semantic Model**: a Power BI semantic model item; contains tables,
  relationships, and measures. The primary source of Canonical Entity
  Modeling findings.

- **Ontology**: a Fabric IQ ontology item; contains entity types,
  properties, relationships, and data bindings. The primary source of
  Field-Level Lineage findings, and a secondary source of Canonical
  Entity Modeling findings.

- **Entity Definition**: an extracted representation of how a semantic
  model or ontology defines a logical business entity. Compared across
  models to detect Canonical Entity Modeling debt.

- **Canonical Entity Conflict**: a detected disagreement between two or
  more Entity Definitions claiming to represent the same logical entity.
  The unit of Canonical Entity Modeling debt.

- **Source-Attribution Gap**: a detected absence of source-attribution
  properties on an entity type or its bindings. The unit of Field-Level
  Lineage debt.

- **Finding**: a single observation about the workspace, mapped to one
  of the four disciplines, anchored to one or more source artifacts,
  with a severity and a remediation hint.

- **Maturity Score**: a 0–4 score per discipline, derived
  deterministically from findings, with a one-sentence rationale and
  an "assessed / partially assessed / not assessed" status.

- **Deliverable**: a generated Markdown file written into a
  timestamped folder in the user's local clone of the repository
  (executive summary, findings detail, remediation plan, workshop
  agenda). Deliverables are committable artifacts, not ephemeral chat
  output.

- **MCP Tool**: a tool exposed by the narrator's MCP server that reads
  from the OneLake findings artifact written by the scanner. The
  LLM-driven agent persona invokes these tools to produce findings
  in conversation; it does not synthesize findings from prose. The
  set of MCP tools is the physical enforcement of the
  diagnostic-determinism principle for the narrator. (For the
  scanner, determinism is enforced by the absence of any LLM call
  in the notebook.)

- **Findings Artifact**: the schema-versioned bundle of files written
  by the scanner to OneLake at `Files/modeling-readiness/<run-id>/`,
  containing at minimum a `manifest.json`, a `findings.json`, and a
  `raw/` subfolder. This artifact is the contract between scanner
  and narrator and the only thing the narrator reads from the
  customer's tenant.

- **Demo Workspace**: a synthetic workspace created by the provisioner,
  modeled on a mid-market industrial manufacturer with three source
  systems, used for internal demos without customer data.

- **Modeling Readiness Pattern**: a named implementation pattern that
  addresses a specific debt type (e.g., "Reconciliation Rule
  Documentation," "Source-System Provenance Columns," "Workspace-
  Scoped Customization"). Patterns are referenced by remediation hints
  in findings and by the remediation plan deliverable. The set of
  patterns is fixed in v1 and documented in the repo.

## Out of scope (v1)

- Layered Modeling and Steward-Loop Modeling deep analysis. The agent
  observes signals when present but does not run dedicated diagnostic
  passes for these disciplines. Reserved for v2.

- Query log analysis (which entities are joined together in practice).
  Reserved for v2.

- Override-pattern detection in lakehouse data. Reserved for v2.

- Data Agent conversation log analysis. Reserved for v2.

- Automated remediation execution. The agent surfaces what to do; humans
  do the work. The Framework is explicit that the political and
  organizational work of modeling discipline cannot be automated.

- Multi-tenant comparison or benchmarking. Each run is single-tenant.
  Cross-customer benchmarks are a v3+ consideration with significant
  privacy implications.

- A rendered web UI. v1 is conversational in the user's AI host only.

- A published GitHub Copilot extension, VS Code extension, or any
  marketplace-distributed package. v1 ships as a cloneable repo only.
  A marketplace extension may be considered for v2 if customer
  feedback indicates the clone+bootstrap step is a barrier; v1 deems
  the trade-off unacceptable because marketplace approval and update
  cycles are slower than the framework iteration cadence.

- Public distribution outside Microsoft. v1 is internal-only; public
  distribution depends on stakeholder alignment outcomes documented
  separately from this spec.

## Future direction (non-binding)

- **First-party Fabric workload (v3 destination)**: the long-term
  destination for the scanner is a first-party Fabric capability — an
  "Assess Modeling Readiness" action available natively in the Fabric
  workspace UI, removing the notebook-import step entirely. v1
  deliberately ships as an importable notebook to avoid blocking on
  Fabric PM partnership and release-train alignment, but the OneLake
  findings artifact contract (FR-019) is designed so that the
  narrator continues to work unchanged when the scanner migrates to
  a first-party surface.

## Success criteria

- A customer data lead with no prior exposure to the agent can import
  the scanner notebook into a Fabric workspace, run it, clone the
  repo, run the bootstrap step, sign in via Entra device code (OneLake
  read scope only), and produce all four deliverables in under 15
  minutes from cold start, working in GitHub Copilot in VS Code. This
  is the customer-onboarding acceptance bar.

- The same end-to-end flow works in at least one additional
  MCP-capable AI host (Claude Code, Cursor, or github.com chat with
  MCP) without code changes to the repository — only the host's
  native MCP registration step. This validates the surface-agnostic
  distribution promise.

- Three internal architects independently rate the agent's Canonical
  Entity Modeling findings against a real customer tenant as "matches
  what I would have found manually" or better. This is the diagnostic-
  credibility bar.

- The Fabric IQ PM team reviews the agent's output against a
  representative ontology and confirms no fabricated or misleading
  findings, and confirms the Framework's framing is fair to Fabric IQ.
  This is the product-relationship bar.

- The synthetic-data provisioner produces a demo workspace where a
  fresh assessment run scores Canonical Entity Modeling at maturity
  level 1 (low) and Field-Level Lineage at maturity level 0 or 1, with
  at least one entity scoring well to demonstrate the Framework
  recognizes good modeling rather than only flagging debt.

- Every deliverable produced by the agent uses the four discipline
  names exactly. Vocabulary review during internal testing finds zero
  regressions before v1 internal release.
