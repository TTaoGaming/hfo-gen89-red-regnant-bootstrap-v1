**Eval Orchestrator — Quick Start**

Purpose: run an automated Perceive → Eval → Yield loop and persist artifacts for P6 assimilation.

Files:
- `hfo_eval_orchestrator.py` — main orchestrator (0_bronze/resources)
- `orchestrator_outputs/` — auto-created folder where logs and recaps are stored

Simple run (one-off):
```powershell
python hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_eval_orchestrator.py --model qwen2.5:7b --limit 5 --once
```

Run continuously (every hour):
```powershell
python hfo_gen_89_hot_obsidian_forge/0_bronze/resources/hfo_eval_orchestrator.py --model qwen2.5:7b --limit 5 --interval 3600
```

Windows service / scheduled task:
- Use `nssm` to install the Python command as a service, or use Task Scheduler to run the same command at system startup and on failure.
- See `windows_service_install.ps1` for an example of scheduled-task creation.

Notes:
- The orchestrator expects `hfo_perceive.py`, `prey8_eval_harness.py`, and `hfo_yield.py` to be present in the same folder.
- Orchestrator writes logs to `0_bronze/resources/orchestrator_outputs` and uses PREY8 bookends so every run is recorded in the SSOT.
