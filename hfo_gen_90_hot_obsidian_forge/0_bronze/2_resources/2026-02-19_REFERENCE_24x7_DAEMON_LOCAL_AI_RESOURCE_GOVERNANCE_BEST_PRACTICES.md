---
schema_id: hfo.gen89.reference.v1
medallion_layer: bronze
mutation_score: 0
hive: V
diataxis_type: reference
port_affinity: [P4, P5, P7, P6]
created: 2026-02-19
title: "24/7 Local AI Daemon Operations with Resource Governance — Best Practices"
bluf: >
  Comprehensive reference for running a 24/7 local AI daemon stack on a resource-constrained
  system (16 GB VRAM Intel Arc 140V, 32 GB RAM, 8-core CPU). Synthesized from 14 months of
  empirical operation across 89 generations and 10,000+ stigmergy events. Covers 8 sections:
  System Inventory, VRAM Budget Tiers, Daemon Priority Stack, .env Configuration Matrix,
  Resource Governance Integration, Crash Recovery, Stigmergy Observability, and Anti-Patterns.
  Core finding: structural enforcement (daemons, schema gates, VRAM budget ceilings) survives
  24/7 operation; cooperative enforcement (instructions, temperature, prompts) fails within
  hours under sustained load. Every recommendation is backed by stigmergy evidence.
tags: [24x7, daemon, resource-governance, best-practices, vram-budget, crash-recovery,
      stigmergy, observability, anti-patterns, local-ai, ollama, intel-arc, bronze,
      p4, p5, p6, p7, reference]
sources:
  - "Doc 179 — Complete Control Surface Taxonomy (7 tiers, 31 vectors)"
  - "Doc 316 — What Actually Works: AI Swarm Governance (empirical inventory)"
  - "hfo_resource_governance.py (827L, RegimeDetector, SampleBuffer, 6 regimes)"
  - "hfo_resource_monitor.py (752L, ResourceMonitor, SlotManager, ResourcePressure)"
  - "hfo_sandbox_launcher.py (1394L, 4-phase boot, P5-gates-P2, watchdog)"
  - "hfo_background_daemon.py (Gemini-backed enrichment scheduler)"
  - "Stigmergy events 10678-10695 (resource snapshots, regime detections)"
  - "14 months empirical operator data (Jan 2025 → Feb 2026, 89 generations)"
---

# 24/7 Local AI Daemon Operations with Resource Governance — Best Practices

> **The one-sentence version**: Run the immune system (P5) before the creator (P2),
> budget VRAM like money you can't borrow, use ring buffers not point-in-time checks,
> log every regime transition to stigmergy, and assume every daemon session WILL crash.

---

## §1 — System Inventory & Hardware Constraints

Know your compute surfaces. Every budget decision flows from these hard numbers.

| Surface | Capacity | Notes |
|---------|----------|-------|
| **GPU VRAM** | 16 GB (Intel Arc 140V) | Shared between ALL Ollama models. No overcommit. |
| **System RAM** | 32 GB | Shared with OS, VS Code, browser, Git. Effective headroom: ~24 GB |
| **CPU** | 8 cores (Intel Core Ultra 7) | Ollama uses all cores during inference. Reserve 2 for OS. |
| **NPU** | Intel AI Boost (11 TOPS) | OpenVINO only. Good for embeddings, not LLM inference. |
| **Disk** | NVMe SSD | SSOT database (~150 MB). Model cache (~30 GB). |

### Hard Limits (Non-Negotiable)

| Constraint | Value | What Happens At Breach |
|------------|-------|----------------------|
| VRAM ceiling | 16.0 GB | Ollama silently CPU-offloads → inference 10-100× slower |
| RAM critical | < 2 GB free | Windows pagefile thrash → entire system unresponsive |
| CPU sustained | > 90% for > 5 min | Thermal throttling on laptop form factor |
| SSOT write lock | SQLite WAL mode | Concurrent readers OK, single writer. Use `busy_timeout=5000` |

### Empirical Observations (from Stigmergy Trail)

- **RAM 96%, VRAM 13.2/12 GB budget**: System entered sustained THROTTLED regime
  when both `gemma3:4b` (4.0 GB) + `gemma3:12b` (9.2 GB) were loaded simultaneously.
- **RAM 80%, VRAM 13.8 GB**: ELEVATED pressure with `qwen2.5-coder:7b` (4.6 GB) +
  `gemma3:12b` (9.2 GB).
