#!/usr/bin/env pwsh
<#
.SYNOPSIS
    CI/CD Mutation Receipt Gate ? Omega v15
    "No mutation receipt = demotion."

.DESCRIPTION
    Verifies that every hardened tile in the Omega v15 kernel has a
    corresponding Stryker mutation receipt file (stryker_<tile>*.txt),
    AND that the score falls within the Goldilocks zone: [MinScore, 100).

    GOLDILOCKS DOCTRINE:
        score < MinScore (default 80) ? BLOCKED  (too weak, slop survives)
        score >= 100.0               ? BLOCKED  (epistemic overfit ?
                                                  tests are testing the
                                                  implementation, not the
                                                  behaviour; brittle and
                                                  untrustworthy)
        MinScore <= score < 100      ? PASS      (Goldilocks zone)

    100% is NOT a badge of honour. It is a red flag.
    From ai_confidence doctrine: 100 = epistemic arrogance, blocked.

    USAGE:
        pwsh -File scripts/check_mutation_receipts.ps1
        pwsh -File scripts/check_mutation_receipts.ps1 -Verbose
        pwsh -File scripts/check_mutation_receipts.ps1 -ReceiptsDir "./receipts"

    EXIT CODES:
        0 ? All tiles in Goldilocks zone. Promotion allowed.
        1 ? Missing receipt OR score out of Goldilocks zone. DEMOTION.

    HFO Omega v15 | PREY8 | Bronze layer
#>

