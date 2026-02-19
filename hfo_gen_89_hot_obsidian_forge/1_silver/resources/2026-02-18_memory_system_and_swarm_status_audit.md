---
schema_id: hfo.mosaic_microkernel_header.v3
medallion_layer: silver
mutation_score: 0
hive: V
hfo_header_v3: compact
mnemonic: "O·B·S·I·D·I·A·N = 8 ports = 1 octree"
bluf: "Silver audit: 2 of 5 memory subsystems working (SQLite + Stigmergy). 0 of 8 daemons running 24/7 yet, but 5 have code. Vector, Shodh, and Hebbian remain designed-but-not-wired in Gen89."
primary_port: P6
role: "Silver Analysis — Memory System & Swarm Status Audit"
tags: [silver, audit, memory, swarm, daemons, p6, status, gen89]
generated: "2026-02-18T00:00:00Z"
evidence_base: "Live SSOT schema audit, 7 SSOT documents (122,125,210,247,274,323), 5 source files, Ollama API scan, stigmergy trail"
prey8_session: "b5bb7cba2b80f16b"
---

# Memory System & Swarm Status Audit — Gen89

> **Date:** 2026-02-18  
> **Medallion:** Silver (operator-reviewed analysis)  
> **Author:** P4 Red Regnant (via PREY8 gated session b5bb7cba2b80f16b)

---

## Executive Summary (Plain Language)

You're building a system where **8 AI commanders** each run as persistent background processes (daemons), each with their own personality, job, and local AI model. Together they form a "social spider swarm" — they don't talk to each other directly, but instead leave traces in a shared database (like ants leaving pheromone trails). This indirect coordination is called **stigmergy**.

**Where we actually are today:**

| Category | Status | Plain English |
|----------|--------|---------------|
| SQLite database | **Working** | Your single source of truth exists. 9,860 documents, ~9M words, 149 MB. Reads and writes work. |
| Full-text search (FTS5) | **Working** | You can search the database by keywords. Fast and accurate. |
| Vector/semantic search | **Not present** | You cannot search by meaning ("find docs similar to X"). The Gen88 version had this but it was broken. Gen89 was rebuilt clean without it. |
| Shodh (association server) | **Not present** | The Shodh memory server was healthy in Gen88 (HTTP 200, v0.1.75) but feature-flagged OFF. Gen89 doesn't include it. |
| Hebbian learning | **Not present** | The idea of "neurons that fire together wire together" (strengthening links between memories used together) is documented in design docs but has never been implemented. |
| Stigmergy event trail | **Working** | 9,700+ events logged. CloudEvent structured. Daemons and tools write here. Other tools read it. This IS the coordination backbone. |
| 8 daemon swarm | **Code exists, not running** | All 8 daemons are defined in code. They can start in threads and loop. But nobody has run them persistently yet. |

**Bottom line:** You have a working database with text search and an event trail. The three "smart" memory features (vector search, knowledge graphs, learning) are still on paper. The swarm code exists but hasn't been turned on for real.

---

## The 8 Commanders — Who Has Code?

Every port in the octree has a commander with an alliterative title and a D&D-inspired signature spell. Here's where each one stands:

| Port | Commander | Title | Spell | Dedicated Code | Fitness | Status |
|------|-----------|-------|-------|----------------|---------|--------|
| **P0** | Lidless Legion | Watcher of Whispers and Wrath | TRUE SEEING | `prey8_eval_harness.py` — model benchmarking | 0.65 | **Has code, tested** |
| **P1** | Web Weaver | Binder of Blood and Breath | FORBIDDANCE | None yet | — | **Designed only** |
| **P2** | Mirror Magus | Maker of Myths and Meaning | GENESIS | `hfo_p2_chimera_loop.py` — evolutionary code gen | 0.40 | **Has code, tested** |
| **P3** | Harmonic Hydra | Harbinger of Harmony and Havoc | GATE | None yet | — | **Designed only** |
| **P4** | Red Regnant | Singer of Strife and Splendor | WEIRD | `hfo_prey8_mcp_server.py` — 12 MCP tools, fail-closed gates | 0.75 | **Most mature. Running now.** |
| **P5** | Pyre Praetorian | Dancer of Death and Dawn | CONTINGENCY | `hfo_p5_contingency.py` — resurrection engine | 0.30 | **Has code, partially tested** |
| **P6** | Kraken Keeper | Devourer of Depths and Dreams | CLONE | None yet (owns memory, ironic) | — | **Designed only** |
| **P7** | Spider Sovereign | Summoner of Silk and Sovereignty | TIME STOP | Represented by TTAO (the operator) | — | **You are P7** |