- **CPU 77-90%**: Normal during active inference. Spikes above 85% sustained trigger
  worker pause in resource_monitor.py.

---

## §2 — VRAM Budget Tiers

VRAM is the scarcest resource. Budget it in discrete tiers — never "see what fits."

### Model VRAM Estimates (from `resource_monitor.py MODEL_VRAM_ESTIMATES`)

| Model | VRAM (GB) | Use Case | Tier |
|-------|-----------|----------|------|
| `lfm2.5-thinking:1.2b` | 1.0 | Ultra-lightweight reasoning | T1 |
| `qwen2.5:3b` | 2.0 | Fast classification, tagging | T1 |
| `granite4:3b` | 2.0 | Fast classification | T1 |
| `llama3.2:3b` | 2.2 | General small tasks | T1 |
| `gemma3:4b` | 3.0 | Standard daemon workhorse | T2 |
| `qwen2.5-coder:7b` | 5.0 | Code generation / review | T2 |
| `qwen3:8b` | 5.5 | Mid-range reasoning | T2 |
| `deepseek-r1:8b` | 5.5 | Mid-range reasoning | T2 |
| `gemma3:12b` | 8.0 | High-quality generation | T3 |
| `phi4:14b` | 9.5 | Highest local intelligence | T3 |
| `qwen3:30b-a3b` | 3.5 | MoE — only active params loaded | T2-special |
| `deepseek-r1:32b` | 20.0 | **EXCEEDS 16 GB** — CPU offload only | BANNED |

### Budget Allocation Tiers

**Tier A — Maximum Intelligence (single-daemon mode)**

| Slot | Model | VRAM | Purpose |
|------|-------|------|---------|
| P5 IMMUNIZE | `phi4:14b` | 9.5 GB | Immune system (Ring 0/1/2 gates) |
| P2 SHAPE | `gemma3:4b` | 3.0 GB | Lightweight creation |
| — | — | 12.5 GB total | 3.5 GB headroom |

Best for: Interactive development with safety spine active.

**Tier B — Balanced Multi-Daemon**

| Slot | Model | VRAM | Purpose |
|------|-------|------|---------|
| P5 IMMUNIZE | `gemma3:12b` | 8.0 GB | Good immune system |
| P2 SHAPE | `gemma3:4b` | 3.0 GB | Creation |
| P6 ASSIMILATE (if needed) | shares P2 model | 0 GB extra | Swarm enrichment |
| — | — | 11.0 GB total | 5.0 GB headroom for P4/prospector |

Best for: Background enrichment + safety spine.

**Tier C — Lightweight Swarm**

| Slot | Model | VRAM | Purpose |
|------|-------|------|---------|
| P6 ASSIMILATE | `gemma3:4b` | 3.0 GB | Swarm enrichment |
| P4 DISRUPT | `gemma3:4b` | 0 GB (shared) | Song prospector |
| — | — | 3.0 GB total | Maximum headroom for operator work |

Best for: Unattended overnight enrichment.

**Tier D — Operator-Only (daemons paused)**

All models unloaded. 16 GB free for operator's manual Ollama use.

### RULE: Never Load Two T3 Models

Loading `phi4:14b` (9.5 GB) + `gemma3:12b` (8.0 GB) = 17.5 GB > 16 GB ceiling.
This is the #1 empirical VRAM breach cause: two high-intelligence models competing.

If you need both: load one, use it, unload it (`keep_alive: 0s`), load the other.

---

## §3 — Daemon Priority Stack

When resources are constrained, shed load in this order (lowest priority first):

| Priority | Daemon | Port | Action When Constrained |
|----------|--------|------|------------------------|
| 1 (LOWEST) | Song Prospector | P4 | Pause first. Creative mining is deferrable. |
| 2 | Chimera Loop | P2 | Pause second. ONLY if P5 is still healthy. |
| 3 | Background Daemon | P7 | Pause enrichment. SSOT doesn't degrade. |
| 4 | Kraken Swarm | P6 | Reduce worker count. Don't kill entirely. |
| 5 | Singer Daemon | P4 | Keep running — no LLM, pure SSOT scan. Zero VRAM. |
| 6 | Resource Governance | P6 | Keep running — monitoring IS the governance. |
| 7 (HIGHEST) | Pyre Praetorian | P5 | **NEVER pause.** Immune system is the gate. |

