---
medallion_layer: gold
mutation_score: 0
hive: V
hfo_header_v3: compact
schema_id: hfo.gen89.gold_report.v1
doc_type: gold_report
title: "AI Systems Availability Report — 2026-02-19T09:18 PST"
doc_id: GR-AI-AVAIL-20260219
date: "2026-02-19"
author: "P4 Red Regnant (adversarial audit)"
ports: [P0, P4, P7]
commanders: [Lidless Legion, Red Regnant, Spider Sovereign]
domains: [OBSERVE, DISRUPT, NAVIGATE]
status: SNAPSHOT
bluf: >-
  4 AI systems audited. 3 ONLINE (GitHub Copilot, Ollama, Gemini), 1 OFFLINE
  (OpenRouter). Ollama running 100% GPU on Intel Arc 140V via Vulkan backend
  (22.5 tok/s 3B, 11.5 tok/s 8B). GOOGLE_API_KEY gap fixed. OpenRouter has
  no API key configured. NPU tooling not in PATH. Total compute surface:
  GitHub Copilot (Claude Opus 4.6) + 12 local Ollama models (2B-32B) +
  47 Gemini cloud models (incl 2.5 Flash/Pro). System: Win11, 8-core,
  31.5GB RAM (59% used), Intel Arc 140V 16GB VRAM (53% used with 2 models).
prey8_chain:
  session_id: 1a729c331cb21e05
  perceive_nonce: "8CF525"
  react_token: "2849E8"
  stigmergy_rows: [10931, 10932, 10934, 10936]
evidence:
  hardware_verified: true
  api_keys_tested: [GEMINI_API_KEY, GOOGLE_API_KEY, BRAVE_API_KEY, GITHUB_API_KEY]
  ollama_benchmarked: [granite4:3b, qwen3:8b]
  timestamp_utc: "2026-02-19T16:18:41Z"
  timestamp_local: "2026-02-19T09:18:41 PST"
---

# AI Systems Availability Report — 2026-02-19

> **Audit timestamp:** 2026-02-19T09:18:41 PST (16:18:41 UTC)
> **Auditor:** P4 Red Regnant via GitHub Copilot (Claude Opus 4.6)
> **SSOT state:** 9,861 docs, 10,936+ stigmergy events, ~149 MB

---

## I. EXECUTIVE SUMMARY

| # | AI System | Status | Backend | Evidence |
|---|-----------|--------|---------|----------|
| 1 | **GitHub Copilot** | **ONLINE** | Claude Opus 4.6 | This session proves it |
| 2 | **Ollama (local)** | **ONLINE** | Vulkan on Intel Arc 140V | `ollama ps`: 100% GPU |
| 3 | **Google Gemini** | **ONLINE** | Cloud API (47 models) | Live inference test: "GOOGLE_API_KEY_WORKS" |
| 4 | **OpenRouter** | **OFFLINE** | No API key configured | `HFO_OPENROUTER_ENABLED=false` |

**Total compute surface:** 1 cloud LLM (Copilot) + 12 local models + 47 Gemini cloud models

---

## II. SYSTEM HARDWARE

| Component | Value | Status |
|-----------|-------|--------|
| OS | Windows 11 (AMD64) Build 26200 | OK |
| CPU | Intel Core Ultra 7 258V, 8 cores | 39% used |
| RAM | 31.5 GB total, 12.9 GB free | 59% used |
| GPU | Intel Arc 140V | Active |
| VRAM | 16 GB shared (WMI reports 2048 MB dedicated) | 53% used (8.6 GB / 16 GB) |
| NPU | Intel AI Boost (present) | `intel_npu_top` NOT in PATH |
| Disk | 951.6 GB total, 669.5 GB free | OK |
| Ollama | v0.16.2 | PIDs 14864 + 24408 |

### Hardware Concerns

