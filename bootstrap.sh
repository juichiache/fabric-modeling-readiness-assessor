#!/usr/bin/env bash
# Bootstrap the Modeling Readiness Assessor narrator MCP server (macOS/Linux).
#
# Steps:
#   1. Install narrator Python dependencies via pip.
#   2. Probe for known AI host config dirs (VS Code, Claude Code, Cursor).
#   3. Write host-specific MCP registration files.
#   4. Print summary — no sudo required.
#
# Usage:
#   chmod +x bootstrap.sh && ./bootstrap.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NARRATOR_PKG="$REPO_ROOT/narrator/mcp_server"

echo ""
echo "=== Modeling Readiness Assessor — Bootstrap ==="
echo ""

# ---------------------------------------------------------------------------
# Step 1: Install narrator Python dependencies
# ---------------------------------------------------------------------------
echo "[1/3] Installing narrator Python dependencies..."

if [ -d "$NARRATOR_PKG" ]; then
    pip install -e "$NARRATOR_PKG" --quiet
    echo "      ✓ narrator dependencies installed"
else
    echo "      ⚠ narrator/mcp_server not found at $NARRATOR_PKG — skipping."
fi

# ---------------------------------------------------------------------------
# Step 2: Probe for AI host config directories
# ---------------------------------------------------------------------------
echo ""
echo "[2/3] Probing for AI hosts..."

VSCODE_PROBE="$HOME/.vscode"
CLAUDE_PROBE="$HOME/.claude"
CURSOR_PROBE="$HOME/.cursor"

probe_host() {
    local name="$1"
    local probe_dir="$2"
    if [ -d "$probe_dir" ]; then
        echo "      ✓ $name: detected"
        echo "true"
    else
        echo "      – $name: not detected"
        echo "false"
    fi
}

VSCODE_DETECTED=$([ -d "$VSCODE_PROBE" ] && echo true || echo false)
CLAUDE_DETECTED=$([ -d "$CLAUDE_PROBE" ] && echo true || echo false)
CURSOR_DETECTED=$([ -d "$CURSOR_PROBE" ] && echo true || echo false)

echo "      $([ "$VSCODE_DETECTED" = true ] && echo '✓' || echo '–') VS Code: $([ "$VSCODE_DETECTED" = true ] && echo detected || echo 'not detected')"
echo "      $([ "$CLAUDE_DETECTED" = true ] && echo '✓' || echo '–') Claude Code: $([ "$CLAUDE_DETECTED" = true ] && echo detected || echo 'not detected')"
echo "      $([ "$CURSOR_DETECTED" = true ] && echo '✓' || echo '–') Cursor: $([ "$CURSOR_DETECTED" = true ] && echo detected || echo 'not detected')"

# ---------------------------------------------------------------------------
# Step 3: Write MCP registration files for detected hosts
# ---------------------------------------------------------------------------
echo ""
echo "[3/3] Writing MCP registration files..."

copy_config() {
    local detected="$1"
    local src="$REPO_ROOT/$2"
    local dst="$REPO_ROOT/$3"
    local host_name="$4"
    if [ "$detected" = true ] && [ -f "$src" ]; then
        mkdir -p "$(dirname "$dst")"
        cp -f "$src" "$dst"
        echo "      ✓ $host_name: wrote $3"
    fi
}

copy_config "$VSCODE_DETECTED" ".vscode/mcp.json" ".vscode/mcp.json" "VS Code"
copy_config "$CLAUDE_DETECTED" "claude_mcp_config.json" "claude_mcp_config.json" "Claude Code"
copy_config "$CURSOR_DETECTED" ".cursor/mcp.json" ".cursor/mcp.json" "Cursor"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Bootstrap Summary ==="
echo ""
printf "  %-15s %-10s %s\n" "Host" "Detected" "MCP Config"
printf "  %-15s %-10s %s\n" "----" "--------" "----------"
printf "  %-15s %-10s %s\n" "VS Code"     "$([ "$VSCODE_DETECTED" = true ] && echo '✓' || echo '–')" "$([ "$VSCODE_DETECTED" = true ] && echo '.vscode/mcp.json' || echo '(not configured)')"
printf "  %-15s %-10s %s\n" "Claude Code" "$([ "$CLAUDE_DETECTED" = true ] && echo '✓' || echo '–')" "$([ "$CLAUDE_DETECTED" = true ] && echo 'claude_mcp_config.json' || echo '(not configured)')"
printf "  %-15s %-10s %s\n" "Cursor"      "$([ "$CURSOR_DETECTED" = true ] && echo '✓' || echo '–')" "$([ "$CURSOR_DETECTED" = true ] && echo '.cursor/mcp.json' || echo '(not configured)')"

echo ""
echo "Next steps:"
echo "  1. Open narrator.config.yaml and set workspace_url"
echo "  2. Import scanner/modeling-readiness-scanner.ipynb into your Fabric workspace"
echo "  3. Run the scanner notebook to generate a findings artifact"
echo "  4. Restart your AI host to pick up the new MCP server registration"
echo ""