### What "fitness" means

Fitness scores come from the mission_state table (MAP-Elites grid). They measure how far along each task is toward completion:
- **0.75** (P4) = Most functionality built and running
- **0.65** (P0) = Core tool built and tested
- **0.40** (P2) = Working but not yet battle-tested across all grid cells
- **0.30** (P5) = Framework built, needs more integration
- **0.0** = Not started

### The Nataraja Dance (P4 + P5)

The P4 Red Regnant (DISRUPT/destroy) and P5 Pyre Praetorian (IMMUNIZE/resurrect) form the "Nataraja" — the cosmic dance of destruction and rebirth. The code for this exists in `hfo_octree_daemon.py`:

- **P4 kills things** (finds weaknesses, applies adversarial pressure)
- **P5 resurrects them stronger** (contingency triggers, phoenix protocol)
- **NATARAJA_Score = P4_kill_rate × P5_rebirth_rate** — when ≥ 1.0, the system is "antifragile"

Current state: The Nataraja engine code is implemented but the dance hasn't been run live. P4 is the only commander doing real work right now (through the MCP gated PREY8 protocol you're using to read this report).

---

## Memory Subsystems — Detailed Audit

### 1. SQLite SSOT — WORKING ✅

This is the heart of everything. One SQLite file, 149 MB.

**What's in it:**

| Table | Rows | What it holds |
|-------|------|---------------|
| `documents` | 9,860 | Every piece of content — markdown files, memories, configs, artifacts. Each has a title, bluf (summary), content, tags, port assignment, word count. |
| `stigmergy_events` | 9,700+ | The event trail. Every time something happens (a PREY8 session, a daemon advisory, a model pull), a CloudEvent gets written here. |
| `mission_state` | 18 | The MAP-Elites behavioral grid — tracks eras, waypoints, and tasks with fitness scores. New as of today. |
| `meta` | 14 | Self-description: schema version, build date, quine instructions, FTS config. |
| `documents_fts` | (virtual) | FTS5 full-text search index over documents. |
| `lineage` | 0 | Dependency graph — exists but empty. Ready for future use. |

**What works:**
- Reading and writing documents
- Reading and writing stigmergy events
- Content-hash deduplication (SHA256 unique constraint)
- Self-describing meta table (the database can explain itself)

**What doesn't:**
- There is no `memories` table (that was Gen88). Gen89 consolidated everything into `documents`.
- There are no vector/embedding columns
- There is no tiering (hot/warm/cold) — that was Gen88's `memories` table

### 2. Full-Text Search (FTS5) — WORKING ✅

FTS5 indexes these columns from `documents`: title, bluf, content, tags, doc_type, port.

**How it works in practice:** When the P4 MCP server's `prey8_fts_search` tool is called, it runs:
```sql
SELECT rowid FROM documents_fts WHERE documents_fts MATCH 'your query'
```
This is fast lexical search — it finds exact words and stems. It's what powered the research phase of this very report.

**Limitations:**
- It's keyword-based, not semantic. Searching "how does memory work" won't find a doc titled "P6 ASSIMILATE architecture" unless those exact words appear.
- No ranking by relevance (BM25 is available in FTS5 but not currently used in queries).

### 3. Vector/Semantic Search (sqlite_vec) — NOT PRESENT ❌

**What it would do:** Let you search by meaning instead of keywords. "Find documents similar to this concept" using embedding vectors (arrays of numbers that represent meaning).

**Gen88 status (from R55 reference doc):**
- 13,585 embeddings existed in a `memory_embeddings` virtual table using `vec0`
- But the `vec0` SQLite extension wasn't loadable on the machine (Chromebook limitation)
- A NumPy brute-force fallback existed but was behind a feature flag and slow
- Coverage was 99.97% but unusable

**Gen89 status:**
- The Gen89 consolidation rebuild deliberately did NOT carry over vec0 tables
- There are zero vector-related tables, columns, or extensions in the Gen89 SSOT
- No Python code in the workspace uses sqlite_vec or any embedding library