### The Safety Spine Invariant

```
INVARIANT: P2 SHAPE cannot run if P5 IMMUNIZE is not HEALTHY.
           P5 down → P2 paused. P5 recovered → P2 resumes.
           This is structural, not cooperative. The watchdog enforces it.
```

This is implemented in `sandbox_launcher.py` `_watchdog_loop()`:
- Every 30 seconds, checks P5 state
- If P5 ≠ HEALTHY and P2 = HEALTHY → terminate P2, set PAUSED
- If P5 = HEALTHY and P2 = PAUSED → reboot P2

### Boot Order (Fail-Closed, Order-Dependent)

```
Phase 0: Preflight  — Check VRAM, SSOT, P6 health
Phase 1: P5 IMMUNIZE boots FIRST
Phase 2: P4 DISRUPT boots SECOND (Singer + optional Prospector)
Phase 3: P2 SHAPE boots LAST (only if P5 healthy)
Phase 4: Watchdog monitors continuously
```

Reverse for shutdown: `P2 → P4 → P5` (creator stops first, immune system last).

---

## §4 — .env Configuration Matrix

All daemon configuration should be centralized in `.env` with typed defaults.
Current state: 20+ env vars scattered across 4 files with hardcoded defaults.

### Master .env Template (Recommended)

```dotenv
# ── Identity ──────────────────────────────
HFO_GENERATION=89
HFO_OPERATOR=TTAO
HFO_HIVE=V

# ── Paths ─────────────────────────────────
HFO_FORGE=hfo_gen_89_hot_obsidian_forge
HFO_SSOT_DB=hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite

# ── Feature Flags ─────────────────────────
HFO_FTS_ENABLED=true
HFO_PRECOMMIT_ENABLED=true
HFO_STRICT_MEDALLION=true

# ── GPU / Ollama ──────────────────────────
OLLAMA_VULKAN=1
OLLAMA_FLASH_ATTENTION=1
OLLAMA_HOST=http://127.0.0.1:11434

# ── VRAM Budget ───────────────────────────
HFO_VRAM_BUDGET_GB=12           # Soft budget for daemon allocation
HFO_VRAM_CEILING_GB=16          # Hard ceiling (hardware limit)
HFO_VRAM_RESERVE_GB=2           # Keep free for operator headroom

# ── Per-Port Model Assignment ─────────────
P5_OLLAMA_MODEL=phi4:14b        # Immune system — high intelligence
P2_OLLAMA_MODEL=gemma3:4b       # Creation — lightweight, P5 gates it
P4_OLLAMA_MODEL=gemma3:4b       # Prospector — lightweight mining
P6_OLLAMA_MODEL=gemma3:4b       # Swarm enrichment

# ── Daemon Enable/Disable ────────────────
HFO_DAEMON_P5_ENABLED=true      # Pyre Praetorian (immune system)
HFO_DAEMON_P4_SINGER_ENABLED=true  # Singer (no LLM, pure scan)
HFO_DAEMON_P4_PROSPECTOR_ENABLED=false  # Song Prospector (VRAM intensive)
HFO_DAEMON_P2_ENABLED=true      # Chimera Loop
HFO_DAEMON_P6_SWARM_ENABLED=true # Kraken Swarm
HFO_DAEMON_P7_BACKGROUND_ENABLED=false  # Background enrichment

# ── Resource Governance ───────────────────
HFO_GOV_SAMPLE_INTERVAL=10      # Sample every N seconds
HFO_GOV_WINDOW_SIZE=60          # Ring buffer size (samples)
HFO_GOV_HEARTBEAT=300           # Heartbeat interval (seconds)
HFO_GOV_CPU_OVER=80             # CPU over-utilization threshold (%)
HFO_GOV_RAM_OVER=90             # RAM over-utilization threshold (%)
HFO_GOV_CPU_UNDER=15            # CPU under-utilization threshold (%)
HFO_GOV_RAM_UNDER=50            # RAM under-utilization threshold (%)
HFO_GOV_REGIME_PCT=70           # % of window that must match for regime
HFO_GOV_COOLDOWN=300            # Seconds between same event type

# ── Resource Monitor (Kraken) ─────────────
HFO_CPU_THROTTLE=85             # Pause workers above this CPU %
HFO_CPU_RESUME=70               # Resume workers below this CPU %
HFO_RAM_THROTTLE_GB=2           # Pause if free RAM < this GB
HFO_RAM_RESUME_GB=4             # Resume if free RAM > this GB
HFO_SENSE_INTERVAL=5            # Resource poll interval (seconds)
HFO_YIELD_CHECK=15              # Stigmergy yield-request check interval

# ── NPU ───────────────────────────────────
HFO_NPU_ENABLED=true            # Enable NPU embedding worker
HFO_NPU_MODEL=bge-small-en      # Embedding model for OpenVINO
HFO_NPU_BATCH_SIZE=32           # Batch size for NPU inference
```

