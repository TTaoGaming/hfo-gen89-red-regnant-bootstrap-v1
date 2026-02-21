---
schema_id: hfo.gen90.agents.v1
medallion_layer: gold
mutation_score: 0
hive: V
hfo_header_v3: compact
mnemonic: "O·B·S·I·D·I·A·N = 8 ports = 1 octree"
bluf: "Root SSOT nav for Gen90. 9,859 docs, 9,590 stigmergy events, ~9M words, ~4B compute tokens. 14 months solo dev by TTAO."
---

# AGENTS.md — HFO Gen90 Agent Context

> **You are entering a 14-month, ~4 billion compute-token refinement pipeline.**
> This file is your orientation. Read it completely before acting.

---

## 1. What This Is

**HFO (Hive Fleet Obsidian)** is a structured knowledge system and AI-human collaboration framework. This workspace contains **Gen90** — a clean dev environment bootstrapped from the consolidated SSOT database.

| Fact | Value |
|------|-------|
| Generation | 90 (consolidated from Gen89) |
| Operator | TTAO |
| Total documents | 9,859 |
| Total words | ~8,971,662 |
| Stigmergy events | 9,590 |
| Temporal span | 2025-01 → 2026-02 |
| Builder | `gen90_ssot_packer.py v2` |

---

## 2. Workspace Layout

```
hfoDev/                                    ← HFO_ROOT (git repo root)
├── AGENTS.md                              ← YOU ARE HERE (root SSOT)
├── .env                                   ← Secrets + config (GITIGNORED)
├── .env.example                           ← Template (committed)
├── .gitignore                             ← Keep root clean
├── .githooks/
│   └── pre-commit                         ← Medallion gate + root cleanliness
├── hfo_gen90_pointers_blessed.json        ← Blessed PAL pointer registry
└── hfo_gen_90_hot_obsidian_forge/         ← The Forge
    ├── 0_bronze/                          ← Unvalidated working data
    │   ├── archives/
    │   ├── areas/
    │   ├── projects/
    │   └── resources/                     ← Scratch scripts, hfo_pointers.py
    ├── 1_silver/                          ← Human-reviewed / validated
    │   ├── archives/
    │   ├── areas/
    │   ├── projects/
    │   └── resources/
    ├── 2_gold/                            ← Hardened, trusted
    │   ├── archives/
    │   ├── areas/
    │   ├── projects/
    │   └── resources/
    │       └── hfo_gen90_ssot.sqlite      ← THE DATABASE (149 MB, self-describing)
    └── 3_hyper_fractal_obsidian/          ← Meta/architectural layer
        ├── archives/
        ├── areas/
        ├── projects/
        └── resources/
```

### Root Cleanliness Rule

The root directory holds **only governance and PAL files**. Everything else lives in the forge. The pre-commit hook enforces this. Allowed root files:

| File | Purpose |
|------|---------|
| `AGENTS.md` | Root SSOT — all governance lives here |
| `.env.example` | Environment template (committed) |
| `.env` | Secrets + local config (gitignored) |
| `.gitignore` | Git ignore rules |
| `.gitattributes` | Git LFS tracking rules |
| `.githooks/` | Git hooks directory |
| `.github/` | GitHub agent modes + workflows |
| `.vscode/` | VS Code settings + MCP config |
| `hfo_gen90_pointers_blessed.json` | Blessed pointer registry |
| `LICENSE` / `README.md` | Standard repo files (optional) |

---

## 3. The PAL System (Path Abstraction Layer)

**Rule: NEVER hardcode a deep forge path. Use a pointer key and resolve it.**

### How It Works

1. **Pointer Registry** — `hfo_gen90_pointers_blessed.json` maps named keys to relative paths
2. **Resolver** — `hfo_pointers.py` resolves keys to absolute paths
3. **Environment** — `.env` provides runtime config (generation, secrets, feature flags)

### Using Pointers

```bash
# Resolve a pointer to an absolute path
python hfo_gen_90_hot_obsidian_forge/0_bronze/resources/hfo_pointers.py resolve ssot.db

# List all registered pointers
python hfo_gen_90_hot_obsidian_forge/0_bronze/resources/hfo_pointers.py list

# Verify all pointers resolve to existing paths
python hfo_gen_90_hot_obsidian_forge/0_bronze/resources/hfo_pointers.py check
```