1. **WMI VRAM misreport:** `Win32_VideoController.AdapterRAM` = 2048 MB. Real shared VRAM = 16 GB. Any tool reading WMI will undercount.
2. **NPU not instrumented:** `HFO_NPU_ALWAYS_ON=true` in `.env` but `intel_npu_top` is not in PATH. NPU utilization cannot be measured.
3. **RAM pressure:** 59% used with no Ollama models actively loaded at rest. Loading phi4:14b + qwen3:8b = ~14 GB VRAM, which would push close to budget.

---

## III. AI SYSTEM DETAILS

### 1. GitHub Copilot — ONLINE

| Property | Value |
|----------|-------|
| Status | **ONLINE** (this session proves it) |
| Backend model | Claude Opus 4.6 |
| Interface | VS Code Copilot Chat |
| Mode | `hfo_gen_89_p4_red_regent_bootstrap_v1` |
| MCP servers | PREY8 Red Regnant (87,359 bytes), Brave Search, Fetch, GitHub, Memory, Ollama, Playwright, SQLite, Sequential Thinking |
| Availability | Always-on when VS Code is open |
| Cost | Included in GitHub Copilot subscription |
| Limitations | Context window-bounded, no persistent memory (uses PREY8 for persistence) |

### 2. Ollama (Local) — ONLINE

| Property | Value |
|----------|-------|
| Status | **ONLINE** — API at `http://127.0.0.1:11434` |
| Version | 0.16.2 |
| GPU backend | **Vulkan** (experimental for Intel Arc) |
| Environment | `OLLAMA_VULKAN=1`, `OLLAMA_INTEL_GPU=1`, `OLLAMA_FLASH_ATTENTION=1` (all User-level) |
| Models installed | 12 |
| VRAM budget | 16 GB total, 12 GB budgeted (`HFO_VRAM_BUDGET_GB`) |

#### Installed Models

| Model | Size | Params | Role |
|-------|------|--------|------|
| granite4:3b | 2.1 GB | 3B | Fast eval, quick tasks |
| lfm2.5-thinking:1.2b | 731 MB | 1.2B | Ultra-light thinking |
| deepseek-r1:32b | 19 GB | 32B | **Exceeds 16GB VRAM — CPU offload required** |
| qwen3:30b-a3b | 18 GB | 30B (3B active MoE) | Large MoE — CPU offload likely |
| phi4:14b | 9.1 GB | 14B | P5 model (highest quality solo) |
| gemma3:12b | 8.1 GB | 12B | Mid-tier quality |
| deepseek-r1:8b | 5.2 GB | 8B | Reasoning |
| qwen2.5-coder:7b | 4.7 GB | 7B | Coding specialist |
| llama3.2:3b | 2.0 GB | 3B | General purpose small |
| gemma3:4b | 3.3 GB | 4B | Former default (replaced by qwen3:8b) |
| qwen3:8b | 5.2 GB | 8B | **Current default** (P2, P6) |
| qwen2.5:3b | 1.9 GB | 3B | General purpose small |

#### Benchmark Results (2026-02-19T09:24 PST)

| Model | Eval tok/s | Prompt tok/s | VRAM | Load time | Total |
|-------|-----------|-------------|------|-----------|-------|
| granite4:3b | 22.5 | 63.0 | 2.7 GB, 100% GPU | 0.2s (warm) | 3.8s |
| qwen3:8b | 11.5 | 13.1 | 5.9 GB, 100% GPU | 13.2s (cold) | 48.8s |

#### Performance Assessment

- **granite4:3b @ 22.5 tok/s:** Moderate. Vulkan experimental backend. OneAPI/IPEX-LLM could yield 2-3x speedup.
- **qwen3:8b @ 11.5 tok/s:** Acceptable for 8B model on Vulkan. Cold load 13.2s is expected.
- **Concurrent models:** Both loaded simultaneously (8.6 GB), confirming multi-model operation.
- **OPTIMIZATION GAP:** Vulkan is experimental for Intel Arc. Native Intel OneAPI via IPEX-LLM would significantly improve throughput.

#### Historical Server Log Analysis