### Env Var Ownership Map

| File | Vars Read | Vars That Should Migrate to .env |
|------|-----------|----------------------------------|
| `resource_governance.py` | 8 vars (`HFO_GOV_*`, `HFO_VRAM_BUDGET_GB`) | Already env-aware ✓ |
| `resource_monitor.py` | 7 vars (`HFO_CPU_*`, `HFO_RAM_*`, `HFO_VRAM_*`) | Already env-aware ✓ |
| `sandbox_launcher.py` | 2 vars (`P5_OLLAMA_MODEL`, `P2_OLLAMA_MODEL`) | Needs full set ✗ |
| `background_daemon.py` | 0 vars | Hardcoded intervals ✗ |
| `hfo_p6_kraken_swarm.py` | inherits from resource_monitor | OK ✓ |

---

## §5 — Resource Governance Integration Patterns

Two architectures exist. Choose based on operational mode.

### Pattern A: Standalone Daemon (Current)

```
┌─────────────────┐     ┌──────────────────┐
│ resource_        │     │ stigmergy_events │
│ governance.py   │ ──→ │ table (SSOT)     │
│ (async loop)    │     │                  │
└─────────────────┘     └──────────────────┘
         ↑                       ↓
    psutil + Ollama API     Other daemons READ
                            events and REACT
```

**Pros**: Simple, isolated, crash doesn't affect other daemons.
**Cons**: READ-ONLY advisory — no one actually reacts to events automatically.
**Use when**: Running governance monitoring alongside manual operations.

### Pattern B: Embedded in Sandbox Watchdog (Recommended for 24/7)

```
┌──────────────────────────────────────────────┐
│  sandbox_launcher.py                         │
│  ┌──────────────┐  ┌──────────────────────┐ │
│  │ _watchdog_   │  │ ResourceGovernor     │ │
│  │ loop()       │──│ (SampleBuffer +      │ │
│  │ (30s cycle)  │  │  RegimeDetector)     │ │
│  └──────────────┘  └──────┬───────────────┘ │
│                            │ REACTIVE ACTIONS │
│  P5: NEVER pause ─────────┤                  │
│  P4_Singer: keep ──────── ├─ if cpu_over:    │
│  P6: reduce workers ──────┤   pause P2 → P4  │
│  P2: pause if needed ─────┤   → P6 workers   │
│  P4_Prospector: first off ┤ if vram_breach:  │
│                            │   ollama unload  │
│                            │   lowest-priority│
│                            │   model          │
└──────────────────────────────────────────────┘
```

**Pros**: Governor IS the watchdog — reactive, structural, can't be ignored.
**Cons**: Coupling risk — governor bug could crash the supervisor.
**Use when**: 24/7 unattended operation with autonomous resource management.

### Integration Recipe (Pattern B)

```python
# Inside sandbox_launcher.py, extend _watchdog_loop():

class ResourceGovernor:
    """Embedded into watchdog for reactive resource management."""
    
    def __init__(self, supervisor: SandboxSupervisor):
        self.supervisor = supervisor
        self.buffer = SampleBuffer(max_size=60)
        self.detector = RegimeDetector()
    
    def check_and_react(self) -> list[str]:
        """Sample, detect regimes, take action. Returns list of actions taken."""
        sample = self._sense()
        self.buffer.add(sample)
        
        if len(self.buffer) < 10:
            return []
        
        actions = []
        regimes = self.detector.analyze(self.buffer)
        
        for regime_event in regimes:
            regime = regime_event["data"]["regime"]
            
            if regime == "vram_breach":
                # Unload lowest-priority model
                actions += self._shed_vram()
            elif regime == "cpu_over":
                # Pause P2, then P4 Prospector
                actions += self._pause_for_cpu()
            elif regime == "ram_over":
                # Reduce P6 worker concurrency
                actions += self._reduce_workers()
            elif regime == "cpu_under":
                # Scale up — enable paused daemons
                actions += self._scale_up()
        
        return actions
```