param(
    [string]$ReceiptsDir = ".",
    [switch]$Verbose
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------- Tile Registry ----------------------------------------------------------------
# Each entry is a tile name. The script looks for stryker_<tile>*.txt
# MinScore: floor (default 80). Score below this = BLOCKED (slop survives).
# MaxScore: ceiling. Score >= this = BLOCKED (epistemic overfit).
#   Default MaxScore = 99.99 -- blocks 100%.
#   Set MaxScore = 100 only for trivial files with <20 mutants where 100%
#   is statistically inevitable (not suspicious). Requires a code comment
#   documenting WHY the file is exempt from the overfit cap.

$HARDENED_TILES = @(
    @{ Name = "event_bus";               MinScore = 80; MaxScore = 99.99; Receipt = "stryker_event_bus_final.txt" },
    @{ Name = "kalman_filter";           MinScore = 80; MaxScore = 99.99; Receipt = "stryker_kalman_filter_r1_2026-02-21.txt" },
    @{ Name = "plugin_supervisor";       MinScore = 80; MaxScore = 99.99; Receipt = "stryker_plugin_supervisor_r2_2026-02-21.txt" },
    @{ Name = "audio_engine_plugin";     MinScore = 80; MaxScore = 99.99; Receipt = "stryker_audio_engine_r2_2026-02-21.txt" },
    @{ Name = "symbiote_injector_plugin"; MinScore = 80; MaxScore = 99.99; Receipt = "stryker_symbiote_r1_2026-02-21.txt" },
    @{ Name = "gesture_fsm";             MinScore = 80; MaxScore = 99.99; Receipt = "stryker_gesture_fsm_r2_2026-02-21.txt" },
    @{ Name = "pal";                     MinScore = 80; MaxScore = 99.99; Receipt = "stryker_pal_final.txt" },
    @{ Name = "stillness_monitor_plugin"; MinScore = 80; MaxScore = 99.99; Receipt = "stryker_stillness_monitor_r1_2026-02-21.txt" },
    # wood_grain_tuning: MaxScore=100 (overfit cap WAIVED) -- 13 mutants total (25-line trivial class).
    # With so few mutants, 100% kill rate is statistically inevitable, not suspicious.
    @{ Name = "wood_grain_tuning";       MinScore = 80; MaxScore = 100;   Receipt = "stryker_wood_grain_r1_2026-02-21.txt" },
    @{ Name = "highlander_mutex_adapter"; MinScore = 80; MaxScore = 99.99; Receipt = "stryker_highlander_mutex_r1_2026-02-21.txt" },
    @{ Name = "hud_plugin";              MinScore = 80; MaxScore = 99.99; Receipt = "stryker_hud_plugin_r1_2026-02-21.txt" },
    @{ Name = "temporal_rollup";         MinScore = 80; MaxScore = 99.99; Receipt = "stryker_temporal_rollup_r1_2026-02-21.txt" }
)

# Tiles in the queue ? must have receipts before next CI/CD run
$QUEUED_TILES = @(
    # All tiles currently have receipts. Add new tiles here when work begins.
)

# ---------------------------------------------------------------- Helpers ----------------------------------------------------------------

function Find-Receipt {
    param([string]$TileName, [string]$SpecificReceipt)

    # 1. If a specific receipt filename is registered, check it first
    if ($SpecificReceipt) {
        $path = Join-Path $ReceiptsDir $SpecificReceipt
        if (Test-Path $path) { return $path }
    }

    # 2. Dynamic fallback: any file matching stryker_<tile>*.txt
    $pattern = "stryker_${TileName}*.txt"
    $found = Get-ChildItem -Path $ReceiptsDir -Filter $pattern -ErrorAction SilentlyContinue
    if ($found) { return $found[0].FullName }

    return $null
}

function Read-MutationScore {
    <#
    .SYNOPSIS
        Parses the mutation score from a Stryker clear-text receipt file.
        Returns [double] score, or -1 if the score cannot be parsed.

    .NOTES
        Stryker clear-text output contains a line like:
        "INFO MutationTestReportHelper Final mutation score of 82.09 is greater than..."
        We extract the float from that line as the canonical score.
    #>
    param([string]$ReceiptPath)

    $content = Get-Content $ReceiptPath -Raw -ErrorAction SilentlyContinue
    if (-not $content) { return -1 }

    # Primary: "Final mutation score of <score>"
    if ($content -match 'Final mutation score of (\d+\.\d+)') {
        return [double]$Matches[1]
    }

    # Fallback: table row "All files | <total> |" from progress output
    if ($content -match 'All files\s*\|\s*(\d+\.\d+)') {
        return [double]$Matches[1]
    }

    return -1
}

function Write-Status {
    param([string]$Symbol, [string]$Color, [string]$Message)
    Write-Host "$Symbol $Message" -ForegroundColor $Color
}

# ---------------------------------------------------------------- Main ----------------------------------------------------------------

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "|     HFO Omega v15 ? Mutation Receipt Gate                   |" -ForegroundColor Cyan
Write-Host "|     Goldilocks zone: [MinScore, 100)                        |" -ForegroundColor Cyan
Write-Host "|     100% = epistemic overfit. 100% is BLOCKED.              |" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

$allPassed = $true
$missingTiles = @()

# ---------------------------------------------------------------- Check hardened tiles (BLOCKING) ----------------------------------------------------------------
Write-Host "---------------------------------------------------------------- Hardened Tiles (BLOCKING) ----------------------------------------------------------------" -ForegroundColor White
foreach ($tile in $HARDENED_TILES) {
    $receipt = Find-Receipt -TileName $tile.Name -SpecificReceipt $tile.Receipt

    if (-not $receipt) {
        Write-Status "  [X]" "Red" "$($tile.Name.PadRight(30)) -> NO RECEIPT FOUND -- BLOCKED"
        $allPassed = $false
        $missingTiles += $tile.Name
        continue
    }

    $relPath = (Split-Path $receipt -Leaf)
    $score   = Read-MutationScore -ReceiptPath $receipt

    if ($score -lt 0) {
        # Could not parse score -- treat as missing
        Write-Status "  [?]" "Yellow" "$($tile.Name.PadRight(30)) -> $relPath (score unparseable -- check receipt format)"
        $allPassed = $false
        $missingTiles += $tile.Name
    } elseif ($score -gt $tile.MaxScore) {
        # Epistemic overfit -- score exceeds tile's MaxScore ceiling
        $cap = $tile.MaxScore
        Write-Status "  [OVERFIT]" "Red" "$($tile.Name.PadRight(30)) -> $relPath  [score: ${score}%] EPISTEMIC OVERFIT -- BLOCKED (MaxScore cap: ${cap}%)"
        $allPassed = $false
        $missingTiles += $tile.Name
    } elseif ($score -lt $tile.MinScore) {
        # Below Goldilocks floor
        Write-Status "  [X]" "Red" "$($tile.Name.PadRight(30)) -> $relPath  [score: ${score}%] BELOW FLOOR (min: $($tile.MinScore)%) -- BLOCKED"
        $allPassed = $false
        $missingTiles += $tile.Name
    } else {
        # Goldilocks zone: [MinScore, 100)
        Write-Status "  [OK]" "Green" "$($tile.Name.PadRight(30)) -> $relPath  [score: ${score}%]"
    }
}

Write-Host ""

# ---------------------------------------------------------------- Check queued tiles (WARNING only ? not yet blocking) ----------------------------------------------------------------
Write-Host "---------------------------------------------------------------- Queued Tiles (in-progress, warning only) ----------------------------------------------------------------" -ForegroundColor White
foreach ($tileName in $QUEUED_TILES) {
    $receipt = Find-Receipt -TileName $tileName -SpecificReceipt $null

    if ($receipt) {
        $relPath = (Split-Path $receipt -Leaf)
        Write-Status "  [OK]" "Green"  "$($tileName.PadRight(30)) -> $relPath"
    } else {
        Write-Status "  [~]" "Yellow" "$($tileName.PadRight(30)) -> pending Stryker run"
    }
}

Write-Host ""

# ---------------------------------------------------------------- Summary ----------------------------------------------------------------
if ($allPassed) {
    Write-Host "================================================================" -ForegroundColor Green
    Write-Host "  ?  ALL HARDENED TILES HAVE MUTATION RECEIPTS" -ForegroundColor Green
    Write-Host "      Promotion: ALLOWED" -ForegroundColor Green
    Write-Host "================================================================" -ForegroundColor Green
    Write-Host ""
    exit 0
} else {
    Write-Host "================================================================" -ForegroundColor Red
    Write-Host "  [FAIL]  MUTATION GATE FAILED" -ForegroundColor Red
    Write-Host "      Blocked tiles: $($missingTiles -join ', ')" -ForegroundColor Red
    Write-Host "      Reason may be: no receipt, BELOW FLOOR, or EPISTEMIC OVERFIT" -ForegroundColor Red
    Write-Host "      Promotion: BLOCKED" -ForegroundColor Red
    Write-Host "================================================================" -ForegroundColor Red
    Write-Host ""
    exit 1
}
