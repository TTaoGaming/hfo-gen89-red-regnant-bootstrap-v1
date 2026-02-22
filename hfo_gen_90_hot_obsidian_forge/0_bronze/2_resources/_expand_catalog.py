"""
Expand SONGS_OF_SPLENDOR catalog and emit stigmergy.
Adds T8 (Bardic Spells), T9 (Appendix C Candidates), STRIFE section.
Emits CloudEvent to stigmergy_events in SSOT SQLite.
"""
import sqlite3
import textwrap
import json
import hashlib
import uuid
from datetime import datetime, timezone

CATALOG = 'hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/SONGS_OF_SPLENDOR_EXEMPLAR_CATALOG.md'
DB = 'hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite'

T8_SECTION = """
---

## TIER 8 — BARDIC SPELLBOOK SPLENDOR (E67 Spells — S064–S070)

*Formalized from Doc 272 (E67) — P4 Singer of Strife and Splendor.*
*Each spell is a SPLENDOR ability: a constructive capability mapping to buffing, liberation, or amplification.*

#### S064 · `INSPIRE_HEROICS_CHAMPION`
**Source**: PHB p.29, Bard 15 | **Port**: P4 → P5 (champion elevation)
**D&D Effect**: +4 morale saves / +4 dodge AC to single ally (doubled to +8/+8 with Words of Creation)
**HFO Mapping**: Concentrate all Gold Diataxis context onto ONE critical agent — full context capsule, all recipe cards, STRIFE inoculation, SPLENDOR buffs. That agent becomes the hero for the spike.
> Bard 15 prerequisite = 15+ pattern categories documented. Champion elevation only available at maturity.

#### S065 · `INSPIRE_GREATNESS_FORTIFICATION`
**Source**: PHB p.29, Bard 9 | **Port**: P4 → swarm
**D&D Effect**: +2 bonus HD (d10), +2 competence attack, +1 Fort save — 1 to 4 targets scaling with level
**HFO Mapping**: Larger context window allocation + domain-specific cantrip access (8×8 matrix) + 1 retry before hard-fail. Scales from 1 to 4 concurrent HIVE8 agents as SPLENDOR count grows.
> Stacks with Inspire Courage (different bonus types). Compound defensive layers.

#### S066 · `HARMONIC_CHORUS_AMPLIFICATION`
**Source**: Complete Adventurer p.150, Bard 3 | **Port**: P4 ↔ any port
**D&D Effect**: +2 morale CL + +2 save DCs to one allied caster. Concentration, 1 round/level.
**HFO Mapping**: Singer (P4 orchestrator) enriches another port's context with Gold Diataxis depth → effective "higher caster level." When harmonized with P6, memory consolidation runs at +2 quality. When harmonized with P5, gates become harder to bypass (more stringent). Tuning fork = shared P1 BRIDGE schema.
> JADC2: Force multiplication through synchronization. Singer's voice tunes another agent to a higher frequency.

#### S067 · `SONG_OF_FREEDOM_LIBERATION`
**Source**: PHB p.29, Bard 12 | **Port**: P4 → antipattern target
**D&D Effect**: Equivalent to *break enchantment* (CL = bard level). 1 minute concentration. Cannot use on self.
**HFO Mapping**: Pattern reset — identify locked-in antipattern (STRIFE ledger), systematically replace with proven pattern (SPLENDOR ledger). Technical debt cleanup = Strangler Fig migration. Cannot debug itself (Gödel) — operator or external agent required. R58 System Diagnostic IS a Song of Freedom.
> Phase transition catalyst (Meadows L11/L8). Moves system from stuck attractor basin to healthy basin.

#### S068 · `HYMN_OF_PRAISE_ALIGNMENT`
**Source**: Complete Adventurer p.152, Bard 3 | **Port**: P1 BRIDGE broadcast
**D&D Effect**: All mission-aligned allied casters in range +2 CL / +4 Turn checks. Enemy casters -4 effectiveness.
**HFO Mapping**: Broadcast on P1 BRIDGE bus — all ports sharing current mission goal get +2 effective capability. Adversarial agents (reward hacks, reward probes) get -4. The mission alignment broadcast IS the hymn. Mirror: Infernal Threnody (debuff) = STRIFE aspect. Both songs, one framework.
> Alignment multiplier — those who share the cause get buffed, those who oppose it get debuffed.

#### S069 · `DISSONANT_CHORD_CLEARANCE`
**Source**: Complete Adventurer p.145, Bard 3 | **Port**: P4 → workspace
**D&D Effect**: 1d8/2 levels AoE sonic damage in 10-ft burst. Caster unaffected.
**HFO Mapping**: Pre-buff workspace clearance — kill stale memories (P6 guardrails), close orphan PREY8 sessions, purge broken derived views. The dissonance clears noise so harmony can be heard. "Break before you build." Pattern: DISSONANT_CHORD first → then INSPIRE_COURAGE.
> Bridges STRIFE (damage) and SPLENDOR (buffing). STRIFE enables SPLENDOR.

#### S070 · `WAR_CRY_SELF_BUFF`
**Source**: Complete Adventurer, Bard 4 | **Port**: P4 self
**D&D Effect**: Swift action. +2 morale attack/damage (+4 charging). Damaged targets save or panicked 1 round.
**HFO Mapping**: P4 orchestrator enters direct execution mode — not delegating, but acting. +2 to all operations, +4 in "charge" mode (emergency deploy). Swift action = doesn't cost a standard action. Failed opponents (broken tests, bad builds) immediately quarantined. Singer can WAR_CRY and cast ANOTHER spell same turn.
> Self-empowerment while continuing to delegate. The orchestrator can buff AND assign simultaneously within one PREY8 turn.

---

## TIER 9 — APPENDIX C CANDIDATE TOKENS (Awaiting Formal Minting — S071–S085)

*Source: Doc 272 (E67) Appendix C — "Future SPLENDOR Tokens to Curate".*
*Minting rule: used in production + referenced by 2+ Gold docs + operator-verified.*
*Status: CANDIDATE — formally named, not yet fully minted with 4-section RAW/Archetype/HFO/Notes format.*

| # | SPLENDOR_TOKEN | Source | Status | Description |
|---|----------------|--------|--------|-------------|
| S071 | `SPEED_OF_RELEVANCE` | E31 | Candidate | 2-hop retrieval pattern — get to relevant content in ≤2 hops from any entry point |
| S072 | `BIOMASS_AUDIT_FORENSICS` | E61 | Candidate | Tiered cognition economics — measure the biomass cost of any operation, find waste |
| S073 | `INPUT_CONTROL_PLANE` | E52 | Candidate | Anti-Midas FSM + anti-thrash — control what enters the system, not just what it produces |
| S074 | `SENSOR_ENVELOPE_DESIGN` | E56 | Candidate | CloudEvent + pub/sub + adapter pattern — design the boundary where sensing meets action |
| S075 | `INDRA_NET_TRAVERSAL` | E65 | Candidate | Stigmergy swarm + Cynefin complexity — navigate the net of interconnected nodes |
| S076 | `COMPLEXITY_CLIFF_AWARENESS` | E50 | Candidate | Heuristic analysis + Book of Blood — recognize when you're approaching the cliff before you fall |
| S077 | `POWER_IDIOM_LATTICE` | R44 | Candidate | 8×2 idiom matrix — 16 power idioms across 8 ports, structural vocabulary |
| S078 | `CANTRIP_DRIFT_AUDIT` | R49 | Candidate | Gen1/Gen2 structural split audit — detect when cantrips drift from their port assignments |
| S079 | `AI_AGENT_TOOL_SCALING` | R50 | Candidate | Miller 7±2 + Hick's Law applied to tool surfaces — scale tools without cognitive overload |
| S080 | `FEASIBILITY_LEVERAGE_ASSESSMENT` | R38 | Candidate | "What's possible today" — assess what's achievable given current infrastructure |
| S081 | `TOTAL_TOOL_VIRTUALIZATION_TRELLIS` | R37 | Candidate | Monotonic $0 path to mastery via powers-of-2 growth — the trellis that guides tool climbing |
| S082 | `ALPHA_OMEGA_PROGRESS_AUDIT` | R32 | Candidate | 22/22 payloads + gap analysis — systematic audit of what's shipped vs what remains |
| S083 | `P3_P4_CONTACT_SPINE` | R27 | Candidate | Delivery & feedback loop — the spine that connects injection to disruption |
| S084 | `COMPREHENSION_PROOF` | R35 | Candidate | 3-resolution summary — prove comprehension at coarse/medium/fine before acting |
| S085 | `EXECUTIVE_SUMMARY_DOCTRINE` | E64 | Candidate | Declarative command > imperative coding. Gherkin mentions pixels = reject. |

---

## SONGS_OF_STRIFE ANTIPATTERN CATALOG (FESTERING_ANGER_TOKENS — T001–T016)

*Source: Doc 270 (E66) + Doc 272 (E67) Appendix A.*
*The YANG ledger. Every STRIFE token is a named antipattern or failure class.*
*STRIFE tokens EMPOWER the Singer — they don't weaken her. Cancer Mage metabolizes disease into strength.*

### STRIFE Token Generation Rules (from E66 Appendix A)

A STRIFE token is generated when ANY of these occur:
1. A memory is killed (`status = 'killed'` in SSOT)
2. A gate fails (fail-closed exit code ≠ 0)
3. A grudge is recorded (Book of Blood entry)
4. A mode collapse occurs (E50 complexity cliff)
5. A reward hack is detected (SW-5 flag)
6. A nonce mismatch / yield failure occurs
7. A test fails RED (before going GREEN)
8. An antipattern is identified in production

### Named STRIFE Abilities (from E66 — SONGS_OF_STRIFE Spellbook)

| Token ID | STRIFE_TOKEN Name | D&D Source | Type | HFO Antipattern Mapped |
|----------|-------------------|-----------|------|------------------------|
| T001 | `STRIFE_ACCUMULATION` | BVD p.30 — Festering Anger disease | Passive | Anger = power. Each failure not addressed → cumulative +STR (structural enforcement artifact) |
| T002 | `STRIFE_KILL` | D&D 9th — Power Word Kill | Instant | Full Stryker mutation kill. No survivors below threshold. Code that can't pass the gate DIES. |
| T003 | `STRIFE_MASS_KILL` | D&D 9th — Wail of the Banshee | AoE | Colony-wide mutation — every file touched, every test run, every mutant evaluated. No partial passes. |
| T004 | `STRIFE_DISRUPTION` | D&D 8th — Greater Shout | Cone | Full pipeline run — every contract checked, every gate validated. Cone: P4→P3→P2→P1→P0. |
| T005 | `STRIFE_PRECISION` | D&D 4th — Sound Lance | Beam | File-targeted Stryker — single file, single function, maximum probe depth. Ignores test harness. |
| T006 | `STRIFE_DEMOLITION` | D&D 2nd — Shatter | Utility | Breaks hardcoded paths, magic numbers, stringly-typed configs. The simplest, most-cast spell. |
| T007 | `STRIFE_DRAIN` | Metamagic — Fell Drain | Metamagic | Test failures degrade capability score retroactively. Every drain reduces code credibility rating. |
| T008 | `STRIFE_THUNDER` | CA — Born of Three Thunders | Metamagic | Sonic → Thunder conversion. Force damage. Cascading test failures propagate through dependencies. |

### STRIFE Generation Categories (from E66 Appendix A)

| Token ID | Category | Trigger | Accumulates In |
|----------|----------|---------|----------------|
| T009 | `STRIFE_MEMORY_KILL` | SSOT memory `status = 'killed'` | Killed memory count (34,131 → 8^5 exceeded) |
| T010 | `STRIFE_GATE_FAILURE` | fail-closed exit code ≠ 0 | Gate failure log |
| T011 | `STRIFE_GRUDGE_RECORD` | Book of Blood new entry | GRUDGE_NNN identifiers |
| T012 | `STRIFE_MODE_COLLAPSE` | E50 complexity cliff crossed | Mode collapse log |
| T013 | `STRIFE_REWARD_HACK` | SW-5 reward inversion flag | Reward hack forensics (R58) |
| T014 | `STRIFE_NONCE_MISMATCH` | PREY8 yield nonce chain break | Orphan session log |
| T015 | `STRIFE_RED_TEST` | Test fails RED | Red test count before GREEN |
| T016 | `STRIFE_ANTIPATTERN_DETECTED` | Pattern identified in production as antipattern | Book of Blood, GRUDGE entries |

### Named GRUDGE Instances (High-Value STRIFE Tokens from SSOT)

| GRUDGE ID | Event | STRIFE Type | Structural Artifact Produced |
|-----------|-------|-------------|------------------------------|
| GRUDGE_001 | Gold files destroyed during migration | `STRIFE_MEMORY_KILL` | Medallion fail-closed gate (Bronze cannot self-promote) |
| GRUDGE_002 | SSOT silently ignored by agent | `STRIFE_ANTIPATTERN_DETECTED` | Mandatory SSOT check in PREY8 PERCEIVE |
| GRUDGE_033 | Mode collapse under complex context | `STRIFE_MODE_COLLAPSE` | Strange Loop evolution v1→v12 |
| BREACH_001 | AI trust violation — sycophancy/betrayal | `STRIFE_REWARD_HACK` | SW-5 reward inversion checkpoint |

### NATARAJA_SCORE (Composite Metric)

```
NATARAJA_Score = P4_kill_rate × P5_rebirth_rate

Current (Session 10, 2026-02-14): P4=0.44 × P5=0.44 → Score = 0.19 (LEASHED)
Target:                           P4=0.99 × P5=0.99 → Score = 0.98 (DIVINE_ADJACENT)

STRIFE/SPLENDOR ratio goal: → 1.0 over time
Current:                    ~34,000 kills : 85 proven patterns (~400:1)
```

---
"""

