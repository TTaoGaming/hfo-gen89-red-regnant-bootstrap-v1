---
schema_id: hfo.gen89.diataxis.reference.v1
medallion_layer: gold
doc_type: reference
title: "Cold Start System Audit — LENOVOSLIM7"
timestamp: "2026-02-18T00:00:00Z"
operator: TTAO
agent: GitHub Copilot (Claude Opus 4.6)
port: P0
tags: [cold-start, system-audit, wsl2, ide-setup, reference, diataxis]
bluf: "New Lenovo Slim 7 laptop. Win11, 32GB RAM, Intel Ultra 7 258V, Arc 140V 16GB GPU, 952GB SSD. Python 3.12 + VS Code installed. No git, no Node, no Docker, no WSL distro. WSL2 engine enabled but empty. SQLite SSOT (149MB, 9,859 docs) confirmed accessible. This is your bootstrap checklist."
---

# Cold Start System Audit — LENOVOSLIM7

> **Reference Document** | Diataxis Category: **Reference**
> Scanned: 2026-02-18 | Agent: GitHub Copilot (Claude Opus 4.6) | Operator: TTAO

---

## 1. Hardware Summary

| Component | Value |
|-----------|-------|
| **Hostname** | LENOVOSLIM7 |
| **OS** | Windows 11 Home, Build 26200 |
| **Processor** | Intel Core Ultra 7 258V (8 cores / 8 threads) |
| **RAM** | 32,305 MB (~32 GB) |
| **GPU** | Intel Arc 140V (16 GB) |
| **GPU Driver** | 32.0.101.6733 |
| **Wi-Fi** | Intel Wi-Fi 7 BE201 320MHz — 1.1 Gbps link |
| **BIOS** | LENOVO QSCN29WW (2025-05-12) |
| **Domain** | WORKGROUP (standalone) |

### Storage

| Drive | Label | Total (GB) | Free (GB) | Usage |
|-------|-------|-----------|----------|-------|
| **C:** | Windows-SSD | 951.6 | 825.7 | 13% used |
| **D:** | microsd_dev | 59.4 | 6.7 | 89% used |

**Assessment:** Excellent hardware. Lunar Lake Ultra 7 with 32GB RAM and a large SSD with >800GB free. The Arc 140V GPU supports Intel oneAPI/SYCL workloads and can be useful for local AI inference via OpenVINO or IPEX-LLM. D: drive is nearly full — consider offloading or cleaning.

---

## 2. Software Inventory

### Installed & Working

| Tool | Version | Path |
|------|---------|------|
| **Python** | 3.12.10 | `C:\Users\tommy\AppData\Local\Programs\Python\Python312\python.exe` |
| **pip** | 25.0.1 | (bundled with Python 3.12) |
| **VS Code** | 1.109.4 | `C:\Users\tommy\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd` |
| **winget** | v1.6.10121 | (Windows Package Manager) |
| **OpenSSH** | (built-in) | `C:\Windows\System32\OpenSSH\ssh.exe` |
| **curl** | (built-in alias) | PowerShell `Invoke-WebRequest` alias |
| **tar** | (built-in) | `C:\Windows\system32\tar.exe` |

### NOT Installed (Action Required)

| Tool | Status | Install Command |
|------|--------|----------------|
| **Git** | MISSING | `winget install Git.Git` |
| **Node.js** | MISSING | `winget install OpenJS.NodeJS.LTS` |
| **Docker** | MISSING | `winget install Docker.DockerDesktop` (needs WSL2 distro first) |
| **WSL2 Distro** | MISSING | `wsl --install Ubuntu-24.04` |

### Python Environment

| Detail | Value |
|--------|-------|
| Installed packages | **Only pip** (bare environment) |
| Virtual env | None detected |
| Site-packages | `C:\Users\tommy\AppData\Local\Programs\Python\Python312\Lib\site-packages` |

### VS Code Extensions

| Status | Detail |
|--------|--------|
| Installed extensions | **None detected** (fresh install, only Copilot active in-session) |

---

## 3. WSL2 Status