### Key Pointer Keys

| Key | Target | Description |
|-----|--------|-------------|
| `ssot.db` | `…/2_gold/resources/hfo_gen90_ssot.sqlite` | The SSOT database |
| `forge.root` | `hfo_gen_90_hot_obsidian_forge` | Forge top-level |
| `forge.bronze` | `…/0_bronze` | Bronze working layer |
| `forge.gold` | `…/2_gold` | Gold hardened layer |
| `forge.hfo` | `…/3_hyper_fractal_obsidian` | Meta-layer |
| `root.agents_md` | `AGENTS.md` | This file |
| `pal.resolver` | `…/0_bronze/resources/hfo_pointers.py` | Pointer resolver |
| `pal.precommit` | `.githooks/pre-commit` | Pre-commit hook |
| `octree.invariants` | `…/2_gold/resources/…invariants.v1.json` | 8-port invariants |
| `prey8.perceive` | `…/0_bronze/resources/hfo_perceive.py` | Session start bookend |
| `prey8.yield` | `…/0_bronze/resources/hfo_yield.py` | Session end bookend |

### Adding New Pointers

Edit `hfo_gen90_pointers_blessed.json` → add a key under `"pointers"`:
```json
"my_new.pointer": {
  "path": "hfo_gen_90_hot_obsidian_forge/0_bronze/resources/my_tool.py",
  "desc": "Description of what this points to"
}
```

### Environment Variables (.env)

| Variable | Purpose | Default |
|----------|---------|---------|
| `HFO_GENERATION` | Current generation | `89` |
| `HFO_OPERATOR` | Operator identity | `TTAO` |
| `HFO_FORGE` | Forge dir (relative) | `hfo_gen_90_hot_obsidian_forge` |
| `HFO_SSOT_DB` | Database path (relative) | `…/hfo_gen90_ssot.sqlite` |
| `HFO_SECRET` | Signing secret (NEVER commit) | — |
| `HFO_STRICT_MEDALLION` | Enforce medallion gates | `true` |
| `HFO_PRECOMMIT_ENABLED` | Pre-commit hook active | `true` |

### Pre-Commit Hook

The `.githooks/pre-commit` hook runs automatically on `git commit` and enforces:

1. **Root cleanliness** — Only allowed files at workspace root
2. **No secrets** — Blocks `.env`, `.pem`, `.key`, etc.
3. **Medallion boundary warnings** — Flags direct writes to silver/gold/hfo layers
4. **Large file warnings** — Files > 10 MB flagged for Git LFS

Setup: `git config core.hooksPath .githooks` (already configured)

---

## 4. PREY8 Bookends — Mandatory Session Protocol

**ZERO EXCEPTIONS. Every agent interaction MUST call Perceive at start and Yield at end.**

The PREY8 loop is the cognitive persistence mechanism inherited from Gen89 (257 perceive events, 944 Red Regnant events). It ensures no agent session is a dead-end — every interaction reads the trail and writes back to it.

### The Loop

```
P — Perceive  (session start: query SSOT, read stigmergy, orient)
R — React     (interpret context, form plan)
E — Engage    (do the work)
Y — Yield     (session end: write stigmergy, leave traces, close loop)
```

### Perceive (Session Start)

```bash
# Basic context snapshot — run this FIRST in every session
python hfo_gen_90_hot_obsidian_forge/0_bronze/resources/hfo_perceive.py

# With user intent for FTS search
python hfo_gen_90_hot_obsidian_forge/0_bronze/resources/hfo_perceive.py --probe "user's question"

# Machine-readable JSON
python hfo_gen_90_hot_obsidian_forge/0_bronze/resources/hfo_perceive.py --json
```

**What it does:**
1. Queries SSOT for document stats (9,859 docs, ~9M words)
2. Gets latest 10 stigmergy events (what happened recently)
3. Finds last perceive/yield pair (session continuity)
4. Runs FTS5 search if probe is provided (relevant context)
5. **Writes a `hfo.gen90.prey8.perceive` CloudEvent** to `stigmergy_events`
6. Returns nonce for yield chain validation

