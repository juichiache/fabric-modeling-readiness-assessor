# Modeling Readiness Assessor

Diagnose Microsoft Fabric IQ modeling debt across four canonical disciplines using the Power BI REST API and Fabric IQ ontology API.

For the full quickstart, see **[`specs/001-modeling-readiness-assessor/quickstart.md`](specs/001-modeling-readiness-assessor/quickstart.md)**.

---

## Components

| Component | Location | Description |
|-----------|----------|-------------|
| Scanner notebook | `scanner/modeling-readiness-scanner.ipynb` | Fabric notebook — enumerates models and ontologies, writes findings artifact to OneLake |
| Narrator MCP server | `narrator/mcp_server/server.py` | MCP server — exposes 6 tools for reading findings artifacts |
| Deliverables | `narrator/mcp_server/deliverables.py` | Renders 4 Jinja templates into `assessments/` |
| Provisioner | `scanner/provisioner.ipynb` | Creates a demo workspace with deliberate modeling debt |
| Provisioner teardown | `scanner/provisioner-teardown.ipynb` | Removes provisioner demo resources |

---

## Four Canonical Disciplines

| Discipline | Description | Assessment Status |
|------------|-------------|-------------------|
| Canonical entity modeling | Detects inconsistent entity definitions (primary keys, join logic, names) across semantic models | Assessed |
| Field-level lineage | Detects missing source-attribution properties in Fabric IQ ontology entity types | Assessed |
| Layered modeling | Detects absence of bronze/silver/gold staging layers | Not assessed in this version |
| Steward-loop modeling | Detects absence of data stewardship feedback loops | Not assessed in this version |

---

## Bootstrap

**Windows (PowerShell):**
```powershell
.\bootstrap.ps1
```

**macOS/Linux:**
```bash
chmod +x bootstrap.sh && ./bootstrap.sh
```

The bootstrap script:
1. Installs narrator Python dependencies
2. Detects installed AI hosts (VS Code, Claude Code, Cursor)
3. Writes MCP registration files for each detected host

---

## Supported AI Hosts

| Host | MCP Config File |
|------|----------------|
| VS Code + GitHub Copilot | `.vscode/mcp.json` |
| Claude Code | `claude_mcp_config.json` |
| Cursor | `.cursor/mcp.json` |

---

## Running the Scanner

1. Import `scanner/modeling-readiness-scanner.ipynb` into your Fabric workspace
2. Set `WORKSPACE_ID` and `WORKSPACE_URL` in cell 1
3. Run all cells top-to-bottom
4. The findings artifact is written to `Files/modeling-readiness/<run-id>/` in your workspace's OneLake

---

## Configuration

Edit `narrator.config.yaml` before running:

```yaml
workspace_url: "https://app.fabric.microsoft.com/groups/<your-workspace-guid>/..."
token_cache: false        # Set to true to cache MSAL tokens in .narrator-token-cache (gitignored)
similarity_threshold: 0.85  # Entity name similarity threshold [0.5, 1.0]
demo_workspace: false     # Set to true only to run provisioner/teardown notebooks
```

### Token Cache

When `token_cache: true`, the narrator caches MSAL tokens in `.narrator-token-cache` at the repo root.
This file is gitignored and must never be committed.

---

## Scoring Rubric

Maturity scores follow a 0–4 scale defined in `scoring-rubric.yaml`:

| Findings | Score | Label |
|----------|-------|-------|
| 0 | 4 | Excellent |
| 1–2 | 3 | Good |
| 3–5 | 2 | Fair |
| 6–10 | 1 | Poor |
| 11+ | 0 | Critical |

Disciplines without detectable signals are reported as "not assessed in this version."

---

## Development

```powershell
# Run all tests
$env:PYTHONPATH = "."
python -m pytest tests/ -q
```

Requirements: Python 3.11+, `pip install pytest pytest-cov rapidfuzz pyyaml msal azure-storage-file-datalake jinja2`

---

## Contracts

- [`specs/001-modeling-readiness-assessor/contracts/findings-artifact.schema.md`](specs/001-modeling-readiness-assessor/contracts/findings-artifact.schema.md) — OneLake artifact JSON schema
- [`specs/001-modeling-readiness-assessor/contracts/mcp-tools.md`](specs/001-modeling-readiness-assessor/contracts/mcp-tools.md) — MCP tool surface
- [`specs/001-modeling-readiness-assessor/contracts/narrator-config.md`](specs/001-modeling-readiness-assessor/contracts/narrator-config.md) — narrator.config.yaml schema

---

## Background

