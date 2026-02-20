<#
diagnose_gpu_npu.ps1

Quick diagnostics for GPU / NPU readiness on Windows. Checks:
- GPU name and driver version
- Presence of Intel Level Zero / oneAPI runtime files
- Basic Ollama API reachability (/api/ps and /api/tags)
- Python environment package checks (delegates to diagnose_python_env.py)

Run:
  powershell -ExecutionPolicy Bypass -File .\diagnose_gpu_npu.ps1
#>

Write-Host "=== HFO GPU / NPU Diagnostic ===" -ForegroundColor Cyan

Write-Host "\n-- Video controllers --" -ForegroundColor Yellow
Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, @{Name='VRAM_GB';Expression={($_.AdapterRAM/1GB).ToString('F1')}}, PNPDeviceID | Format-List

Write-Host "\n-- Search for Level Zero / oneAPI runtime files --" -ForegroundColor Yellow
$found = $false
foreach ($p in @("C:\Program Files","C:\Program Files (x86)","C:\intel")) {
    if (Test-Path $p) {
        $f = Get-ChildItem -Path $p -Filter "level_zero.dll" -Recurse -ErrorAction SilentlyContinue -Force -Depth 3 | Select-Object -First 1
        if ($f) { Write-Host "Found level_zero.dll at: $($f.FullName)"; $found = $true; break }
    }
}
if (-not $found) { Write-Host "level_zero.dll not found in common locations." -ForegroundColor DarkYellow }

Write-Host "\n-- Ollama API check (http://127.0.0.1:11434) --" -ForegroundColor Yellow
try {
    $ps = Invoke-RestMethod -Uri http://127.0.0.1:11434/api/ps -Method Get -TimeoutSec 5
    Write-Host "Ollama /api/ps responded." -ForegroundColor Green
    if ($ps) { $ps | ConvertTo-Json -Depth 3 }
} catch {
    Write-Host "Ollama /api/ps did not respond: $_" -ForegroundColor Red
}

try {
    $tags = Invoke-RestMethod -Uri http://127.0.0.1:11434/api/tags -Method Get -TimeoutSec 5
    Write-Host "Ollama /api/tags responded." -ForegroundColor Green
    if ($tags) { $tags | ConvertTo-Json -Depth 3 }
} catch {
    Write-Host "Ollama /api/tags did not respond: $_" -ForegroundColor Red
}

Write-Host "\n-- Python environment checks --" -ForegroundColor Yellow
try {
    & python - <<'PY'
import json, sys
from importlib import util
pkgs = ["ollama","openvino","intel_extension_for_pytorch","transformers","accelerate","torch"]
out = {}
for p in pkgs:
    spec = util.find_spec(p)
    if spec is None:
        out[p] = None
    else:
        try:
            mod = __import__(p)
            out[p] = getattr(mod, '__version__', str(mod))
        except Exception as e:
            out[p] = f"import_error:{e}"
print(json.dumps(out, indent=2))
PY
} catch {
    Write-Host "Python check failed: $_" -ForegroundColor Red
}

Write-Host "\nDiagnostic complete. If you want, run diagnose_python_env.py for a JSON report." -ForegroundColor Cyan