### Yield (Session End)

```bash
# Basic yield — run this LAST in every session
python hfo_gen_90_hot_obsidian_forge/0_bronze/resources/hfo_yield.py \
  --summary "What was accomplished" \
  --probe "Original user intent"

# With artifacts and next steps
python hfo_gen_90_hot_obsidian_forge/0_bronze/resources/hfo_yield.py \
  --summary "Built PREY8 bookend scripts" \
  --probe "setup prey8 mandatory bookends" \
  --artifacts-created "hfo_perceive.py,hfo_yield.py" \
  --next "test full loop,add to AGENTS.md" \
  --insights "CloudEvent structure from Gen89 exemplars"

# Machine-readable JSON
python hfo_gen_90_hot_obsidian_forge/0_bronze/resources/hfo_yield.py --json -s "summary"
```

**What it does:**
1. Finds the matching perceive nonce (chain validation)
2. Records: summary, artifacts created/modified, next steps, insights
3. **Writes a `hfo.gen90.prey8.yield` CloudEvent** to `stigmergy_events`
4. Outputs SW-4 Completion Contract (Given/When/Then)

### Pointer Keys

| Key | Target | Description |
|-----|--------|-------------|
| `prey8.perceive` | `…/0_bronze/resources/hfo_perceive.py` | Session start bookend |
| `prey8.yield` | `…/0_bronze/resources/hfo_yield.py` | Session end bookend |

### Why This Is Mandatory

- **Cognitive persistence**: Agent sessions vanish without warning. The stigmergy trail is the only thing that survives.
- **Nonce chain**: Each perceive generates a nonce; yield references it. Broken chains = lost sessions.
- **Stigmergy**: "All text is stigmergy" (Gen89 insight). Every session leaves pheromones for future agents.
- **SSOT integrity**: The database grows with every interaction. No dead-end sessions.

### Enforcement

If an agent does NOT run perceive/yield:
1. The next agent's perceive will show a gap in the stigmergy trail
2. The operator will see missing nonce chains
3. The session's work is **not recorded** — it's as if it never happened

---

## 5. The Database — How to Use It

The SQLite database at `hfo_gen_90_hot_obsidian_forge/2_gold/resources/hfo_gen90_ssot.sqlite` is a **self-describing Memory Quine**. It contains everything.

### Connect

```python
import sqlite3
conn = sqlite3.connect('hfo_gen_90_hot_obsidian_forge/2_gold/resources/hfo_gen90_ssot.sqlite')
cursor = conn.cursor()
```

### Essential Queries

```sql
-- Read the self-description
SELECT value FROM meta WHERE key = 'quine_instructions';

-- Overview
SELECT key, substr(value, 1, 200) FROM meta;

-- Full-text search (FTS5)
SELECT id, title, bluf, source, port
FROM documents
WHERE id IN (
    SELECT rowid FROM documents_fts
    WHERE documents_fts MATCH 'your query here'
)
LIMIT 20;

-- Browse by source
SELECT source, COUNT(*), SUM(word_count) FROM documents GROUP BY source;

-- Browse by port
SELECT port, COUNT(*) FROM documents WHERE port IS NOT NULL GROUP BY port;

-- Browse stigmergy trail
SELECT event_type, COUNT(*) FROM stigmergy_events
GROUP BY event_type ORDER BY COUNT(*) DESC;

-- Read a document
SELECT content FROM documents WHERE id = ?;

-- Schema self-description
SELECT value FROM meta WHERE key = 'schema_doc';
```

### Database Schema (abbreviated)

| Table | Rows | Purpose |
|-------|------|---------|
| `documents` | 9,859 | All content — markdown, configs, artifacts, memories |
| `stigmergy_events` | 9,590 | Indirect coordination trail (CloudEvents) |
| `lineage` | 0 | Dependency graph (unfilled — ready for population) |
| `meta` | 14 | Self-description keys (quine, schema, manifest) |
| `documents_fts` | — | FTS5 full-text search index |

