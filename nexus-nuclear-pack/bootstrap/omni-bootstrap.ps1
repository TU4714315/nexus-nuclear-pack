# omni-bootstrap.ps1
# Creates a clean workspace structure (if missing) and opens VS Code workspace.
# This pack is a SPEC + SKELETON (no runtime binary included).

$ErrorActionPreference = "Stop"

function Ensure-Dir($p) { if (!(Test-Path $p)) { New-Item -ItemType Directory -Path $p | Out-Null } }

$root = (Resolve-Path ".").Path
Write-Host "Nexus Nuclear Pack bootstrap in: $root"

Ensure-Dir ".vscode"
Ensure-Dir "config"
Ensure-Dir "catalog"
Ensure-Dir "wit"
Ensure-Dir "db"
Ensure-Dir "bootstrap"

Write-Host "✅ Folders ensured."

if (Get-Command code -ErrorAction SilentlyContinue) {
  Write-Host "Opening VS Code workspace..."
  code "nexus-nuclear.code-workspace"
} else {
  Write-Host "VS Code CLI not found. Open the folder manually in VS Code."
}

Write-Host "Done."