| Check | Result |
|-------|--------|
| WSL engine | **Installed** (default version 2) |
| WSL1 support | Not available (hardware config doesn't support it — normal for Lunar Lake) |
| Installed distros | **None** |
| Virtual Machine Platform | Presumably enabled (WSL2 default set) |
| Available distros | Ubuntu, Ubuntu-24.04, openSUSE-Tumbleweed, openSUSE-Leap-16.0, SUSE variants |

### WSL2 Setup — How-To (Quick Reference)

```powershell
# Step 1: Install Ubuntu 24.04 LTS (recommended)
wsl --install Ubuntu-24.04

# Step 2: After reboot/setup, verify
wsl -l -v
#   NAME            STATE    VERSION
#   Ubuntu-24.04    Running  2

# Step 3: First launch (sets username/password)
wsl

# Step 4: Inside Ubuntu — update immediately
sudo apt update && sudo apt upgrade -y

# Step 5: Install essentials inside WSL
sudo apt install -y build-essential git curl wget unzip \
  python3 python3-pip python3-venv nodejs npm

# Step 6 (optional): Install Docker Desktop for Windows
# Then enable WSL2 backend in Docker Desktop settings
```

**Note:** WSL1 is not supported on this hardware (Intel Lunar Lake / Windows 11 26200). WSL2 uses full Hyper-V virtualization — this is the correct and only path.

---

## 4. HFO Workspace Audit

### Workspace Root: `C:\hfoDev`

```
hfoDev/
├── AGENTS.md                              ← Root SSOT / agent orientation (271 lines)
├── explore_db.py                          ← Legacy DB explorer (root)
├── explore_db2.py                         ← Legacy DB explorer v2 (root)
└── hfo_gen_89_hot_obsidian_forge/         ← The Forge (Gen89)
    ├── 0_bronze/
    │   └── resources/
    │       ├── explore_db.py              ← DB explorer copy
    │       ├── explore_db2.py             ← DB explorer copy
    │       ├── explore_db3.py             ← DB explorer v3 (advanced)
    │       └── _probe_db.py              ← Created this session (system audit probe)
    ├── 1_silver/                          ← Empty (no promoted docs yet)
    ├── 2_gold/
    │   └── resources/
    │       └── hfo_gen89_ssot.sqlite      ← THE DATABASE (148.8 MB)
    └── 3_hyper_fractal_obsidian/          ← Empty (meta layer)
```

### SSOT Database Verified

| Property | Value |
|----------|-------|
| **File** | `hfo_gen89_ssot.sqlite` |
| **Size** | 148.8 MB |
| **Schema version** | gen89_ssot_v2.0 |
| **Builder** | gen89_ssot_packer.py v2 ("The Cursed Ralph Wiggums Loop") |
| **Generation** | 89 (consolidated from Gen88) |
| **Total documents** | 9,859 |
| **Total words** | 8,971,662 (~9M) |
| **Total stigmergy events** | 9,590 |
| **FTS5 index** | Active (unicode61 tokenizer; title, bluf, content, tags, doc_type, port) |
| **Medallion policy** | ALL BRONZE — trust nothing |
| **Dedupe** | SHA256 content hash (UNIQUE constraint) |

### Database Tables

| Table | Purpose |
|-------|---------|
| `meta` | 14 self-description keys (quine instructions, schema, manifest) |
| `documents` | 9,859 rows — all content |
| `stigmergy_events` | 9,590 rows — coordination trail |
| `lineage` | 0 rows — dependency graph (ready for population) |
| `documents_fts` | FTS5 full-text search index |

### Content Breakdown by Source

| Source | Docs | Words | Description |
|--------|------|-------|-------------|
| memory | 7,423 | 6,497,159 | Bulk corpus — portable artifacts |
| p4_payload | 1,234 | 535,113 | P4 Red Regnant session outputs |
| p3_payload | 522 | 138,807 | P3 Harmonic Hydra deliveries |
| diataxis | 428 | 824,785 | Formal documentation library |
| forge_report | 134 | 208,243 | Forge execution reports |
| project | 64 | 40,338 | Project definitions and specs |
| silver | 31 | 30,268 | Curated analyses/research |
| artifact | 9 | 661,166 | Large consolidated artifacts |
| gold_report | 6 | 2,262 | Hardened reports |
| config | 5 | 24,330 | Configuration files |
| root_doc | 3 | 9,191 | Incident reports, operator notes |

### Top Stigmergy Event Types

| Event Type | Count |
|------------|-------|
| unknown | 1,716 |
| system_health | 1,583 |
| hfo.web_search.scatter_gather.v1 | 497 |
| hfo.gen88.p4.basic.preflight | 470 |
| hfo.gen88.p4.basic.payload | 468 |
| hfo.gen88.p4.basic.payoff | 468 |
| hfo.gen88.p4.basic.postflight | 467 |
| hfo.gen88.p4.toolbox_turn_v10.preflight | 449 |
| hfo.gen88.p4.toolbox_turn_v10.payload | 446 |
| hfo.p4.red_regnant.postflight | 372 |

---

## 5. Agent Capabilities in This Session

### What I CAN Do

| Capability | Status |
|------------|--------|
| Read/write files in workspace | YES |
| Run PowerShell commands | YES |
| Run Python scripts | YES |
| Query SQLite SSOT database | YES (via Python) |
| Create/edit markdown, code | YES |
| Search workspace (text, regex, semantic) | YES |
| Install packages via pip/winget | YES (pip confirmed; winget available) |
| Install WSL distros | YES (via `wsl --install`) |
| Run background processes | YES |
| Access VS Code APIs | Available (deferred tools) |
| Fetch web pages | Available (deferred tool) |

### What I CANNOT Do

| Limitation | Detail |
|------------|--------|
| Elevated/admin commands | Cannot run as Administrator (Get-WindowsOptionalFeature failed) |
| GUI interactions | No mouse/keyboard automation |
| Persistent state across sessions | No memory between conversations (but the SSOT database IS your persistent memory) |
| Direct WSL commands | No distro installed yet — `wsl` shell unavailable until install |

---

## 6. Recommended IDE Setup (Priority Order)

### Critical (Do First)

| # | Action | Command | Why |
|---|--------|---------|-----|
| 1 | **Install Git** | `winget install Git.Git` | Version control is non-negotiable. Required by most tools. |
| 2 | **Install WSL2 Ubuntu** | `wsl --install Ubuntu-24.04` | Enables Linux dev, Docker, and cross-platform workflows. Requires restart. |
| 3 | **Install VS Code extensions** | See list below | Bare VS Code is crippled without extensions. |
| 4 | **Create Python venv** | `python -m venv .venv` | Isolate project dependencies from system Python. |

### Recommended VS Code Extensions

```powershell
# Core
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension ms-toolsai.jupyter

# WSL Integration
code --install-extension ms-vscode-remote.remote-wsl

# Git
code --install-extension eamodio.gitlens

# Markdown
code --install-extension yzhang.markdown-all-in-one
code --install-extension bierner.markdown-mermaid

# SQLite
code --install-extension alexcvzz.vscode-sqlite

# Quality of Life
code --install-extension esbenp.prettier-vscode
code --install-extension streetsidesoftware.code-spell-checker

# AI (already have Copilot)
code --install-extension GitHub.copilot
code --install-extension GitHub.copilot-chat
```

### Important (Do Second)

| # | Action | Command | Why |
|---|--------|---------|-----|
| 5 | **Install Node.js** | `winget install OpenJS.NodeJS.LTS` | Many tools/extensions need it. |
| 6 | **Install key Python packages** | `pip install sqlite-utils rich httpx` | sqlite-utils for DB work, rich for TUI, httpx for HTTP. |
| 7 | **Git init the workspace** | `cd C:\hfoDev; git init; git add -A; git commit -m "Gen89 cold start"` | Snapshot the initial state. |
| 8 | **Install Docker Desktop** | `winget install Docker.DockerDesktop` | After WSL2 Ubuntu is running. |

### Nice to Have (Do Later)

| # | Action | Why |
|---|--------|-----|
| 9 | Configure Windows Terminal profiles | Better terminal experience for WSL + PowerShell |
| 10 | Set up SSH keys | `ssh-keygen -t ed25519` for GitHub/remote access |
| 11 | Install `uv` (Python) | `pip install uv` — blazing fast package manager |
| 12 | D: drive cleanup | Only 6.7 GB free on microsd_dev |

---

## 7. Quick-Start Commands (Copy-Paste Ready)

```powershell
# === PHASE 1: Essentials (run in PowerShell) ===

# Install Git
winget install Git.Git

# Install WSL2 with Ubuntu 24.04
wsl --install Ubuntu-24.04
# ⚠️ This may require a restart

# Install Node.js LTS
winget install OpenJS.NodeJS.LTS

# === PHASE 2: VS Code Extensions ===
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension ms-toolsai.jupyter
code --install-extension ms-vscode-remote.remote-wsl
code --install-extension eamodio.gitlens
code --install-extension yzhang.markdown-all-in-one
code --install-extension alexcvzz.vscode-sqlite

# === PHASE 3: Python Environment ===
cd C:\hfoDev
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install sqlite-utils rich httpx ipython

# === PHASE 4: Git Init ===
git init
git add -A
git commit -m "Gen89 cold start — 2026-02-18"
```

---

## 8. Architecture Notes for Future Sessions

1. **The SSOT is your cross-session memory.** Every future agent starts by reading `AGENTS.md` then querying the SQLite database. This is your 14-month knowledge base.

2. **Medallion promotion is manual.** All 9,859 docs are bronze. Promoting to silver/gold requires validation workflows you'll build over time.

3. **The lineage table is empty.** This is the dependency graph for document relationships — a high-value future project.

4. **Stigmergy events are your audit trail.** 9,590 events documenting 14 months of AI-human coordination. Valuable for pattern analysis.

5. **This laptop is well-specced for local AI.** 32GB RAM + Arc 140V 16GB GPU = viable for local inference (Ollama, llama.cpp with Intel GPU support, OpenVINO).

---

*Document generated 2026-02-18 by GitHub Copilot (Claude Opus 4.6) during cold-start system audit. Operator: TTAO. Machine: LENOVOSLIM7.*