### Key Document Columns

- **`source`**: Where it came from (`memory`, `diataxis`, `p4_payload`, `p3_payload`, `forge_report`, `artifact`, `config`, `silver`, `gold_report`, `project`, `root_doc`)
- **`port`**: P0–P7 routing (nullable)
- **`medallion`**: ALL `bronze` — trust nothing, validate everything
- **`doc_type`**: `portable_artifact`, `explanation`, `reference`, `doctrine`, `how_to`, `tutorial`, `recipe_card_card`, `forge_report`, etc.
- **`content_hash`**: SHA256 dedupe key (UNIQUE constraint)
- **`tags`**: Comma-separated, searchable
- **`metadata_json`**: Full lossless frontmatter/metadata as JSON

---

## 6. The Octree — 8 Ports

Mnemonic: **O·B·S·I·D·I·A·N**

| Port | Word | Commander | Domain | Docs |
|------|------|-----------|--------|------|
| P0 | OBSERVE | Lidless Legion | Sensing under contest | 27 |
| P1 | BRIDGE | Web Weaver | Shared data fabric | 19 |
| P2 | SHAPE | Mirror Magus | Creation / models | 41 |
| P3 | INJECT | Harmonic Hydra | Payload delivery | 564 |
| P4 | DISRUPT | Red Regnant | Red team / probing | 1,306 |
| P5 | IMMUNIZE | Pyre Praetorian | Blue team / gates | 16 |
| P6 | ASSIMILATE | Kraken Keeper | Learning / memory | 113 |
| P7 | NAVIGATE | Spider Sovereign | C2 / steering | 47 |

---

## 7. Medallion Architecture

```
bronze  →  silver  →  gold  →  hyper_fractal_obsidian
(raw)      (reviewed)  (hardened)  (meta/architectural)
```

**Current state:** ALL 9,859 documents are `bronze`. Promotion requires validation.

- **Bronze (0):** Trust nothing. Raw ingestion. May contain hallucinations, duplicates, stale data.
- **Silver (1):** Human-reviewed or automated-validation-passed. Factual claims verified.
- **Gold (2):** Hardened. Cross-referenced. Tested against invariants.
- **Hyper Fractal Obsidian (3):** Meta-layer. Architecture, governance, self-description.

---

## 8. Stigmergy — The Event Trail

The `stigmergy_events` table is an indirect coordination log. Agents leave traces; other agents read them. Key patterns:

### 4-Phase Execution Loop
```
preflight → payload → payoff → postflight
```

### Major Event Families
- `hfo.gen89.p4.basic.*` — P4 basic protocol (~1,873 events)
- `hfo.gen89.p4.toolbox_turn_v10.*` — P4 toolbox protocol (~1,594 events)
- `hfo.p4.red_regnant.*` — Red Regnant adversarial coaching (~944 events)
- `hfo.gen89.p4.toolbox.*` — P4 toolbox v1 (~1,008 events)
- `system_health` — System health snapshots (1,583 events)
- `hfo.web_search.scatter_gather.v1` — Web research (497 events)
- `hfo.prey8.perceive` — Perception subsystem (257 events)

---

## 9. Governance — The Silk Web Protocols

All agents operating in this workspace MUST follow these protocols:

### SW-1: Spec Before Code
Before any multi-file change, state WHAT you will change and WHY in a structured spec. No silent multi-file edits.

### SW-2: Recitation Gate
Before executing a spec, repeat it back verbatim. If you can't recite it, you haven't understood the task. Stop and clarify.

### SW-3: Never Silently Retry
If an operation fails, STOP and report what failed + why. Do not silently retry with different parameters. Three consecutive failures = hard stop, ask human.

### SW-4: Completion Contract
Every task must produce a verifiable receipt: Given (precondition) → When (action) → Then (postcondition + evidence).

### SW-5: Boundary Respect
Fail-closed on medallion boundary crossings. Bronze cannot self-promote. All promotions require explicit gate passage.

---

## 10. Path Resolution

**Rule: NEVER hardcode a deep forge path.** Use the PAL system (§3) to resolve all paths.