**What's needed to add it:**
- Install `sqlite-vec` Python package
- Generate embeddings (using an Ollama model like `nomic-embed-text` or `mxbai-embed-large`)
- Create a vec0 virtual table in the SSOT
- Wire it into the MCP server as a `prey8_semantic_search` tool

### 4. Shodh (Association/Knowledge Graph Server) — NOT PRESENT ❌

**What it is:** Shodh is a Rust-based memory server that runs as a separate HTTP service (port 3030). It provides an association graph — a network of connections between memories, where links strengthen when memories are retrieved together.

**Gen88 status (from R55):**
- Server was healthy: HTTP 200, version v0.1.75
- 3 users registered
- Running in Docker with resource limits (1GB mem, 2GB swap, 1 CPU)
- But feature flag `HFO_MCP_ENABLE_SHODH_MEMORY=0` was **disabled**
- All Shodh search paths were marked **BLOCKED** in the operational audit

**Gen89 status:**
- Shodh is not running
- No Shodh configuration, Docker setup, or connection code exists in Gen89
- The Gen89 workspace is on a Windows machine (previous was Chromebook), so the Docker-based Shodh would need WSL2+Docker setup

**What's needed:**
- Start Shodh in Docker (WSL2 Docker is being set up based on terminal history)
- Wire Shodh API calls into MCP server or daemon code
- Enable the feature flag
- Populate with associations from the 9,860 documents

### 5. Hebbian Learning — NOT PRESENT ❌

**What it would do:** "Neurons that fire together wire together." When two memories are retrieved together during a successful task, the association between them gets stronger. Over time, the system builds a web of connections showing which knowledge tends to be useful together.

**Formula from the design docs:** $\Delta w = \gamma \cdot a \cdot b$ (weight change = learning rate × activation of neuron A × activation of neuron B)

**What exists:**
- Detailed design documentation (Doc 274: E40, Doc 323: P6 Rollup)
- Three planned modes: semantic (vector KNN), associative (graph traversal), hybrid
- Concept mapping: memory record = neuron, association edge = synapse, co-retrieval = co-firing

**What doesn't exist:**
- Zero implementation code
- No association/edge tables in the database
- No weight tracking, decay, or reinforcement logic
- No integration with any retrieval pipeline

**This is the most "designed but not built" subsystem.** The architecture is well-documented in theory. Nothing has been coded.

### 6. Stigmergy — WORKING ✅

This is arguably the most important subsystem and it works well.

**How it works:** Instead of daemons calling each other (direct communication), they write events to the `stigmergy_events` table. Other daemons/tools read these events and react. It's like ants leaving pheromone trails — no ant talks to another ant, but they coordinate through the environment.

