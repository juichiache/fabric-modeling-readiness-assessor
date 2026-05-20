#!/usr/bin/env pwsh
<#
.SYNOPSIS
Bootstrap the Modeling Readiness Assessor narrator MCP server.

.DESCRIPTION
1. Installs narrator Python dependencies via pip.
2. Probes for known AI host config directories (VS Code, Claude Code, Cursor).
3. Writes host-specific MCP registration files.
4. Prints a summary table — no admin elevation required.

.EXAMPLE
.\bootstrap.ps1
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = $PSScriptRoot

Write-Host ""
Write-Host "=== Modeling Readiness Assessor — Bootstrap ===" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# Step 1: Install narrator Python dependencies
# ---------------------------------------------------------------------------
Write-Host "[1/3] Installing narrator Python dependencies..." -ForegroundColor Yellow

$narratorPkg = Join-Path $RepoRoot "narrator\mcp_server"
if (Test-Path $narratorPkg) {
    pip install -e $narratorPkg --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Error "pip install failed. Ensure Python and pip are available in PATH."
    }
    Write-Host "      ✓ narrator dependencies installed" -ForegroundColor Green
} else {
    Write-Warning "narrator/mcp_server not found at $narratorPkg — skipping dependency install."
}

# ---------------------------------------------------------------------------
# Step 2: Probe for AI host config directories
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[2/3] Probing for AI hosts..." -ForegroundColor Yellow

$hosts = [ordered]@{
    "VS Code"     = @{ Probe = "$env:USERPROFILE\.vscode"; Config = ".vscode\mcp.json"; Template = ".vscode\mcp.json" }
    "Claude Code" = @{ Probe = "$env:USERPROFILE\.claude"; Config = "claude_mcp_config.json"; Template = "claude_mcp_config.json" }
    "Cursor"      = @{ Probe = "$env:USERPROFILE\.cursor"; Config = ".cursor\mcp.json"; Template = ".cursor\mcp.json" }
}

$results = [ordered]@{}
foreach ($host in $hosts.GetEnumerator()) {
    $detected = Test-Path $host.Value.Probe
    $results[$host.Key] = $detected
    $icon = if ($detected) { "✓" } else { "–" }
    $status = if ($detected) { "detected" } else { "not detected" }
    Write-Host "      $icon $($host.Key): $status" -ForegroundColor $(if ($detected) { "Green" } else { "Gray" })
}

# ---------------------------------------------------------------------------
# Step 3: Write MCP registration files for detected hosts
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[3/3] Writing MCP registration files..." -ForegroundColor Yellow

foreach ($host in $hosts.GetEnumerator()) {
    if ($results[$host.Key]) {
        $src = Join-Path $RepoRoot $host.Value.Template
        $dst = Join-Path $RepoRoot $host.Value.Config
        if (Test-Path $src) {
            # Ensure parent directory exists
            $dstDir = Split-Path $dst -Parent
            if (-not (Test-Path $dstDir)) { New-Item -ItemType Directory -Force -Path $dstDir | Out-Null }
            Copy-Item -Path $src -Destination $dst -Force
            Write-Host "      ✓ $($host.Key): wrote $($host.Value.Config)" -ForegroundColor Green
        } else {
            Write-Warning "Template not found: $src — skipping $($host.Key)"
        }
    }
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=== Bootstrap Summary ===" -ForegroundColor Cyan
Write-Host ""
Write-Host ("  {0,-15} {1,-12} {2}" -f "Host", "Detected", "MCP Config") -ForegroundColor White
Write-Host ("  {0,-15} {1,-12} {2}" -f "----", "--------", "----------") -ForegroundColor Gray
foreach ($host in $hosts.GetEnumerator()) {
    $detected = $results[$host.Key]
    $icon = if ($detected) { "✓" } else { "–" }
    $configPath = if ($detected) { $host.Value.Config } else { "(not configured)" }
    Write-Host ("  {0,-15} {1,-12} {2}" -f $host.Key, $icon, $configPath) -ForegroundColor $(if ($detected) { "Green" } else { "Gray" })
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Open narrator.config.yaml and set workspace_url" -ForegroundColor Gray
Write-Host "  2. Import scanner/modeling-readiness-scanner.ipynb into your Fabric workspace" -ForegroundColor Gray
Write-Host "  3. Run the scanner notebook to generate a findings artifact" -ForegroundColor Gray
Write-Host "  4. Restart your AI host to pick up the new MCP server registration" -ForegroundColor Gray
Write-Host ""
