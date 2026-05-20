# Modeling Readiness Assessor — Spec Kit Artifacts

This directory contains the Spec Kit-shaped artifacts for the Modeling
Readiness Assessor agent, ready to drop into a Spec Kit-initialized
project.

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
