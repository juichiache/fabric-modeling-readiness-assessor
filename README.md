# Fabric Modeling Readiness Assessor

**Who this is for:** Data architects and platform engineers preparing a Microsoft Fabric workspace for Fabric IQ (AI-powered Q&A and analytics). Before AI can answer questions about your data, your semantic models and ontologies need to be modeled correctly. This tool tells you exactly where the gaps are—and what to do about them.

**What it does:** In about fifteen minutes, it produces:
- An **executive summary** scoring your workspace across four modeling disciplines
- A **findings report** grouped by pattern, with specific models and fields called out
- A **remediation plan** your team can execute against

**How it works:** A Fabric notebook scans your workspace using the Power BI REST API and Fabric IQ APIs. It writes a structured findings artifact to OneLake. You open the narrator in your AI host (VS Code + GitHub Copilot, Claude Code, or Cursor), and an agent reads those findings to guide the conversation, generate deliverables, and answer follow-up questions—grounded in evidence, not guesswork.

---

---

## Prerequisites

- **Fabric workspace** with Viewer + Run notebook permissions
- **Python 3.11+** on your local machine
- **VS Code** with [GitHub Copilot](https://marketplace.visualstudio.com/items?itemName=GitHub.copilot) (primary path), or Claude Code, or Cursor

---

## Getting Started

### Step 1 — Clone the narrator repository

```bash
git clone https://github.com/YOUR-ORG/fabric-modeling-readiness.git
cd fabric-modeling-readiness/modeling-readiness-assessor
```

### Step 2 — Run bootstrap

Bootstrap installs the narrator's Python dependencies and registers the MCP server with your AI host automatically.

**Windows:**
```powershell
.\bootstrap.ps1
```

**macOS / Linux:**
```bash
chmod +x bootstrap.sh && ./bootstrap.sh
```

Follow the prompts. When it finishes, you'll see confirmation that the MCP server is registered.

### Step 3 — Upload the scoring rubric to your Fabric workspace

The scanner notebook needs `scoring-rubric.yaml` at runtime. Upload it to your Fabric workspace's default lakehouse:

1. In the Fabric portal, open your workspace's default lakehouse
2. Go to **Files**
3. Upload `scoring-rubric.yaml` from the root of this repository

### Step 4 — Import and run the scanner notebook

1. In the Fabric portal, go to **My workspace** → **Import** → **Notebook**
2. Import `scanner/modeling-readiness-scanner.ipynb`
3. Open the imported notebook
4. **Run Cell 0** — this installs the scanner library. When it finishes, restart the kernel.
5. In **Cell 1**, set your workspace details:
   ```python
   WORKSPACE_ID = "your-workspace-guid"
   WORKSPACE_URL = "https://app.fabric.microsoft.com/groups/your-workspace-guid/..."
   ```
6. Run all remaining cells top-to-bottom

When the final cell completes, the findings artifact has been written to `Files/modeling-readiness/<run-id>/` in your OneLake.

### Step 5 — Configure the narrator

Edit `narrator.config.yaml` in the repo root:

```yaml
workspace_url: "https://app.fabric.microsoft.com/groups/<your-workspace-guid>/..."
```

That's the same URL you used in the notebook.

### Step 6 — Open your AI host and start the assessment

1. Open VS Code in the `modeling-readiness-assessor/` folder
2. Open GitHub Copilot Chat
3. Switch to **Agent mode**
4. Type: `@narrator assess this workspace`

The narrator will read the findings artifact from OneLake and guide you through the assessment conversation. When you're done, type `write deliverables` — the agent will produce an executive summary, findings report, and remediation plan in an `assessments/` folder.

---

## What gets assessed

| Discipline | What it detects |
|------------|-----------------|
| **Canonical entity modeling** | Inconsistent entity definitions across semantic models (mismatched keys, join logic, naming) |
| **Field-level lineage** | Missing source-attribution properties in Fabric IQ ontology entity types |
| **Layered modeling** | Absence of bronze/silver/gold staging layers *(not assessed in v1)* |
| **Steward-loop modeling** | Absence of data stewardship feedback loops *(not assessed in v1)* |

### Scoring

| Findings count | Score | Label |
|----------------|-------|-------|
| 0 | 4 | Excellent |
| 1–2 | 3 | Good |
| 3–5 | 2 | Fair |
| 6–10 | 1 | Poor |
| 11+ | 0 | Critical |

Disciplines without detectable signals are reported as "not assessed in this version."

---

## Supported AI hosts

| Host | Setup |
|------|-------|
| VS Code + GitHub Copilot | Automatic (bootstrap writes `.vscode/mcp.json`) |
| Claude Code | Automatic (bootstrap writes `claude_mcp_config.json`) |
| Cursor | Automatic (bootstrap writes `.cursor/mcp.json`) |

---

## Configuration reference

`narrator.config.yaml`:

| Field | Default | Description |
|-------|---------|-------------|
| `workspace_url` | `""` | Fabric workspace URL — required |
| `token_cache` | `false` | Cache MSAL tokens in `.narrator-token-cache` (gitignored) |
| `similarity_threshold` | `0.85` | Entity name similarity threshold `[0.5, 1.0]` |
| `demo_workspace` | `false` | Set `true` only when running the provisioner/teardown notebooks |

---

## Troubleshooting

**"WORKSPACE_ID not set" error in the notebook**  
Set `WORKSPACE_ID` and `WORKSPACE_URL` in Cell 1 before running.

**Cell 0 pip install fails in Fabric**  
Make sure `REPO_URL` in Cell 0 points to the correct GitHub URL for this repo. The repo must be publicly accessible or reachable from the Fabric notebook runtime.

**MCP server not appearing in VS Code**  
Rerun bootstrap. If VS Code was open during bootstrap, reload the window (`Ctrl+Shift+P` → *Developer: Reload Window*).

**"No findings artifact" error from the narrator**  
The scanner notebook must complete successfully first. Check that `Files/modeling-readiness/` exists in your OneLake and that `narrator.config.yaml` has the correct `workspace_url`.

**Authentication prompt on first narrator run**  
The narrator uses Microsoft Entra device-code flow to read OneLake (read-only scope). Follow the prompt to sign in. Set `token_cache: true` in `narrator.config.yaml` to avoid re-authenticating on every run.

---

## What you can build on top of this

The framework is designed to be extended:

- **Add disciplines.** Each discipline is a discrete module in `scanner/lib/scanner/`. Add vertical-specific entities or deeper signals without touching the rest.
- **Consume findings downstream.** Findings emit as structured JSON (`findings.json` in OneLake). Downstream agents—remediation trackers, Planner integrations, empirical assessors—can read them directly.
- **Adopt the framework without the agent.** The four disciplines and ten patterns are documented independently in `docs/patterns.md`. Usable on their own without running the agent.

---

## Development

```powershell
# Install dev dependencies
pip install pytest pytest-cov rapidfuzz pyyaml msal azure-storage-file-datalake jinja2

# Run tests
$env:PYTHONPATH = "."
python -m pytest tests/ -q
```

---

## License

MIT — see [LICENSE](LICENSE).


All Session 1 and Session 2 clarifications are resolved in
`spec.md`. The spec is ready to drive Spec Kit's planning commands.