### The 6 Regimes and Their Reactive Actions

| Regime | Trigger | Reactive Action | Priority Model Shed Order |
|--------|---------|----------------|--------------------------|
| `cpu_over` | CPU > 80% for 70% of window | Pause P2 → P4_Prospector → reduce P6 | — |
| `ram_over` | RAM > 90% for 70% of window | Unload idle models, reduce batch sizes | — |
| `vram_breach` | VRAM > budget for 70% of window | Unload lowest-priority model | P4_Prospector → P2 → P6 |
| `cpu_under` | CPU < 15% for 70% of window | Enable paused daemons, increase workers | — |
| `ram_under` | RAM < 50% for 70% of window | Load additional models, increase batch | — |
| `npu_idle` | NPU available + unused for 70% of window | Start NPU embedding worker | — |

---

## §6 — Crash Recovery & Durability

### Assume Every Session WILL Crash

Empirical evidence: 8 orphaned PREY8 sessions in a single day (2026-02-19).
MCP server restarts, Ollama OOM, VS Code reloads, laptop sleep/wake — all cause
session loss. Design for it.

### State Persistence Pattern

```python
# Every daemon should persist state to a .json file:
STATE_FILE = HFO_ROOT / ".hfo_{daemon_name}_state.json"

# Save state periodically (every heartbeat):
def save_state(self):
    state = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "total_samples": self._total_samples,
        "regimes": self.detector.get_status(),
    }
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# On startup, recover from state file:
def recover_state(self):
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return None
```

### Crash Recovery Checklist

| Step | Action | Command |
|------|--------|---------|
| 1 | Check what's running | `Get-Process python* | Format-Table Id,CPU,WorkingSet,CommandLine` |
| 2 | Check Ollama models | `ollama ps` |
| 3 | Check VRAM usage | `python hfo_resource_governance.py --sample` |
| 4 | Kill zombie daemons | `Get-Process python* | Where-Object {$_.CPU -gt 100} | Stop-Process` |
| 5 | Unload all models | `python hfo_sandbox_launcher.py --force-unload` |
| 6 | Check SSOT health | `python hfo_perceive.py` |
| 7 | Check orphaned sessions | `prey8_detect_memory_loss` (via MCP) |
| 8 | Restart clean | `python hfo_sandbox_launcher.py --kill-existing --force-unload` |

### Auto-Restart Pattern (Windows Task Scheduler)

```xml
<!-- Create task: HFO_Sandbox_Watchdog -->
<!-- Trigger: On startup + every 30 minutes (restart if not running) -->
<!-- Action: powershell.exe -File hfo_sandbox_watchdog.ps1 -->
```

```powershell
# hfo_sandbox_watchdog.ps1
$sandbox = Get-Process python* | Where-Object {
    $_.CommandLine -match "hfo_sandbox_launcher"
}
if (-not $sandbox) {
    Write-Output "$(Get-Date) — Sandbox not running. Restarting..."
    Start-Process python -ArgumentList "hfo_sandbox_launcher.py" `
        -WorkingDirectory "C:\hfoDev\hfo_gen_89_hot_obsidian_forge\0_bronze\resources" `
        -WindowStyle Hidden
}
```

### Ollama Model Persistence

Ollama models auto-unload after `keep_alive` (default: 5 minutes).
For 24/7 operation, set explicitly:

```bash
# In daemon code — keep model loaded indefinitely:
ollama run phi4:14b --keepalive -1

# Or via API:
{"model": "phi4:14b", "keep_alive": -1}  # Never unload

# To explicitly unload (VRAM reclaim):
{"model": "phi4:14b", "keep_alive": "0s"}  # Unload immediately
```

**Best practice**: Set `keep_alive: -1` for P5 (always need immune system).
Set `keep_alive: "5m"` for P2/P4 (auto-unload when idle to free VRAM).

---

## §7 — Stigmergy Observability

### Essential Monitoring Queries