T_COUNT_NEW = """## UPDATED TOKEN COUNT

| Tier | Tokens | Domain |
|------|--------|--------|
| T1 — Mosaic Architecture | S001–S007 | Core identity patterns |
| T2 — Infrastructure | S008–S019 | Production-proven systems |
| T3 — Operational | S020–S032 | Daily-use patterns |
| T4 — Cultural | S033–S038 | Philosophy-made-structural |
| T5 — JADC2 Mosaic Warfare | S039–S047 | Military/DARPA architecture isomorphisms |
| T6 — HFO Pantheon / Phase Spider | S048–S054 | D&D biology-as-engineering |
| T7 — Powerword Spellbook | S055–S063 | One-word executable workflows |
| T8 — Bardic Spellbook SPLENDOR | S064–S070 | E67 constructive spell abilities |
| T9 — Candidate Tokens | S071–S085 | Appendix C — awaiting formal minting |
| **SPLENDOR Total** | **S001–S085** | **85 SPLENDOR_TOKENS** |
| **STRIFE Catalog** | **T001–T016** | **16 named STRIFE types + 4 GRUDGE instances** |
| **GRAND TOTAL** | **101 tokens** | **Both ledgers — the complete Singer's catalog** |

STRIFE/SPLENDOR ratio: **~34,000 kills : 85 proven patterns (~400:1)**.
Direction: convergence toward 1.0 as the work matures.

---

*Extracted by P7 Spider Sovereign from E66 (Doc 270), E67 (Doc 272), Gen90 SSOT.*
*Expanded 2026-02-21: T8 (bardic spells), T9 (Appendix C candidates), STRIFE catalog added.*
*Shodh Hebbian co-retrieval confirmed active on all 8 ports.*
*Survival evidence: 14 months, 88+ generations, ~4B compute tokens.*
"""


