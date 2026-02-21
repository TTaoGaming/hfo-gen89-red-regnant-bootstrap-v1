# HFO Gen89 — Expand Windows Pagefile to 20 GB / 32 GB
# Run this script AS ADMINISTRATOR (launched automatically by _housekeeping.py)
# Requires restart to take full effect.

$ErrorActionPreference = "Stop"

try {
    # Disable auto-management
    $cs = Get-WmiObject Win32_ComputerSystem -EnableAllPrivileges
    $cs.AutomaticManagedPagefile = $false
    $null = $cs.Put()
    Write-Host "[1/3] Auto-managed pagefile: DISABLED"

    # Set explicit sizes: 20 GB initial, 32 GB max
    $targetInit = 20480   # 20 GB
    $targetMax  = 32768   # 32 GB

    $pf = Get-WmiObject -Query "SELECT * FROM Win32_PageFileSetting" -ErrorAction SilentlyContinue
    if ($pf) {
        $pf.InitialSize = $targetInit
        $pf.MaximumSize = $targetMax
        $null = $pf.Put()
        Write-Host "[2/3] Updated existing pagefile: InitialSize=$targetInit MB, MaximumSize=$targetMax MB"
    } else {
        $null = Set-WmiInstance -Class Win32_PageFileSetting -Arguments @{
            Name        = "C:\pagefile.sys"
            InitialSize = $targetInit
            MaximumSize = $targetMax
        }
        Write-Host "[2/3] Created pagefile setting: InitialSize=$targetInit MB, MaximumSize=$targetMax MB"
    }

    # Verify
    $verify = Get-WmiObject -Query "SELECT * FROM Win32_PageFileSetting"
    Write-Host "[3/3] Verification: $($verify.Name) Init=$($verify.InitialSize) Max=$($verify.MaximumSize)"
    Write-Host ""
    Write-Host "SUCCESS: Pagefile set to 20 GB initial / 32 GB max."
    Write-Host "A restart is needed for the new size to take effect."
    Write-Host "(Current session will continue using the old size.)"
} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
    Write-Host "Make sure you are running as Administrator."
}

Write-Host ""
Write-Host "Press any key to close..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
