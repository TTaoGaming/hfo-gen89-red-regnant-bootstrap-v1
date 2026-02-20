---
schema_id: hfo.gen89.p4.trade_study.v1
medallion_layer: bronze
port: P4
doc_type: trade_study
title: "DSE AoA: Daemon Chat Interface Options"
bluf: "4-option trade study for direct operator-daemon chat. Option C (Stigmergy Chat CLI) is Pareto-dominated by Option A (MCP-Native). Recommended: start with Option A (zero-build), graduate to Option B (Textual TUI) when bandwidth allows. Option D (Gradio Web) is non-dominated but resource-costly."
date: 2026-02-19
session_id: a565aad4a85e3da8
prey8_chain: perceive→react→execute→yield
---

# DSE AoA: Daemon Chat Interface — 4 Options

> **Decision context:** The operator has 5 daemon categories (PREY8 MCP, Octree
> Daemon, Spider Tremorsense, Kraken Swarm, Stigmergy Watchdog) coordinating via
> stigmergy in SSOT SQLite. No direct conversational interface exists. The system
> is at 91% RAM / 115% VRAM budget. Any solution must be lightweight.

---

## 1. Candidates

### Option A — MCP-Native (Copilot Chat as the Interface)

**Architecture:** Use the existing VS Code Copilot Chat + 12 MCP servers already
configured. The operator speaks in natural language; Copilot routes to PREY8 MCP
tools (`prey8_fts_search`, `prey8_query_stigmergy`, `prey8_session_status`,
`prey8_ssot_stats`), Ollama MCP (`ollama_chat`), SQLite MCP (direct queries),
and Gemini MCP (`gemini_chat`). Daemon state is read via stigmergy queries.
Daemon commands are issued by writing stigmergy events.