The original spec and architecture description is preserved in the [spec bundle README below](#spec-kit-artifacts).

---

<details>
<summary>Spec Kit Artifacts (original README)</summary>

This directory contains the Spec Kit-shaped artifacts for the Modeling Readiness Assessor agent, ready to drop into a Spec Kit-initialized project.

See `specs/001-modeling-readiness-assessor/spec.md` for the full feature specification.

</details>

## Distribution model

The Modeling Readiness Assessor ships as **two cooperating components**,
not as a GitHub Copilot extension, not as a VS Code extension, not as
any marketplace-distributed package:

1. **Scanner** — a Fabric notebook the customer imports into their
   Fabric workspace and runs there. It executes the deterministic
   Modeling Readiness scans against Fabric/Power BI APIs from inside
   the tenant under the customer's own Fabric workspace identity, and
   writes a versioned findings artifact (JSON plus raw evidence) to
   `Files/modeling-readiness/<run-id>/` in OneLake. No new Entra app
   registration; no admin consent; no credential prompts.

2. **Narrator** — a cloneable Git repository the customer clones on
   their own machine and opens in whatever MCP-capable AI host they
   already use. The narrator's MCP server reads the scanner's OneLake
   findings artifact (OneLake-read scope only — not broad Fabric or
   Power BI scopes) and surfaces findings to an LLM-driven persona,
   which conducts the conversation and writes structured deliverables
   into a timestamped folder in the user's clone.

The narrator repository is constituted by:

- **Agent-customization files** (`AGENTS.md`, skill files, prompt
  files) that define the agent persona, vocabulary discipline, and
  conversational flow.
- **An MCP server** that exposes tools reading the OneLake findings
  artifact. The MCP tool surface is the physical enforcement of the
  constitution's diagnostic-determinism principle for the narrator:
  the LLM cannot fabricate findings, it can only call tools that read
  the artifact.
- **The scanner notebook** (versioned alongside the narrator so the
  schema contract stays in sync).
- **Host registration files** (e.g., `.vscode/mcp.json` for VS Code +
  GitHub Copilot; equivalents for other supported hosts) so the MCP
  server is discovered automatically after clone.
- **A synthetic-data provisioner CLI** that creates a demo Fabric
  workspace modeled on a mid-market industrial manufacturer.
- **Deliverable templates** that the agent fills in and writes to a
  timestamped folder in the user's clone.

GitHub Copilot in VS Code is the primary documented happy path for
the narrator. Claude Code, Cursor, JetBrains AI, and github.com chat
with MCP are supported as best-effort surfaces.

The long-term destination for the scanner is a first-party Fabric
workload (a native "Assess Modeling Readiness" action in the Fabric
workspace UI), removing the notebook-import step entirely. v1 ships
the scanner as a notebook deliberately, to avoid blocking on Fabric
PM/release alignment; the OneLake findings artifact schema is
designed so the narrator keeps working unchanged when that migration
happens.

## Layout

```
.specify/
  memory/
    constitution.md         # Non-negotiable project principles
  specs/
    001-modeling-readiness-assessor/
      spec.md               # The feature specification
docs/
  patterns.md               # The 10 Modeling Readiness Patterns
```

## How to use these files

1. Initialize a Spec Kit project somewhere convenient:

   ```
   uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
   specify init modeling-readiness-assessor
   cd modeling-readiness-assessor
   ```

2. Copy the three files from this bundle into the matching paths in
   the initialized project.

3. Resolve any remaining `[NEEDS CLARIFICATION]` markers in
   `spec.md` before running Spec Kit commands. (Currently: none
   open.)

4. Run, in order:

   ```
   /speckit.constitution
   /speckit.clarify
   /speckit.plan
   /speckit.analyze
   /speckit.tasks
   /speckit.implement
   ```

## Status

These files reflect the spec as drafted before the most recent
conversation about identity propagation, lightweight data-layer
inspection, two-agent split, action surface expansion, and
post-assessment user actions. None of those modifications are
incorporated yet. Treat this as the v1 spec; iterate from here.

## Resolved decisions

The following items were open in the original draft and are now
resolved in `spec.md`:

- **Distribution surface**: cloneable Git repository, IDE/host-
  agnostic via MCP and agent-customization files. No published
  extension in v1. Driven by the customer-run distribution model:
  architects guide customers to run the agent themselves on their own
  Fabric tenants, so marketplace install friction and host lock-in
  are unacceptable.
- **Authentication**: Microsoft Entra ID device code flow only,
  brokered by MSAL inside the MCP server, scoped to **OneLake read
  only** (no broad Fabric or Power BI scopes). Azure CLI is NOT a
  prerequisite. Microsoft architects may opt into an Azure CLI
  shortcut via env var, but no user-facing flow depends on it.
- **Synthetic source systems**: Dynamics 365 CRM + SAP S/4HANA ERP +
  a homegrown invoicing application represented as a SQL database
  mirrored to OneLake. Representative of real mid-market industrial
  manufacturers; exercises cross-vendor reconciliation; the
  homegrown system is the natural home for the most useful modeling
  debt.
- **Onboarding friction architecture**: the agent splits into a
  scanner (Fabric notebook running inside the customer's workspace
  under workspace identity) and a narrator (cloneable repo with MCP
  server reading the scanner's OneLake findings artifact). This
  eliminates the customer-side Entra admin-consent burden for broad
  Fabric/Power BI scopes. The first-party Fabric workload remains
  the v3 destination once Fabric's MCP/agent hosting story matures;
  the OneLake findings artifact schema is designed to make that
  later migration transparent to the narrator.
- **Synthetic-data provisioner location**: implemented as Fabric
  notebook(s), not as a laptop CLI. Runs under the same delegated
  Fabric session identity as the scanner; no separate Entra app
  registration; gated on a repo-config flag designating the target
  workspace as a demo tenant.
- **Scanner notebook runtime**: Python Fabric notebook (not
  PySpark). Metadata scans don't need Spark; Python avoids
  cluster-cold-start cost and unnecessary capacity consumption.
- **Narrator workspace scoping**: paste a Fabric workspace URL into
  the chat as the primary gesture; narrator infers the OneLake
  findings folder path. Repository configuration caches the
  most-recently-used workspace.
- **Multi-run handling**: narrator selects the most recent run by
  default and surfaces a one-line note that prior runs are
  available; comparison across runs supported on request.
- **Schema version skew**: narrator is forward-tolerant. When it
  reads an artifact written by a newer scanner schema, it interprets
  what it knows and explicitly marks unknown fields as
  "produced by a newer scanner; not interpreted in this version."

## Ready for `/speckit.clarify`

All Session 1 and Session 2 clarifications are resolved in
`spec.md`. The spec is ready to drive Spec Kit's planning commands.