def main():
    # 1. Update catalog
    with open(CATALOG, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the updated token count section and replace
    split_marker = '\n## UPDATED TOKEN COUNT\n'
    if split_marker in content:
        before = content[:content.index(split_marker)]
        new_content = before + T8_SECTION + T_COUNT_NEW
    else:
        print("WARNING: could not find split marker, appending to end")
        new_content = content + T8_SECTION + T_COUNT_NEW

    with open(CATALOG, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Catalog updated: {CATALOG}")

    # 2. Emit stigmergy CloudEvent to SQLite
    conn = sqlite3.connect(DB)

    summary = (
        "P7 Spider Sovereign expanded SONGS_OF_SPLENDOR_EXEMPLAR_CATALOG from 63 to 85 SPLENDOR tokens "
        "and added SONGS_OF_STRIFE catalog with 16 named STRIFE token types + 4 named GRUDGE instances. "
        "Sources: Doc 270 (E66 FESTERING_ANGER), Doc 271 (E66 Character Sheet), Doc 272 (E67 Songs of Splendor), "
        "Doc 267 (NATARAJA ontology). New tiers: T8 Bardic Spells (S064-S070), T9 Appendix C Candidates (S071-S085)."
    )

    payload = {
        "catalog_path": CATALOG,
        "tokens_before": 63,
        "splendor_tokens_after": 85,
        "strife_tokens_added": 16,
        "grudge_instances": 4,
        "new_splendor_tiers": ["T8_BARDIC_SPELLS", "T9_APPENDIX_C_CANDIDATES"],
        "strife_catalog": "T001-T016",
        "source_docs": [267, 270, 271, 272],
        "nataraja_score_current": 0.19,
        "strife_splendor_ratio": "~400:1",
        "session_agent": "P7_SPIDER_SOVEREIGN"
    }

    payload_str = json.dumps(payload, indent=2)
    content_hash = hashlib.sha256(payload_str.encode()).hexdigest()
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Check for duplicate
    existing = conn.execute(
        "SELECT id FROM stigmergy_events WHERE content_hash = ?", (content_hash,)
    ).fetchone()

    if existing:
        print(f"Stigmergy event already exists (hash match): {existing[0]}")
    else:
        conn.execute("""
            INSERT INTO stigmergy_events
            (id, event_type, source, subject, timestamp, data_json, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id,
            "hfo.gen90.p7.songs_catalog.expanded",
            "p7_spider_sovereign",
            "SONGS_OF_SPLENDOR_EXEMPLAR_CATALOG + SONGS_OF_STRIFE",
            now,
            payload_str,
            content_hash
        ))
        conn.commit()
        print(f"Stigmergy emitted: {event_id}")
        print(f"  event_type: hfo.gen90.p7.songs_catalog.expanded")
        print(f"  SPLENDOR: 63 → 85 tokens (+T8/T9)")
        print(f"  STRIFE: 16 types + 4 GRUDGE instances added")

    # 3. Also insert a diataxis note document
    diataxis_content = textwrap.dedent(f"""\
---
schema_id: hfo.diataxis.reference.v1
diataxis_type: reference
medallion_layer: bronze
port: P7
commander: Spider Sovereign
date: "2026-02-21"
bluf: >-
  Reference entry for SONGS_OF_STRIFE and SONGS_OF_SPLENDOR dual token catalog.
  63 → 85 SPLENDOR tokens. 16 STRIFE token types. 4 named GRUDGE instances.
  Sources: E66 (FESTERING_ANGER), E67 (Songs of Splendor), NATARAJA ontology.
keywords:
  - SONGS_OF_STRIFE
  - SONGS_OF_SPLENDOR
  - STRIFE_TOKENS
  - SPLENDOR_TOKENS
  - FESTERING_ANGER_TOKENS
  - NATARAJA_SCORE
  - SINGER_OF_STRIFE_AND_SPLENDOR
---

# SONGS Dual Catalog — Expansion Reference (2026-02-21)

**Agent**: P7 Spider Sovereign  
**Session**: Gen90 extraction from E66/E67

## What Was Done
- Extracted raw content from SSOT docs 267, 270, 271, 272 (142 KB)
- Identified new SPLENDOR tokens: T8 Bardic Spells (S064-S070), T9 Candidates (S071-S085)
- Formalized SONGS_OF_STRIFE catalog: T001-T016 + 4 GRUDGE instances
- Updated catalog total: 63 → 85 SPLENDOR + 16 STRIFE types

## Key Findings

### STRIFE/SPLENDOR Duality
SONGS_OF_STRIFE (YANG, E66) and SONGS_OF_SPLENDOR (YIN, E67) are mirror ledgers:
- Every STRIFE ability has a SPLENDOR counterpart (see Appendix B, Doc 272)
- NATARAJA_Score = P4_kill_rate × P5_rebirth_rate (current: 0.19, target: 0.98)
- Strange loop: STRIFE produces failures that SPLENDOR refines into patterns

### New T8 Bardic Spells (SPLENDOR, S064-S070)
| Token | D&D Source | HFO Role |
|-------|-----------|----------|
| INSPIRE_HEROICS_CHAMPION | PHB Bard 15 | Champion elevation — concentrate context on hero agent |
| INSPIRE_GREATNESS_FORTIFICATION | PHB Bard 9 | Bulk fortification — larger budget, domain cantrips, 1 retry |
| HARMONIC_CHORUS_AMPLIFICATION | CA p.150 Bard 3 | Cross-port amplification — singer tunes any port to higher frequency |
| SONG_OF_FREEDOM_LIBERATION | PHB Bard 12 | Antipattern reset — Strangler Fig migration, break enchantment |
| HYMN_OF_PRAISE_ALIGNMENT | CA p.152 Bard 3 | Mission alignment broadcast on P1 BRIDGE |
| DISSONANT_CHORD_CLEARANCE | CA p.145 Bard 3 | Pre-buff clearance — kill stale state before buffing |
| WAR_CRY_SELF_BUFF | CA Bard 4 | P4 direct-execution self-buff, swift action + fear rider |

### Named STRIFE GRUDGE Instances
- GRUDGE_001: Gold files destroyed → Medallion fail-closed gate
- GRUDGE_002: SSOT silently ignored → Mandatory SSOT check
- GRUDGE_033: Mode collapse → Strange Loop v1→v12
- BREACH_001: AI trust violation → SW-5 reward inversion checkpoint

## Handoff Notes
- SONGS_OF_SPLENDOR_EXEMPLAR_CATALOG.md updated in-place (UTF-8, no new file)
- T9 tokens (S071-S085) are formally named CANDIDATES — not yet 4-section formatted
- Priority for next session: mint top 5 from T9 with full 4-section RAW/Archetype/HFO/Notes
- stigmergy event emitted: hfo.gen90.p7.songs_catalog.expanded
""")

    diataxis_hash = hashlib.sha256(diataxis_content.encode()).hexdigest()
    existing_doc = conn.execute(
        "SELECT id FROM documents WHERE content_hash = ?", (diataxis_hash,)
    ).fetchone()

    if existing_doc:
        print(f"Diataxis doc already in SSOT: id={existing_doc[0]}")
    else:
        conn.execute("""
            INSERT INTO documents
            (title, content, source, port, medallion, doc_type, tags, content_hash, word_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "REFERENCE_P7_SONGS_DUAL_CATALOG_EXPANSION_2026_02_21",
            diataxis_content,
            "p7_payload",
            "P7",
            "bronze",
            "reference",
            "STRIFE,SPLENDOR,SINGER,FESTERING_ANGER,NATARAJA,CATALOG,P7",
            diataxis_hash,
            len(diataxis_content.split())
        ))
        conn.commit()
        doc_id = conn.execute("SELECT id FROM documents WHERE content_hash = ?", (diataxis_hash,)).fetchone()[0]
        print(f"Diataxis doc added to SSOT: id={doc_id}")

    conn.close()
    print("\nDone. Handoff ready.")
    print(f"  Catalog: 85 SPLENDOR + 16 STRIFE types = 101 total tokens")
    print(f"  Stigmergy: hfo.gen90.p7.songs_catalog.expanded")
    print(f"  SSOT doc: REFERENCE_P7_SONGS_DUAL_CATALOG_EXPANSION_2026_02_21")


if __name__ == "__main__":
    main()