**What's working:**
- 9,700+ events accumulated over 14 months of development
- CloudEvent structure (type, source, subject, data, timestamp, content hash)
- Multiple event families: PREY8 sessions, daemon advisories, model pulls, mission state changes
- Read/write from Python (MCP server, perceive/yield scripts, daemon engine)
- Pheromone decay model designed (exponential decay with reinforcement from Gen88's `v_pheromone_ranked` view) — but NOT in Gen89 yet

**What's missing:**
- No pheromone ranking view in Gen89 (the `v_pheromone_ranked` view from Gen88 was not migrated)
- No automatic cleanup/expiry of old events
- No reinforcement tracking

---

## The Swarm Infrastructure — What You Actually Have

### The Daemon Engine (`hfo_octree_daemon.py` — 1,087 lines)

This is a complete, working swarm supervisor. Here's what it does:

1. **8 `OctreeDaemon` objects** — one per port, each with:
   - Its own Ollama model assignment
   - A persona/system prompt built from port invariants
   - A background thread that loops on a tick rate (30–120 seconds)
   - State tracking (STOPPED → STARTING → RUNNING → ADVISING → ERROR → DEAD)

2. **`SwarmSupervisor`** — creates all 8 daemons, starts/stops them, prints status

3. **`NatarajaDance`** — monitors P4+P5 together, calculates antifragility score

4. **Ollama integration** — `ollama_generate()` calls the local API, `list_available_models()` scans what's pulled

5. **Model fleet management** — watchlist of 19 models across 16 families, scan/pull commands

### What's Pulled (12 Ollama Models)

| Model | Size | Assigned To |
|-------|------|-------------|
| gemma3:4b | 3.3 GB | P0 OBSERVE (fast sensing) |
| qwen2.5:3b | 1.9 GB | P1 BRIDGE (fast data fabric) |
| qwen2.5-coder:7b | 4.7 GB | P2 SHAPE (code generation) |
| qwen3:8b | 5.2 GB | P3 INJECT (balanced delivery) |
| deepseek-r1:8b | 5.2 GB | P4 DISRUPT (adversarial reasoning) |
| phi4:14b | 9.1 GB | P5 IMMUNIZE (resurrection) |
| deepseek-r1:8b | 5.2 GB | P6 ASSIMILATE (knowledge extraction) |
| qwen3:30b-a3b | 18.6 GB | P7 NAVIGATE (strongest for C2) |
| deepseek-r1:32b | 19.9 GB | Reserve / evaluation |
| gemma3:12b | 8.1 GB | Reserve / evaluation |
| llama3.2:3b | 2.0 GB | Reserve |
| granite4:3b | 2.1 GB | Reserve / evaluation |
| lfm2.5-thinking:1.2b | 0.7 GB | Reserve (tiny thinking model) |

**Total: ~86 GB of models on disk.** All 8 port assignments have a model ready.

### What's Actually Running Right Now

| Component | Running? | Evidence |
|-----------|----------|---------|
| SQLite SSOT | ✅ Yes | Every MCP tool call reads/writes it |
| FTS5 search | ✅ Yes | `prey8_fts_search` used in this session |
| PREY8 MCP server | ✅ Yes | You're using it right now (12 tools, fail-closed gates) |
| Stigmergy writing | ✅ Yes | 9,700+ events, new ones written this session |
| Ollama | ✅ Yes | 12 models loaded, API responding on 127.0.0.1:11434 |
| 8 daemon loop | ❌ No | Code exists but `hfo_octree_daemon.py --all` has not been run persistently |
| Nataraja P4+P5 dance | ❌ No | Code exists, never activated live |
| P5 contingency watcher | ❌ No | Code exists, not running |
| P2 chimera loop | ⚠️ Tested | Has been run with `--test-model` flag but not in continuous evolution mode |
| P0 eval harness | ⚠️ Tested | Has been run for benchmarking but not as persistent daemon |
| Vector search | ❌ No | Not implemented |
| Shodh | ❌ No | Not deployed |
| Hebbian learning | ❌ No | Not implemented |

---

## How It All Fits Together (The Big Picture)

```
                        YOU (P7 Spider Sovereign)
                              │
                    ┌─────────┴─────────┐
                    │  PREY8 MCP Server  │  ← The only running "daemon"
                    │  (P4 Red Regnant)  │     12 tools, fail-closed gates
                    └─────────┬─────────┘
                              │ reads/writes
                    ┌─────────┴─────────┐
                    │   SSOT SQLite DB   │  ← 149 MB, 9,860 docs
                    │   + FTS5 index     │     + 9,700+ stigmergy events
                    │   + mission_state  │     + 18 MAP-Elites grid cells
                    └─────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
        ┌─────┴─────┐  ┌─────┴─────┐  ┌──────┴──────┐
        │  12 Ollama │  │ 8 Daemon  │  │  NOT YET:   │
        │   Models   │  │  Engine   │  │  • Vectors   │
        │  (pulled)  │  │  (coded)  │  │  • Shodh     │
        │            │  │           │  │  • Hebbian   │
        └────────────┘  └───────────┘  └─────────────┘
           READY          READY           DESIGNED
```

The architecture is a hub-and-spoke around the SQLite SSOT. Everything coordinates through stigmergy (writing events to the shared database). The spokes that are actually connected: the MCP server (P4), FTS5 search, and your direct queries. The spokes that are built but not plugged in: the 8-daemon swarm engine, the P2 chimera loop, the P5 contingency engine. The spokes that don't exist yet: vector search, Shodh, Hebbian learning.

---

## Honest Assessment

### What P4 Red Regnant Thinks (Adversarial)

1. **The swarm is a fleet of ships in bottles.** Beautiful code, sitting on a shelf. Not one daemon has run for more than a test invocation. "24/7 daemons" is the destination, not the current state.

2. **P6 Kraken Keeper owns memory but has no code.** The port responsible for "STORE" operations has zero dedicated scripts. Memory subsystem documentation is excellent; implementation is absent.

3. **You have 2 of 5 memory primitives.** SQLite + Stigmergy work. That gives you: write documents, search by keywords, write/read coordination events. You cannot: search by meaning, traverse knowledge graphs, or learn which memories are useful together.

4. **The Gen88→Gen89 transition was the right call but expensive.** You went from a broken mess (47K memories, 71% dead, 6 search paths with 1 working, vec0 broken, Shodh disabled) to a clean foundation (9,860 curated documents, FTS5 working, clean schema). But you lost everything that was partially working in Gen88 and haven't rebuilt it yet.

5. **P4 is carrying the team.** Fitness 0.75 means P4 has done 75% of its job. The next closest (P0 at 0.65) is an evaluation tool, not a production daemon. P1, P3, P6 are at zero. The swarm won't be a swarm until at least 4 ports have dedicated, tested scripts.

### What's Actually Good

1. **The PREY8 protocol works.** Fail-closed gates, hash chains, tamper detection, nonce validation — this is robust infrastructure. P4's 12 MCP tools are the most mature tooling in the system.

2. **12 models are ready.** Every port has a capable model assigned. The fleet spans 1.2B to 30B parameters across 8 model families (Gemma, Qwen, DeepSeek, Phi, Llama, Granite, LFM). Vendor agnostic.

3. **Stigmergy is proven.** 9,700+ events over 14 months. The coordination pattern works. Daemons don't need direct communication channels — they just need to read/write the trail.

4. **The daemon engine code is solid.** 1,087 lines with proper threading, error handling, state management, tick rates, and the Nataraja feedback loop. It just needs to be turned on.

---

## Recommended Next Steps (Priority Order)

| Priority | Action | Why | Effort |
|----------|--------|-----|--------|
| 1 | **Run the daemon swarm live** | `python hfo_octree_daemon.py --all` — start all 8 daemons and let them loop. Even with imperfect code, the stigmergy trail they generate has value. | Low |
| 2 | **Add vector search (sqlite_vec)** | Pull `nomic-embed-text` model, generate embeddings for all 9,860 docs, create vec0 table. This unlocks semantic search ("find similar docs") — the single biggest retrieval upgrade. | Medium |
| 3 | **Build P6 ASSIMILATE script** | The memory port needs its own dedicated code for knowledge extraction, post-action review, and memory lifecycle management. | Medium |
| 4 | **Add BM25 ranking to FTS5** | FTS5 supports `rank` — currently unused. Adding `ORDER BY rank` to search queries would make text search much more useful. | Low |
| 5 | **Rebuild Shodh or replace with SQLite graph** | Either deploy Shodh in WSL2+Docker or implement a lightweight association graph directly in SQLite (edges table with weights). SQLite-native may be simpler. | Medium-High |
| 6 | **Implement Hebbian learning** | Build an edges/association table, add co-retrieval tracking, implement weight updates. This is the most complex missing piece. | High |

---

## Evidence Trail

| Source | What it told us |
|--------|-----------------|
| Live DB schema audit (`_db_audit.py`) | Confirmed tables, views, columns, absence of vec0/shodh/hebbian |
| SSOT stats (MCP `prey8_ssot_stats`) | 9,860 docs, 9,708 events, 149 MB, 4 memory losses |
| Doc 122 (R55 Infrastructure Snapshot) | Gen88 state: broken vec0, disabled Shodh, 1/6 search paths |
| Doc 323 (P6 One-Page Rollup) | Designed architecture: 3 primitives, Hebbian learning, Shodh |
| Doc 274 (E40 Hebbian Learning) | Theory and HFO mapping for association learning |
| Doc 210 (Indra Net Traversal) | Stigmergy + SQLite O(1) as thermodynamically viable coordination |
| `hfo_octree_daemon.py` (1,087 lines) | Complete swarm supervisor with all 8 ports + Nataraja engine |
| `hfo_prey8_mcp_server.py` (12 tools) | P4 Red Regnant MCP server — the most mature component |
| `hfo_p2_chimera_loop.py` | P2 evolutionary code generation — tested |
| `hfo_p5_contingency.py` | P5 resurrection engine — partially tested |
| `prey8_eval_harness.py` | P0 model benchmarking — tested |
| Ollama API scan (`_check_models.py`) | 12 models pulled, 86 GB, all port assignments covered |
| Mission state table (18 rows) | MAP-Elites grid with fitness scores per task |
| Stigmergy trail (9,700+ events) | 14 months of coordination history |

---

*Report generated 2026-02-18 by P4 Red Regnant via PREY8 session b5bb7cba2b80f16b. All claims verified against live evidence.*
