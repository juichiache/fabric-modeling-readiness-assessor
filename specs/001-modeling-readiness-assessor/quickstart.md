# Quickstart: Modeling Readiness Assessor

**Audience**: Microsoft principal architects onboarding a customer.  
**Goal**: Reach the first generated deliverable in under 15 minutes from cold start (NFR-004).

---

## Prerequisites

- A Fabric workspace the customer's data lead has at minimum **Viewer + Run** permissions on.
- The data lead's machine has **git**, **Python 3.11+**, and at least one supported AI host installed (GitHub Copilot in VS Code, Claude Code, or Cursor).
- No Azure CLI, no new Entra app registration, no admin privileges required.

---

## Step 1 — Run the Scanner (in Fabric)

1. In the customer's Fabric workspace, select **Import notebook**.
2. Upload `scanner/modeling-readiness-scanner.ipynb` from this repository.
3. Open the notebook and run all cells. The notebook will:
   - Enumerate all Power BI semantic models and Fabric IQ ontologies in the workspace.
   - Detect Canonical Entity Modeling conflicts and Field-Level Lineage gaps.
   - Write a findings artifact to `Files/modeling-readiness/<run-id>/` in OneLake.
   - Print human-readable progress to each output cell.
4. When the final cell prints **"Findings artifact written to OneLake"**, the scanner is done.

> **No credentials to enter.** The notebook runs under your Fabric workspace identity automatically.

---

## Step 2 — Bootstrap the Narrator (on your laptop)

```bash
git clone <narrator-repo-url>
cd modeling-readiness-assessor

# Windows:
./bootstrap.ps1

# macOS / Linux:
./bootstrap.sh
```

The bootstrap will:
- Install Python dependencies for the MCP server (`narrator/mcp_server/`).
- Detect installed AI hosts and register the MCP server with each one.
- Print a summary table of what was configured.

> **No admin required.** The bootstrap writes only inside the cloned repo and to the AI host's own config file.

---

## Step 3 — Sign In to OneLake

The first time you start a narration session, the MCP server will prompt you with a device code:

```
To sign in, open https://microsoft.com/devicelogin and enter code: XXXX-XXXX
```

Open the link, enter the code, and sign in with the same account that has Viewer access to the customer's Fabric workspace. The required consent is **OneLake read only** — no Fabric or Power BI admin consent required.

> **Optional**: To persist the token across sessions, add `token_cache: enabled` to `narrator.config.yaml`. The token will be saved to `.narrator-token-cache` in the repo root (gitignored).

---

## Step 4 — Start a Narration Session

Open your AI host (e.g., VS Code with GitHub Copilot in Agent mode) in the cloned repository folder.

Paste the customer's Fabric workspace URL into the chat:

```
https://app.fabric.microsoft.com/groups/<workspace-id>/...
```

The narrator will:
1. Resolve the OneLake path from the workspace URL.
2. List available assessment runs.
3. Load the most recent run by default.
4. Present an inventory of what was scanned and offer to walk through findings by discipline.

---

## Step 5 — Generate Deliverables

When you've reviewed the findings in chat, ask the agent to generate the deliverables:

```
Generate the full set of deliverables for this assessment.
```

The agent will write four files to `assessments/<timestamp>-<workspace>/`:
- `executive-summary.md` — scores per discipline, top findings, recommended next steps
- `findings-detail.md` — every finding with source citations
- `remediation-plan.md` — prioritized remediation items mapped to Modeling Readiness Patterns
- `workshop-agenda.md` — structured agenda for the follow-up workshop with the customer

These files are plain Markdown — commit them, diff them across runs, and share them via the customer's normal Git workflow.

---

## Demo Mode (No Customer Tenant)

To run the agent against the synthetic demo workspace:

1. Designate a Fabric workspace as a demo tenant by setting `demo_workspace: true` in `narrator.config.yaml`.
2. Import and run `scanner/provisioner.ipynb` in that workspace. The provisioner creates semantic models, a Fabric IQ ontology, and OneLake tables modeled on a mid-market industrial manufacturer.
3. Import and run `scanner/modeling-readiness-scanner.ipynb` in the same workspace.
4. Follow Steps 2–5 above using the demo workspace URL.

To reset the demo workspace, run `scanner/provisioner-teardown.ipynb`.

---

## Configuration Reference (`narrator.config.yaml`)

```yaml
# Fabric workspace URL — cached after first use; paste to override
workspace_url: ""

# Set to true to persist the OneLake auth token across sessions
# Token is written to .narrator-token-cache (gitignored)
token_cache: false

# Name-similarity threshold for entity conflict detection (0.0–1.0)
# Default 0.85 minimizes false positives; lower for abbreviated naming conventions
similarity_threshold: 0.85

# Set to true to allow the provisioner to write to this workspace
demo_workspace: false
```
