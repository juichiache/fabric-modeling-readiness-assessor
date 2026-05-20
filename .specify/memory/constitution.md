# Constitution: Modeling Readiness Assessor

## Project Identity

This project implements the Modeling Readiness Framework — a structured
approach to diagnosing customer modeling debt before customer data is wired
to Microsoft Fabric IQ ontologies and Data Agents. The Framework defines
four disciplines that, together, determine whether a customer's data is
ready to ground AI agents reliably:

  1. **Canonical Entity Modeling** — every business entity has one
     definition with explicit reconciliation rules across systems.
  2. **Field-Level Lineage** — source attribution lives in the data as
     first-class properties, not as a system-level audit log.
  3. **Layered Modeling** — customer-specific extensions live in their
     own scope and never mutate the canonical model.
  4. **Steward-Loop Modeling** — corrections from users and stewards flow
     back into the model rather than dying in tickets.

Every artifact this project produces — code, documentation, deliverables,
agent conversations — uses these four discipline names exactly. Variations
("entity discipline," "lineage practice," "extension hygiene," etc.) are
NOT permitted. Vocabulary consistency is what makes the Framework durable
across customer engagements; drift makes it forgettable.

## Core Principles

### I. Diagnostic determinism over generative interpretation (NON-NEGOTIABLE)
All findings about a customer's tenant MUST come from deterministic code
that reads structured metadata (Power BI semantic models, Fabric IQ
ontologies, lakehouse schemas). LLM calls MUST be confined to: conducting
the conversation with the user, summarizing deterministic findings into
narrative form, and generating report prose. An LLM MUST NEVER be the
source of a finding about the customer's data state. Hallucinated findings
against a customer tenant are a credibility-ending failure mode for this
project and for the Framework's standing inside Microsoft.

### II. Honesty about scope (NON-NEGOTIABLE)
The agent assesses Canonical Entity Modeling fully and Field-Level Lineage
partially. It scores Layered Modeling and Steward-Loop Modeling only when
unambiguous signals exist, and otherwise marks them "not assessed in this
version." It MUST NOT fabricate maturity scores to feel complete. Every
deliverable MUST make this scope honesty visible to the reader.

### III. Read-only by default
The agent MUST NOT write to, modify, or delete any artifact in a customer
or production tenant. Two narrow exceptions are permitted:
  1. The Fabric notebook component (the scanner) writes its findings
     artifact and raw evidence to a single, namespaced folder in OneLake
     under the assessed workspace (e.g.,
     `Files/modeling-readiness/<run-id>/`). It MUST NOT write anywhere
     else and MUST NOT modify any pre-existing artifact.
  2. The synthetic-data provisioning flow, which is itself implemented
     as a Fabric notebook running under the same delegated session
     identity model as the scanner, writes only to a Fabric tenant
     the user has explicitly designated as a demo tenant via
     repository configuration, and writes only to workspaces it has
     been explicitly run in.
Because the scanner runs inside the customer's Fabric workspace under
the running user's Fabric session identity (the standard Fabric
notebook delegated context), and the conversational agent runs on the
user's machine reading only the OneLake findings artifact, the
customer's existing Entra RBAC and Fabric workspace permissions are
the authoritative permission boundaries — each component inherits
exactly what its identity can see and do, and nothing more.

### IV. Findings must be reproducible
Every finding MUST cite the specific artifact (semantic model ID, ontology
ID, table name, column name) it was derived from. A reader of any
deliverable MUST be able to navigate to the source artifact and verify the
finding manually. Findings without traceable sources are forbidden.

### V. Conversation as primary UX
The agent's interface is a chat conversation in the user's IDE. Long-form
deliverables (executive summary, findings detail, remediation plan,
workshop agenda) are written as files in the workspace. The agent MUST
NOT produce wall-of-text responses in chat; in-chat output is for
surfacing findings, asking the user questions, and confirming actions.

### VI. The Framework is the framework
All findings, scoring, recommendations, and report sections MUST map to
one of the four named disciplines. Findings that do not fit the Framework
MUST NOT be invented to pad reports, and MUST NOT be reframed under a
discipline they do not belong to. If the agent observes something useful
that doesn't fit the Framework, it surfaces it as an "Additional
Observation" outside the maturity scoring.

### VII. Synthetic data is canonical for demos
The agent MUST be runnable end-to-end against a synthetic demo tenant
modeled on a mid-market industrial manufacturer with three source systems
(CRM, ERP, homegrown invoicing). The synthetic tenant is the canonical
demo path. Internal distribution and onboarding MUST NOT require pointing
the agent at a real customer tenant to see meaningful output. The
end-to-end onboarding bar is: from a cold start, the customer's data
lead imports the scanner notebook into their Fabric workspace, runs it,
clones the repo, opens it in their AI host, and reaches the first
generated deliverable in under 15 minutes.