```bash
# Instead of hardcoding paths, use pointer keys:
python hfo_gen_90_hot_obsidian_forge/0_bronze/resources/hfo_pointers.py resolve ssot.db
python hfo_gen_90_hot_obsidian_forge/0_bronze/resources/hfo_pointers.py resolve forge.bronze
```

See §3 for the full pointer key table and environment variables.

---

## 11. Content Inventory (by source)

| Source | Docs | Words | Description |
|--------|------|-------|-------------|
| `memory` | 7,423 | 6,497,159 | Bulk corpus — portable artifacts from pre-HFO through Gen84 |
| `p4_payload` | 1,234 | 535,113 | P4 Red Regnant / development session outputs |
| `p3_payload` | 522 | 138,807 | P3 Harmonic Hydra delivery artifacts |
| `diataxis` | 428 | 824,785 | Formal documentation library (explanations, references, how-tos, tutorials) |
| `forge_report` | 134 | 208,243 | Forge execution reports |
| `project` | 64 | 40,338 | Project definitions and specs |
| `silver` | 31 | 30,268 | Curated analyses, deep research, SOTA synthesis |
| `artifact` | 9 | 661,166 | Large consolidated artifacts (concordances, analyses) |
| `gold_report` | 6 | 2,262 | Hardened reports (slop defense, antifragility, reward hacking forensics) |
| `config` | 5 | 24,330 | Configuration files (AGENTS.md, pointers, braided thread) |
| `root_doc` | 3 | 9,191 | Incident reports, operator notes |

---

## 12. Quick Start for New Agents

1. **Read this file completely.** You now have orientation.
2. **Check the environment.** Verify `.env` exists (copy from `.env.example` if not).
3. **Verify pointers resolve:**
   ```bash
   python hfo_gen_90_hot_obsidian_forge/0_bronze/resources/hfo_pointers.py check
   ```
4. **Query the database.** Use FTS5 to find what you need:
   ```sql
   SELECT id, title, bluf FROM documents
   WHERE id IN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH 'your topic')
   LIMIT 10;
   ```
5. **Check stigmergy** for what's already been tried:
   ```sql
   SELECT event_type, timestamp, subject FROM stigmergy_events
   WHERE event_type LIKE '%your_topic%' ORDER BY timestamp DESC LIMIT 10;
   ```
6. **Work in bronze.** All new artifacts go to `0_bronze/`. Promotion happens later.
7. **Leave traces.** If you produce artifacts, they should eventually be ingested into the SSOT with proper metadata.
8. **Follow SW-1 through SW-5.** No exceptions.
9. **Commit often.** The pre-commit hook will catch violations automatically.

---

## 13. Trust Model

- The database is a **bronze-only** consolidation. Every document, including ones originally from gold/silver sources, was re-ingested as bronze.
- Content hashes (SHA256) guarantee deduplication.
- The `metadata_json` column preserves original frontmatter losslessly.
- Stigmergy events are CloudEvent-structured with content-hash deduplication.
- The `lineage` table exists but is unpopulated — ready for dependency graph construction.

---

## 14. Active Projects

### Omega v13 Microkernel
**Status:** Ready to Ship
**Location:** `hfo_gen_90_hot_obsidian_forge/1_silver/projects/omega_v13_microkernel/`
**Description:** A strict I/O Sandbox (Host vs. Guest) gesture substrate. The Host handles the camera, MediaPipe, and gesture invariants. The Guest receives a highly constrained, Zod-validated stream of W3C Pointer events.
**Key Features:**
- **W3C Pointer Fabric:** Shared data fabric for decoupled components.
- **Defense-in-Depth FSM:** Strict state machine for gesture transitions.
- **Audio Engine:** Synthesized Cherry MX mechanical keyboard sounds for state transitions (READY -> COMMIT_POINTER -> READY/IDLE).
- **Visualization:** Dot/ring visualization of state changes per hand.
- **Behavioral Predictive Layer:** Hyper-heuristic GA for predicting user movement.

---

*Gen90 SSOT built 2026-02-18 by gen90_ssot_packer.py v2. Operator: TTAO.*