```sql
-- 1. Current daemon health (last heartbeat per source)
SELECT source, MAX(timestamp) as last_seen, 
       COUNT(*) as total_events
FROM stigmergy_events
WHERE timestamp > datetime('now', '-1 hour')
GROUP BY source
ORDER BY last_seen DESC;

-- 2. Active resource regimes
SELECT event_type, timestamp, 
       json_extract(data_json, '$.data.regime') as regime,
       json_extract(data_json, '$.data.recommendation') as action
FROM stigmergy_events
WHERE event_type LIKE 'hfo.gen89.governance.%'
ORDER BY timestamp DESC LIMIT 10;

-- 3. VRAM breach history
SELECT timestamp,
       json_extract(data_json, '$.data.avg_vram_gb') as vram_gb,
       json_extract(data_json, '$.data.loaded_models') as models
FROM stigmergy_events
WHERE event_type = 'hfo.gen89.governance.budget_breach'
ORDER BY timestamp DESC LIMIT 20;

-- 4. Sandbox daemon deaths
SELECT timestamp, subject,
       json_extract(data_json, '$.data.port_key') as port,
       json_extract(data_json, '$.data.exit_code') as exit_code
FROM stigmergy_events
WHERE event_type = 'hfo.gen89.sandbox.daemon_death'
ORDER BY timestamp DESC LIMIT 20;

-- 5. Memory loss trail (orphaned PREY8 sessions)
SELECT timestamp,
       json_extract(data_json, '$.orphaned_perceive_nonce') as nonce,
       json_extract(data_json, '$.phase_at_loss') as phase,
       json_extract(data_json, '$.orphaned_probe') as probe
FROM stigmergy_events
WHERE event_type LIKE '%memory_loss%'
ORDER BY timestamp DESC LIMIT 20;

-- 6. Resource pressure timeline (last hour)
SELECT timestamp,
       json_extract(data_json, '$.data.cpu_pct') as cpu,
       json_extract(data_json, '$.data.ram_pct') as ram,
       json_extract(data_json, '$.data.vram_used_gb') as vram,
       json_extract(data_json, '$.data.pressure') as pressure
FROM stigmergy_events
WHERE event_type = 'hfo.gen89.resource.snapshot'
  AND timestamp > datetime('now', '-1 hour')
ORDER BY timestamp DESC;

-- 7. Swarm heartbeat (worker status)
SELECT timestamp,
       json_extract(data_json, '$.data.resources.pressure') as pressure,
       json_extract(data_json, '$.data.resources.active_workers') as workers,
       json_extract(data_json, '$.data.resources.paused') as paused,
       json_extract(data_json, '$.data.progress.enrichment_pct.bluf') as bluf_pct
FROM stigmergy_events
WHERE event_type = 'hfo.gen89.swarm.heartbeat'
ORDER BY timestamp DESC LIMIT 5;
```

### Key Event Types to Monitor

| Event Type | Meaning | Severity |
|------------|---------|----------|
| `hfo.gen89.governance.overutilized` | Sustained high resource use | WARN |
| `hfo.gen89.governance.budget_breach` | VRAM over budget | CRITICAL |
| `hfo.gen89.governance.npu_idle` | NPU wasted | INFO |
| `hfo.gen89.sandbox.daemon_death` | A daemon process died | ERROR |
| `hfo.gen89.sandbox.p2_paused` | P2 paused (P5 died) | WARN |
| `hfo.gen89.prey8.memory_loss` | Agent session lost | WARN |
| `hfo.gen89.resource.snapshot` | Point-in-time resource state | INFO |
| `hfo.gen89.swarm.heartbeat` | P6 swarm health check | INFO |

### Web Dashboard

The `hfo_daemon_chat_web.py` (port 8089) provides a live stigmergy feed
with 3-second polling. Use it for real-time monitoring:

```bash
python hfo_daemon_chat_web.py
# Opens http://127.0.0.1:8089 with stigmergy feed + chat
```

---

## §8 — Anti-Patterns (What NOT To Do)

### Anti-Pattern 1: Loading Models On Demand Without Checking Budget

```python
# BAD — loads model without checking available VRAM
ollama.generate(model="phi4:14b", prompt="...")

# GOOD — check budget first
snapshot = resource_monitor.sense()
if snapshot.vram_free_gb >= MODEL_VRAM_ESTIMATES.get("phi4:14b", 10):
    ollama.generate(model="phi4:14b", prompt="...")
else:
    # Use smaller model or queue request
    ollama.generate(model="gemma3:4b", prompt="...")
```

### Anti-Pattern 2: Point-in-Time Resource Checks