| Log file | Timestamp | GPU Status | Vulkan | Layers offloaded |
|----------|-----------|------------|--------|-----------------|
| server-4 | 2026-02-18 17:45 | CPU only | Disabled | 0/37 |
| server-2 | 2026-02-18 21:01 | CPU only | `OLLAMA_VULKAN:false` | 0/35 |
| Current | 2026-02-19 08:22+ | **100% GPU** | Enabled (User env var) | All layers |

> **Key finding:** Before `OLLAMA_VULKAN=1` was set as a User environment variable, Ollama was running **CPU-only**. All inference today has been GPU-accelerated.

### 3. Google Gemini — ONLINE

| Property | Value |
|----------|-------|
| Status | **ONLINE** — API authenticated, live inference confirmed |
| API key | `GEMINI_API_KEY` (39 chars, `AIzaSyBM...`) |
| `GOOGLE_API_KEY` | **FIXED** — Now set identically (was missing) |
| Models available | 47 (including gemini-2.5-flash, gemini-2.5-pro) |
| Rate limits | 15 RPM / 1500 RPD (per `.env` config) |
| Enabled | `HFO_GEMINI_ENABLED=true` |
| MCP server | `hfo_gemini_mcp_server.py` (21,204 bytes) |
| Live test | `gemini-2.5-flash:generateContent` → "GOOGLE_API_KEY_WORKS" |

#### Key Gemini Models Available

| Model | Type |
|-------|------|
| gemini-2.5-flash | Fast, efficient |
| gemini-2.5-pro | High quality |
| gemini-2.0-flash | Current stable |
| gemini-2.0-flash-lite | Ultra-fast |
| gemini-2.0-flash-exp-image-generation | Image gen |
| gemini-2.5-flash-preview-tts | Text-to-speech |

#### Fix Applied This Session

**Before:** Only `GEMINI_API_KEY` was set in `.env`. `GOOGLE_API_KEY` was missing.
**Issue:** The `google-generativeai` Python SDK defaults to reading `GOOGLE_API_KEY`. Some tools/scripts may fail silently.
**Fix:** Added `GOOGLE_API_KEY=<same value>` to `.env` with documentation comment.
**Verified:** Both keys resolve identically (39 chars, match=True). Live Gemini 2.5 Flash inference confirmed via `GOOGLE_API_KEY`.

### 4. OpenRouter — OFFLINE

| Property | Value |
|----------|-------|
| Status | **OFFLINE** — No API key configured |
| `HFO_OPENROUTER_ENABLED` | `false` |
| `OPENROUTER_API_KEY` | **NOT SET** |
| Action required | Obtain API key from openrouter.ai and add to `.env` |

---

## IV. API KEY INVENTORY

| Key | Status | Length | Prefix | Used by |
|-----|--------|--------|--------|---------|
| `GEMINI_API_KEY` | SET | 39 | AIzaSyBM | Gemini MCP server, hfo_gemini_models.py |
| `GOOGLE_API_KEY` | **FIXED** | 39 | AIzaSyBM | google-generativeai SDK, env_config |
| `BRAVE_API_KEY` | SET | 31 | BSA7lX5Z | Brave MCP server, web search |
| `GITHUB_API_KEY` | SET | 93 | github_p | GitHub MCP server |
| `OPENROUTER_API_KEY` | **NOT SET** | — | — | Not configured |

---

## V. BRAIDED MISSION THREAD STATUS

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| yield_ratio | 9.9% | 50% | NOT MET |
| SDD | 1.5/6 | 4/6 | NOT MET |
| nataraja | 0.85 | 1.0 | NOT MET |
| Alpha payloads | 22/22 | Complete | **COMPLETE** |
| Omega state | COLD_START | TRACTION | NOT MET |
| Income Mode | Not entered | yield_ratio+SDD+nataraja | NOT MET |

### Today's Infrastructure Build (2026-02-19)