### VIII. Framework vocabulary is canonical
All code, documentation, agent conversation, and deliverable output MUST
use the four discipline names exactly:
  - "Canonical Entity Modeling" (not "Entity," not "Identity," not "ECM")
  - "Field-Level Lineage" (not "Provenance," not "FLL," not "Lineage")
  - "Layered Modeling" (not "Extension," not "Hygiene," not "Layering")
  - "Steward-Loop Modeling" (not "Closed Loop," not "Feedback," not "SLM")
Abbreviations are forbidden in user-facing output. Internal code
identifiers MAY use camelCase or snake_case versions (canonicalEntityModeling,
field_level_lineage) but MUST NOT use abbreviations.

## Constraints

- The agent is distributed as two cooperating components:
  1. **Scanner**: a Python Fabric notebook (NOT a PySpark notebook,
     because the scans operate on metadata rather than data volumes
     and a Spark cluster would impose unnecessary cold-start cost and
     capacity consumption) imported into the customer's Fabric
     workspace and executed there under the running user's Fabric
     session identity (the standard Fabric notebook delegated
     context, exposed by the platform through `notebookutils` /
     `mssparkutils` and the in-runtime authenticated SDK clients).
     The scanner performs the deterministic Modeling Readiness scans
     against Fabric and Power BI APIs from inside the tenant and
     writes a structured findings artifact (JSON plus raw evidence)
     to a namespaced OneLake folder in the assessed workspace.
  2. **Narrator**: a cloneable Git repository constituted by
     agent-customization files (skills, agent personas, instructions)
     and a Model Context Protocol (MCP) server. The narrator runs on
     the user's machine inside any MCP-capable AI host the user
     already has (GitHub Copilot in VS Code is the primary documented
     path; Claude Code, Cursor, JetBrains AI, and github.com chat with
     MCP are best-effort supported). The MCP server's tools read the
     OneLake findings artifact and surface findings to the LLM-driven
     persona for narration into deliverables.
  Neither component MAY be replaced by a published marketplace
  extension in v1.

- The scanner MUST authenticate using the running user's Fabric session
  identity, as supplied by the standard Fabric notebook runtime (the
  delegated context exposed via `notebookutils` / `mssparkutils` and
  in-runtime authenticated SDK clients). It MUST NOT require its own
  Entra app registration, MUST NOT request additional credentials
  beyond the user's existing Fabric sign-in, and MUST NOT escalate
  privileges beyond what the running user already holds in the
  workspace.

- The narrator MUST authenticate to OneLake using Microsoft Entra ID
  device code flow, brokered by MSAL inside the MCP server, scoped to
  read access on OneLake only (no broad Fabric or Power BI scopes). It
  MUST NOT require Azure CLI to be installed or pre-authenticated. It
  MUST NOT prompt for customer credentials over insecure channels or
  persist them beyond the session, except via an explicit opt-in token
  cache documented in the repo.

- The deterministic analysis layer (the scanner) MUST be testable in
  isolation (without an LLM, without a live Fabric tenant) using
  fixture data derived from the synthetic demo scenario. The OneLake
  findings artifact schema is the contract between scanner and
  narrator; the MCP tool surface is the boundary where determinism is
  enforced for the narrator: LLM-driven persona files invoke findings
  only through MCP tools that read the artifact, never through
  prose-level reasoning.

- The agent MUST work against Fabric IQ in its current preview state and
  tolerate API changes gracefully (warn and degrade, do not crash).

- All Microsoft API calls MUST go through the official Fabric REST API,
  Power BI REST API, or OneLake APIs. Reverse-engineered or
  undocumented endpoints are forbidden.

- The synthetic demo scenario MUST be a mid-market industrial manufacturer
  with three source systems and 8–12 entities total, of which 3–5 exhibit
  deliberate modeling failures across the four disciplines. The scenario
  MUST NOT extend or reference Microsoft's public Lakeshore Retail
  tutorial; the Framework's credibility depends on being usable across
  customer scenarios, not anchored to one.

## Development Workflow

- Spec → Plan → Tasks → Implement, in that order. No implementation before
  /speckit.tasks has produced an approved task list.

- Tests for the deterministic analysis modules are written before the
  modules themselves. The conversation layer and report generation may be
  tested via fixture-based integration tests using the synthetic scenario
  as the canonical fixture source.

- The synthetic-data provisioner is a first-class feature with its own
  spec subsection, its own tests, and its own acceptance criteria — not a
  demo afterthought. The agent's internal distribution depends on the
  provisioner working cleanly.

- Vocabulary review is a step in every PR. Reviewers check that the four
  discipline names appear exactly as specified, with no drift, in all
  changed files. This is the cheapest moment to catch vocabulary erosion.

## Governance

This constitution supersedes any conflicting suggestion from a coding
agent or implementation expediency argument. Amendments require updating
this file and re-running /speckit.analyze on existing artifacts to surface
conflicts. Vocabulary changes (renaming a discipline, renaming the
Framework) require updating this file, the spec, the plan, and all
generated tasks before any code change.

**Version**: 1.0.0 | **Ratified**: [DATE] | **Last Amended**: [DATE]