```python
# BAD — single check can miss transient spikes
if psutil.cpu_percent() > 80:
    pause_daemon()  # Could pause on a 1-second spike

# GOOD — use SampleBuffer with windowed analysis
buffer.add(sample())
if buffer.pct_above("cpu_pct", 80) >= 70:  # 70% of window
    pause_daemon()  # Only pauses on sustained overload
```

### Anti-Pattern 3: Silent Failures

```python
# BAD — swallow exception and continue
try:
    start_daemon("P2")
except Exception:
    pass  # Who knows what happened?

# GOOD — log to stigmergy and fail-closed
try:
    start_daemon("P2")
except Exception as e:
    _write_stigmergy("hfo.gen89.sandbox.boot_failure", {
        "port": "P2", "error": str(e), "action": "BLOCKED"
    })
    daemon.state = PortState.BLOCKED
```

### Anti-Pattern 4: Running P2 Without P5

```python
# BAD — starts P2 without checking P5
start_daemon("P2", model="gemma3:4b")

# GOOD — enforce safety spine structurally
if daemons["P5"].state != PortState.HEALTHY:
    daemons["P2"].state = PortState.BLOCKED
    raise SafetySpineViolation("P2 requires P5 healthy")
```

### Anti-Pattern 5: Cooperative-Only Governance

From Doc 316: "Cooperative enforcement works when you don't need it and breaks
when you do." Writing "please don't use too much VRAM" in a system prompt does
nothing when the LLM is under pressure.

**Structural alternatives**:
- VRAM budget ceiling checked before model load (fail-closed)
- SampleBuffer regime detection with debounced event firing
- Watchdog loop in separate thread (agent can't turn it off)
- Pre-commit hooks catch violations at commit time

### Anti-Pattern 6: No Heartbeat / Silent Daemon Death

A daemon that doesn't write heartbeats is a daemon you can't tell is alive.
Every daemon should write a heartbeat event every 5 minutes:

```python
# Every daemon: write heartbeat to SSOT
_write_stigmergy("hfo.gen89.{daemon}.heartbeat", {
    "uptime_s": time.time() - start_time,
    "state": "healthy",
    "models_loaded": [...],
})
```

### Anti-Pattern 7: Hardcoded Thresholds Without .env

All thresholds should be configurable via `.env` so the operator can tune
without editing code:

```python
# BAD
CPU_THRESHOLD = 80

# GOOD
CPU_THRESHOLD = float(os.getenv("HFO_GOV_CPU_OVER", "80"))
```

---

## Appendix A — Quick Reference Commands

| Task | Command |
|------|---------|
| Start full sandbox | `python hfo_sandbox_launcher.py` |
| Start P5+P4 only | `python hfo_sandbox_launcher.py --ports P5,P4` |
| Dry run | `python hfo_sandbox_launcher.py --dry-run` |
| Status from SSOT | `python hfo_sandbox_launcher.py --status` |
| Stop sandbox | `python hfo_sandbox_launcher.py --stop` |
| Force clear VRAM | `python hfo_sandbox_launcher.py --force-unload` |
| Governance status | `python hfo_resource_governance.py --status` |
| One resource sample | `python hfo_resource_governance.py --sample` |
| Start governance daemon | `python hfo_resource_governance.py` |
| Perceive (session start) | `python hfo_perceive.py` |
| Check Ollama models | `ollama ps` |
| Unload a model | `ollama stop <model>` |
| Web dashboard | `python hfo_daemon_chat_web.py` |

---

## Appendix B — Decision Tree: Which Tier To Run

```
START
  │
  ├── Operator at keyboard?
  │   ├── YES → interactive work planned?
  │   │   ├── YES: heavy LLM use → Tier D (all daemons paused)
  │   │   └── NO: monitoring → Tier A (P5 + P2 safety spine)
  │   └── NO → leaving overnight?
  │       ├── YES → Tier C (lightweight enrichment only)
  │       └── NO → Tier B (balanced multi-daemon)
  │
  └── Resource pressure?
      ├── THROTTLED → drop to next lower tier
      ├── ELEVATED → monitor, prepare to drop
      ├── NOMINAL → current tier is fine
      └── IDLE → scale up to next higher tier
```

---

*Generated by P4 Red Regnant | Session b9b30ddc4c313e99 | Gen89 | 2026-02-19*
*Recovery from crashed session 584948c0e5d7d8a9 (nonce 6C7639)*