| Deliverable | Lines | Port | Status |
|-------------|-------|------|--------|
| P5 Pyre Praetorian daemon | 1,154 | P5 | Tested GREEN |
| P7 Spider Sovereign orchestrator | 580 | P7 | Tested |
| Sandbox launcher | 1,280 | P2/P5 | Tested |
| hfo_env_config.py | 310 | All | Validated |
| Web chat UI | 1,078 | P1 | Tested |
| Song prospector | 1,158 | P4 | Built |
| TUI chat | 600 | P1 | Built |
| PREY8 v4.0 BDD suite | 21 scenarios / 134 steps | P5 | ALL GREEN |
| 4D orthogonal synthesis | 222 | P4 | Gold |
| Chimera loop meta-genome wiring | +198 (1525→1723) | P2 | Verified |
| **Total today** | **~6,580** | 5 ports | — |

---

## VI. ADVERSARIAL FINDINGS (P4)

| # | Finding | Severity | Recommendation |
|---|---------|----------|----------------|
| 1 | **Ollama Vulkan is experimental** — 22.5 tok/s for 3B is 2-3x slower than OneAPI/IPEX-LLM native | MEDIUM | Investigate IPEX-LLM integration for Intel Arc |
| 2 | **PREY8 MCP server `_session` bug** — execute/yield response fails with `name '_session' is not defined`. Data writes to SSOT but response path crashes | HIGH | Restart MCP server to pick up v4.0 fix |
| 3 | **NPU not instrumented** — `intel_npu_top` not in PATH despite `HFO_NPU_ALWAYS_ON=true` | LOW | Install Intel NPU tools or add to PATH |
| 4 | **OpenRouter unconfigured** — potential 4th AI provider sitting idle | LOW | Add API key if cloud fallback desired |
| 5 | **deepseek-r1:32b exceeds VRAM** — 19 GB model installed on 16 GB GPU | INFO | Will auto-offload to CPU; consider removal if VRAM constrained |
| 6 | **10+ orphaned PREY8 sessions today** — v4.0 AGENT_REGISTRY session contention | MEDIUM | Per-instance sessions or queue/lock mechanism |
| 7 | **WMI VRAM misreport** — scripts using Win32_VideoController will see 2048 MB not 16 GB | LOW | Any P7 orchestrator code should use Ollama API for actual VRAM info |
| 8 | **Ollama startup bind errors** — server-1.log full of port bind failures | LOW | Multiple Ollama instances competing; normal during restarts |

---

## VII. TOTAL AI COMPUTE MAP

```
┌─────────────────────────────────────────────────────────────────┐
│                    TTAO AI FLEET — 2026-02-19                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CLOUD TIER (always available with internet)                     │
│  ├── GitHub Copilot (Claude Opus 4.6)     ████████ ONLINE       │
│  ├── Google Gemini (47 models, 2.5 Flash/Pro) ████████ ONLINE   │
│  └── OpenRouter                           ░░░░░░░░ OFFLINE      │
│                                                                  │
│  LOCAL TIER (Intel Arc 140V, 16 GB VRAM)                         │
│  ├── Ollama (12 models installed)         ████████ ONLINE        │
│  │   ├── qwen3:8b (default P2/P6)        5.2 GB  11.5 tok/s    │
│  │   ├── phi4:14b (P5 quality)            9.1 GB  ~8 tok/s*     │
│  │   ├── qwen2.5-coder:7b (coding)       4.7 GB  ~13 tok/s*    │
│  │   ├── granite4:3b (fast eval)          2.1 GB  22.5 tok/s    │
│  │   └── 8 more models available                                 │
│  └── NPU embedder                        ░░░░░░░░ NOT MEASURED  │
│                                                                  │
│  * estimated from model size ratios                              │
│                                                                  │
│  COVERAGE: 3/4 systems ONLINE = 75% fleet availability           │
│  TOTAL MODELS: 12 local + 47 Gemini + 1 Copilot = 60 models     │
└─────────────────────────────────────────────────────────────────┘
```

---

*Report generated by P4 Red Regnant. PREY8 session 1a729c331cb21e05.*
*SSOT rows: 10931 (perceive), 10932 (react), 10934 (execute 1), 10936 (execute 2).*
