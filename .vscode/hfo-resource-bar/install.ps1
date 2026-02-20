# HFO Resource Bar — one-time extension install
# Run from hfoDev workspace root: .\.vscode\hfo-resource-bar\install.ps1
#
# Requires Node.js / npm on PATH. Packages the extension as a VSIX
# and installs it into VS Code. Re-run to update after code changes.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$extDir = Join-Path $PSScriptRoot ""     # same dir as this script
Push-Location $extDir

try {
    Write-Host "==> Packaging HFO Resource Bar extension..." -ForegroundColor Cyan
    # @vscode/vsce via npx — no need for a global install
    npx --yes "@vscode/vsce" package --no-dependencies --allow-missing-repository --skip-license --out "hfo-resource-bar.vsix"
    if ($LASTEXITCODE -ne 0) { throw "vsce package failed" }

    Write-Host "==> Installing into VS Code..." -ForegroundColor Cyan
    code --install-extension "hfo-resource-bar.vsix" --force
    if ($LASTEXITCODE -ne 0) { throw "code --install-extension failed" }

    Write-Host "==> Done. Reload VS Code window (Ctrl+Shift+P -> Reload Window) to activate." -ForegroundColor Green
} finally {
    Pop-Location
}