- **Build effort:** Zero — already operational (you're using it right now)
- **Dependencies:** VS Code, MCP SDK, existing servers
- **RAM cost:** ~0 MB incremental (Copilot is already loaded)
- **Daemon interaction:** Indirect — reads stigmergy trail; can write command events
- **Multi-daemon:** Yes — route to any port's data via FTS/stigmergy queries

### Option B — Textual TUI (Terminal-Native Rich Chat)

**Architecture:** Python `textual` app (~2.5MB install) running in the VS Code
integrated terminal. Dual-pane layout: left = stigmergy event stream (live tail),
right = chat input with direct Ollama API calls. Each port daemon has a named
"channel" — select a port, type a message, the TUI builds a prompt with that
port's persona + FTS context + recent stigmergy, calls Ollama, renders response
with `rich` markup. All exchanges logged as stigmergy events.

- **Build effort:** ~300 lines, 2-4 hours
- **Dependencies:** `textual` (pulls `rich` which is already installed)
- **RAM cost:** ~30-50 MB
- **Daemon interaction:** Direct — calls Ollama with port persona, reads/writes stigmergy
- **Multi-daemon:** Yes — tab/sidebar per port, cross-port broadcast mode

### Option C — Stigmergy Chat CLI (Lightweight Python Script)

**Architecture:** Single-file Python script (~150 lines). `readline`-based REPL
that reads stigmergy_events for context, formats a prompt with the target daemon's
persona, calls Ollama API, prints the response, and writes a stigmergy_event with
the exchange. Minimal: no TUI framework, no web server, no dependencies beyond
`httpx` (already installed).

- **Build effort:** ~150 lines, 1-2 hours
- **Dependencies:** `httpx` (already installed)
- **RAM cost:** ~15-20 MB
- **Daemon interaction:** Direct — same Ollama call pattern as Option B
- **Multi-daemon:** Limited — one daemon per invocation, switch with `--port P4`
- **Bonus:** Scriptable — pipe input, use in batch/cron, capture output

### Option D — Gradio Web App (Browser-Based Chat UI)

**Architecture:** Python `gradio` app (~200MB install) serving a web-based chat
interface on localhost. Tabbed interface with one chat per port. Each tab maintains
conversation history (multi-turn), calls Ollama/Gemini per port persona, and shows
a live stigmergy feed panel. WebSocket push for real-time event notifications.
Export conversations as stigmergy event chains.

- **Build effort:** ~500 lines, 4-8 hours
- **Dependencies:** `gradio` (~200MB), `uvicorn`, `starlette`
- **RAM cost:** ~200-300 MB (Python server + Chromium tab)
- **Daemon interaction:** Direct + rich — multi-turn history, streaming tokens
- **Multi-daemon:** Full — tabs per port, broadcast mode, side-by-side compare

---

## 2. Evaluation Criteria (Weighted)

| # | Criterion | Weight | Rationale |
|---|-----------|--------|-----------|
| C1 | **Resource Cost** | **0.25** | System at 91% RAM. Every MB counts. |
| C2 | **Implementation Effort** | **0.20** | Solo operator, limited bandwidth. |
| C3 | **SSOT Integration Depth** | **0.20** | Must read/write stigmergy. Must not bypass SSOT. |
| C4 | **Real-Time Interaction** | **0.15** | Streaming tokens, live event tails. |
| C5 | **Stigmergy Preservation** | **0.10** | Every exchange must leave traces in SSOT. |
| C6 | **Multi-Daemon Conversation** | **0.10** | Talk to multiple ports, cross-reference. |

---

## 3. Scoring Matrix (1 = poor, 5 = excellent)

| Criterion | Wt | A: MCP-Native | B: Textual TUI | C: Stig CLI | D: Gradio Web |
|-----------|----|:---:|:---:|:---:|:---:|
| C1 Resource Cost | 0.25 | **5** | **4** | **5** | **2** |
| C2 Impl. Effort | 0.20 | **5** | **3** | **4** | **2** |
| C3 SSOT Integration | 0.20 | **5** | **4** | **4** | **3** |
| C4 Real-Time | 0.15 | **3** | **4** | **2** | **5** |
| C5 Stigmergy Pres. | 0.10 | **5** | **4** | **4** | **3** |
| C6 Multi-Daemon | 0.10 | **4** | **5** | **2** | **5** |
| | | | | | |
| **Weighted Total** | | **4.55** | **3.85** | **3.70** | **2.95** |

### Score Formulas

```
A = 5(.25) + 5(.20) + 5(.20) + 3(.15) + 5(.10) + 4(.10)
  = 1.25 + 1.00 + 1.00 + 0.45 + 0.50 + 0.40 = 4.60

B = 4(.25) + 3(.20) + 4(.20) + 4(.15) + 4(.10) + 5(.10)
  = 1.00 + 0.60 + 0.80 + 0.60 + 0.40 + 0.50 = 3.90

C = 5(.25) + 4(.20) + 4(.20) + 2(.15) + 4(.10) + 2(.10)
  = 1.25 + 0.80 + 0.80 + 0.30 + 0.40 + 0.20 = 3.75

D = 2(.25) + 2(.20) + 3(.20) + 5(.15) + 3(.10) + 5(.10)
  = 0.50 + 0.40 + 0.60 + 0.75 + 0.30 + 0.50 = 3.05
```

---

## 4. Dominance Analysis

**Definition:** Option X **dominates** Option Y if X ≥ Y on ALL criteria and X > Y on at least one.

### Pairwise Comparison

| Pair | C1 | C2 | C3 | C4 | C5 | C6 | Verdict |
|------|:---:|:---:|:---:|:---:|:---:|:---:|---------|
| A vs B | A>B | A>B | A>B | A<B | A>B | A<B | **Not dominated** (B wins C4, C6) |
| A vs C | A=C | A>C | A>C | A>C | A>C | A>C | **A dominates C** |
| A vs D | A>D | A>D | A>D | A<D | A>D | A<D | **Not dominated** (D wins C4, C6) |
| B vs C | B<C | B<C | B=C | B>C | B=C | B>C | **Not dominated** (C wins C1, C2) |
| B vs D | B>D | B>D | B>D | B<D | B>D | B=D | **Not dominated** (D wins C4) |
| C vs D | C>D | C>D | C>D | C<D | C>D | C<D | **Not dominated** (D wins C4, C6) |

### Result

```
╔═══════════════════════════════════════════════════════════════════╗
║  DOMINATED:     Option C (Stigmergy Chat CLI)                   ║
║                 → Dominated by Option A (MCP-Native)             ║
║                   A ≥ C on ALL 6 criteria, A > C on 5 of 6      ║
║                                                                   ║
║  PARETO FRONT:  {A, B, D}                                       ║
║                 A = high efficiency, zero build                   ║
║                 B = balanced (best multi-daemon UX at low cost)  ║
║                 D = highest interactivity (at resource premium)   ║
║                                                                   ║
║  NOT VIABLE:    Option C offers nothing A doesn't already have.  ║
║                 The only differentiator (scriptable/pipeable)    ║
║                 is trivially served by CLI wrappers around MCP.  ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## 5. Pareto Frontier Visualization

```
     C4 Real-Time Interaction →
  5 ┤                                    ● D (Gradio)
    │
  4 ┤              ● B (Textual)
    │
  3 ┤  ● A (MCP-Native)
    │
  2 ┤                    ○ C (CLI) ← DOMINATED
    │
  1 ┤
    └──┬──┬──┬──┬──┬──
       1  2  3  4  5
       ← Resource Cost (inverted: 5=cheapest) →

  Pareto front: A──B──D  (convex hull, C is interior)
```

---

## 6. Recommendation

### Phased Strategy

| Phase | Option | Trigger | Effort |
|-------|--------|---------|--------|
| **Now** | **A: MCP-Native** | Already operational | 0 hours |
| **Next** | **B: Textual TUI** | When operator wants dedicated daemon chat window | 2-4 hours |
| **Later** | **D: Gradio Web** | When RAM headroom > 4GB free, or after SSD upgrade | 4-8 hours |
| **Never** | ~~C: Stigmergy CLI~~ | Dominated — skip entirely | — |

### Why A First

You are **already using Option A right now.** This Copilot Chat session reads
stigmergy via PREY8 MCP, queries the SSOT via SQLite MCP, and can call any
Ollama model via the Ollama MCP server. The interface is natural language with
full context. The only limitation is that Copilot doesn't have a persistent
"daemon dashboard" view — you get daemon state on demand, not as a live stream.

### Why B Next

Textual TUI fills the gap A can't: a **persistent live view** of stigmergy
events streaming in real-time, with the ability to switch between port channels
and see daemon heartbeats as they arrive. It runs inside the VS Code terminal,
costs ~30MB, and has zero external dependencies beyond `pip install textual`.

### Why Not D Now

Gradio's 200MB+ footprint on a system already at 91% RAM / 115% VRAM is a
non-starter today. When the resource budget improves (new hardware, or daemons
paused), Gradio adds multi-turn conversation history, streaming token display,
and browser-based accessibility that neither A nor B match.

---

## 7. P4 Adversarial Challenges Applied

| Challenge | Finding |
|-----------|---------|
| **Is MCP-native really "chat"?** | Yes — Copilot Chat is the UI. MCP tools are the backend. Natural language in, structured data out. The operator doesn't see JSON unless they want to. |
| **Could Gradio dominate Textual?** | No — Gradio loses on C1 (resource cost) and C2 (effort). Textual wins on the operator's tightest constraint (RAM). |
| **Is CLI just a worse Textual?** | Dominated by MCP-native. The only CLI advantage (scriptable) is served by `prey8_fts_search` MCP calls or direct SQLite queries. |
| **What about Open WebUI?** | Excluded — 500MB+ footprint, Docker dependency, duplicates Ollama management, no native SSOT integration. Dominated by D on effort, dominated by A on resource cost. |
| **What about Chainlit/NiceGUI?** | Same class as Gradio — web server + browser tab. No resource advantage. Gradio has the largest ecosystem and fastest prototyping. |

---

*Trade study produced by P4 Red Regnant, session a565aad4a85e3da8, 2026-02-19.*
*PREY8 chain: perceive(06D417) → react(2FEFA3) → execute(163777) → yield(pending)*
