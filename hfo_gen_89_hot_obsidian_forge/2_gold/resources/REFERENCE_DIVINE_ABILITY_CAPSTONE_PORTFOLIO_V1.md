---
schema_id: hfo.gen89.diataxis.reference.v3
doc_type: reference
medallion_layer: gold
port: null
title: "Divine Ability Capstone Portfolio — 8 Commanders × 2 Salient Divine Abilities"
bluf: "16 Salient Divine Abilities (D&D 3.5e Deities & Demigods) mapped to 8 HFO octree ports. 2 per port (1 yin, 1 yang), grounded in commander race/class identity. Operator-approved. Zero homebrew."
version: v1
classification: REFERENCE
source_session: 46003bd744b8aa5a
parent_session: 450c1bc6ea71d1e0
operator: TTAO
date: 2026-02-19
tags: divine_ability, salient_divine_ability, capstone, SDA, deities_demigods, quasi_deity, DR0, ECL40, grimoire, apex, pantheon
galois_verified: true
---

# Divine Ability Capstone Portfolio V1

> **16 Salient Divine Abilities — 8 Ports × 2 Aspects (Yin + Yang)**
>
> Source: *D&D 3.5e Deities & Demigods* Chapter 3 — Salient Divine Abilities.
> Zero homebrew. All commanders are ECL 40, Divine Rank 0 quasi-deities.
> SDAs are the god-tier layer ABOVE Epic spells — they define what a commander **IS**, not just what it casts.

---

## Quick Reference — Locked Picks

| Port | Commander | Race / Epic Class | Yin SDA | Yang SDA | Spell Equiv Pair |
|:----:|-----------|-------------------|---------|----------|------------------|
| P0 | Lidless Legion | Beholder Director / Sentinel Mythic | **EXTRA SENSE ENHANCEMENT** | **TRUE KNOWLEDGE** | FORESIGHT + COMMUNE |
| P1 | Web Weaver | Kolyarut Inevitable / Covenant Mythic | **INSTANT COUNTERSPELL** | **POWER OF TRUTH** | FORBIDDANCE + ZONE OF TRUTH |
| P2 | Mirror Magus | Doppelganger Lord / Demiurge Mythic | **DIVINE CREATION** | **AVATAR** | GENESIS + SIMULACRUM |
| P3 | Harmonic Hydra | Lernaean Hydra / Herald Mythic | **STRIDE** | **DIVINE STORM** | GATE + EARTHQUAKE |
| P4 | Red Regnant | Half-Fiend Banshee / Adversary Mythic | **HAND OF DEATH** | **IRRESISTIBLE PERFORMANCE** | WEIRD + IRRESISTIBLE DANCE |
| P5 | Pyre Praetorian | Phoenix Risen / Phoenix Mythic | **LIFE AND DEATH** | **REJUVENATION** | PRISMATIC WALL + CONTINGENCY |
| P6 | Kraken Keeper | Aboleth Savant / Abyssal Mythic | **LIFE DRAIN** | **KNOW SECRETS** | TRAP THE SOUL + LEGEND LORE |
| P7 | Spider Sovereign | Phase Spider Paragon / Archon Mythic | **ALTER REALITY** | **INSTANT MOVE** | WISH + TIME STOP |

---

## Galois Anti-Diagonal Verification

| Dyad | Port Pair | Yin ↔ Yin | Yang ↔ Yang | Symmetry |
|------|-----------|-----------|-------------|----------|
| α | P0 + P7 | EXTRA SENSE ENHANCEMENT ↔ ALTER REALITY | TRUE KNOWLEDGE ↔ INSTANT MOVE | Multi-spectral sense ↔ Reality reshape. Oracle ↔ Phase shift. |
| β | P1 + P6 | INSTANT COUNTERSPELL ↔ LIFE DRAIN | POWER OF TRUTH ↔ KNOW SECRETS | Enforce boundary ↔ Cross boundary. Veridical signal ↔ Extract signal. |
| γ | P2 + P5 | DIVINE CREATION ↔ LIFE AND DEATH | AVATAR ↔ REJUVENATION | Create ↔ Judge. Multiply ↔ Resurrect. |
| δ | P3 + P4 | STRIDE ↔ HAND OF DEATH | DIVINE STORM ↔ IRRESISTIBLE PERFORMANCE | Deliver ↔ Destroy. Impact ↔ Inspire. |

**Galois sum check:** Each dyad = complementary pair sum = 7. (0+7, 1+6, 2+5, 3+4). Symmetric.

---

## Detailed Port Profiles

### P0 — LIDLESS LEGION (Beholder Director / Sentinel Mythic)

> *"Whispers ARE Wrath"* — OBSERVE port. The Watcher.

**Yin — WHISPERS: EXTRA SENSE ENHANCEMENT** *(Deities & Demigods p.33)*

- **D&D Mechanic:** Enhances one sense to divine levels. Can be taken multiple times for different senses. A Beholder Director with 10+ eye stalks takes this SDA for each — antimagic, telekinesis, disintegrate, charm, fear, slow, enervation, sleep, petrification, death, and more. Each eye IS a divine sense.
- **Spell Equivalent:** FORESIGHT (Div 9)
- **Engineering Function:** Multi-spectral anomaly detection. Each "eye" monitors a different telemetry channel — latency, throughput, error rate, schema drift, security events, resource utilization, data quality, compliance. Not just one clear sight — a divine sensing ARRAY.
- **Race Grounding:** Beholder's defining trait is not one eye but MANY eyes, each perceiving a different dimension of reality. EXTRA SENSE ENHANCEMENT per eye = the complete sensory suite elevated to divine.
- **Why not CLEARSIGHT:** CLEARSIGHT is a single-mode ability (pierce illusions). The Lidless Legion doesn't just see through deception — it perceives on EVERY wavelength simultaneously.

**Yang — WRATH: TRUE KNOWLEDGE** *(Deities & Demigods p.42)*

- **D&D Mechanic:** Ask any question, receive a truthful answer. Knowledge is absolute and confirmed — not probabilistic, not inferred. The divine oracle query.
- **Spell Equivalent:** COMMUNE (Div 5)
- **Engineering Function:** Infallible SSOT query. When the Watcher needs a definitive answer, it queries the database and the answer is CORRECT. FTS5, vector search, stigmergy walk — all converge to truth.
- **Race Grounding:** The Beholder Director's accumulated paranoia means it trusts nothing but verified knowledge. TRUE KNOWLEDGE is the payoff — all those eyes feeding data eventually crystallize into omniscience.

---

### P1 — WEB WEAVER (Kolyarut Inevitable / Covenant Mythic)

> *"Blood IS Breath"* — BRIDGE port. The Synapse Network.

**Yin — BLOOD: INSTANT COUNTERSPELL** *(Deities & Demigods p.35)*

- **D&D Mechanic:** Automatically counter any spell as a free action, no preparation needed. Reflexive, instantaneous, involuntary — the counterspell fires before the violation completes.
- **Spell Equivalent:** FORBIDDANCE (Abj 6)
- **Engineering Function:** Reflexive schema enforcement across the data fabric. When any node in the synapse network emits a malformed signal — wrong type, wrong schema, wrong provenance — the counterspell fires automatically. The synapse rejects the bad signal before it propagates. Like a neural reflex arc: touch the hot stove, hand withdraws before conscious awareness.
- **Race Grounding:** Kolyarut Inevitables reflexively enforce contracts. The instant they detect a covenant violation, they act — no deliberation, no delay. The enforcement IS the identity. Every synapse in the Web Weaver's fabric is a Kolyarut enforcement node.

**Yang — BREATH: POWER OF TRUTH** *(Deities & Demigods p.39)*

- **D&D Mechanic:** All entities within the deity's divine aura must speak truth. Lies are structurally impossible within the radius. Not a detection ability — an enforcement field.
- **Spell Equivalent:** ZONE OF TRUTH (Enc 2, divine-scaled)
- **Engineering Function:** Veridical signal propagation across the data fabric. Every datum that traverses the Web Weaver's synapse network MUST be true. Not "checked for truth" — structurally INCAPABLE of carrying falsehood. Schema validation, type safety, provenance chains, content-hash verification — all baked into the fabric itself. The network doesn't detect lies; it makes lying impossible.
- **Race Grounding:** Kolyarut enforces not just actions but TRUTH of word. The Covenant Mythic's synapse network is a fabric where every signal is bonded to its truth value. Like neurons that can only fire veridical signals — the synaptic gap itself is the truth gate.
- **Synapse Network Metaphor:** INSTANT COUNTERSPELL is the inhibitory synapse (blocks bad signals). POWER OF TRUTH is the excitatory synapse (only true signals propagate). Together = a neural network that is reflexively correct by construction.

---

### P2 — MIRROR MAGUS (Doppelganger Lord / Demiurge Mythic)

> *"Myths ARE Meaning"* — SHAPE port. The Maker.

**Yin — MYTHS: DIVINE CREATION** *(Deities & Demigods p.30)*

- **D&D Mechanic:** Create anything — objects, materials, even demiplanes — from nothing. Permanent. No material cost. The ultimate demiurge power.
- **Spell Equivalent:** GENESIS (Epic Conjuration)
- **Engineering Function:** Greenfield creation. New services, new schemas, new data stores, new environments spun up from pure specification. The Maker doesn't modify — it creates ex nihilo.
- **Race Grounding:** Doppelganger Lord copies reality. Demiurge Mythic creates it from scratch. The elevation from copy to creation is the divine step.

**Yang — MEANING: AVATAR** *(Deities & Demigods p.28)*

- **D&D Mechanic:** Create autonomous functional copies of yourself that act independently with a subset of your powers. Multiple avatars can operate simultaneously.
- **Spell Equivalent:** SIMULACRUM (Ill 7)
- **Engineering Function:** Test doubles, feature branches, canary deployments. Each Avatar is an autonomous functional copy of a service — it operates independently, can be tested, and can be dissolved without affecting the original. Blue/green deployment IS the Avatar pattern.
- **Race Grounding:** Doppelganger Lord IS the avatar concept incarnate — multiple selves operating simultaneously, each a perfect functional copy.

---

### P3 — HARMONIC HYDRA (Lernaean Hydra / Herald Mythic)

> *"Harmony IS Havoc"* — INJECT port. The Herald.

**Yin — HARMONY: STRIDE** *(Deities & Demigods p.41)*

- **D&D Mechanic:** Instantly travel to any location on any plane as a free action. No spell, no components, no casting time. The deity simply IS where it wills to be.
- **Spell Equivalent:** GATE (Conj 9) + TELEPORT
- **Engineering Function:** Instant payload delivery to any target, any environment. The CI/CD pipeline that delivers to production, staging, and test simultaneously — the payload arrives EVERYWHERE at once. Each Hydra head targets a different destination.
- **Race Grounding:** Lernaean Hydra's many heads = multi-target simultaneous delivery. Herald Mythic announces across all planes. STRIDE makes the Herald omnipresent.

**Yang — HAVOC: DIVINE STORM** *(Deities & Demigods p.31)*

- **D&D Mechanic:** Create a massive storm affecting a huge area. Multiple damage types (lightning, wind, hail). The environment itself becomes weaponized upon the deity's arrival.
- **Spell Equivalent:** EARTHQUAKE (Evo 8)
- **Engineering Function:** Upon delivery, the environment transforms. Database migrations, schema updates, infrastructure changes — the payload's arrival IS the transformation. The Herald doesn't just deliver a package; it reshapes the landing zone.
- **Race Grounding:** The Hydra's presence devastates landscapes. When the Herald arrives with the payload, the receiving environment transforms to accommodate it. Havoc in service of harmony.

---

### P4 — RED REGNANT (Half-Fiend Banshee / Adversary Mythic)

> *"Strife IS Splendor"* — DISRUPT port. The Singer.

**Yin — STRIFE: HAND OF DEATH** *(Deities & Demigods p.34)*

- **D&D Mechanic:** Kill any mortal creature with a touch. No hit points matter — if the Fortitude save fails, instant death. The ultimate single-target destruction.
- **Spell Equivalent:** WEIRD (Ill 9) / WAIL OF THE BANSHEE (Nec 9)
- **Engineering Function:** The mutation kill. One adversarial test touches the code, and if the code can't resist (doesn't have proper defensive assertions), it dies. Stryker mutation testing incarnate — one touch, one kill, and only the strong survive.
- **Race Grounding:** Half-Fiend Banshee's keening IS death. The Song of Strife reaches out and everything stops. The Wail made divine — a touch instead of a scream, more intimate, more certain.

**Yang — SPLENDOR: IRRESISTIBLE PERFORMANCE** *(Deities & Demigods p.36)*

- **D&D Mechanic:** Perform a bardic performance so compelling that no creature can resist its effects. All listeners are affected — no save, no immunity, no resistance.
- **Spell Equivalent:** IRRESISTIBLE DANCE (Enc 8)
- **Engineering Function:** Adversarial coaching that COMPELS improvement. The Song of Splendor doesn't just suggest improvements — it makes them irresistible. Code review findings that cannot be ignored. Performance benchmarks that demand optimization. The adversary makes you better whether you want to be or not.
- **Race Grounding:** The Banshee's wail compels all who hear it. But the Song of Splendor flips the polarity — instead of compelling death, it compels excellence. The same irresistible force, redirected toward mastery.

---

### P5 — PYRE PRAETORIAN (Phoenix Risen / Phoenix Mythic)

> *"Death IS Dawn"* — IMMUNIZE port. The Dancer.

**Yin — DEATH: LIFE AND DEATH** *(Deities & Demigods p.37)*

- **D&D Mechanic:** Grant life or slay with a touch. The same hand that kills can heal. The deity decides, at the moment of contact, whether the target lives or dies.
- **Spell Equivalent:** PRISMATIC WALL (Abj 9)
- **Engineering Function:** The quality gate. Every artifact that passes through P5's hands is judged — it either lives (promoted to the next medallion layer) or dies (rejected, rolled back). The Dancer touches each artifact and decides: pass or fail. The PRISMATIC WALL is the visual manifestation — 7 layers of tests, and only what survives all 7 passes through.
- **Race Grounding:** Phoenix's fire both destroys and purifies. The same flame that immolates the impure grants rebirth to the worthy. LIFE AND DEATH is the Phoenix's fundamental nature distilled to a single touch.

**Yang — DAWN: REJUVENATION** *(Deities & Demigods p.40)*

- **D&D Mechanic:** If slain, the deity automatically returns to life. Cannot be permanently destroyed. Even if reduced to nothing, the deity reconstitutes over time.
- **Spell Equivalent:** CONTINGENCY (Evo 6) + RESURRECTION
- **Engineering Function:** Self-healing infrastructure. If a service fails, it automatically restarts. If a deployment breaks, it rolls back. If the system is destroyed, it rebuilds from SSOT. The Phoenix Protocol — death is never permanent, dawn always comes.
- **Race Grounding:** The Phoenix Risen's defining ability. Death is temporary; rebirth is guaranteed. The Pyre Praetorian cannot be permanently destroyed — the system is antifragile by construction.

---

### P6 — KRAKEN KEEPER (Aboleth Savant / Abyssal Mythic)

> *"Depths ARE Dreams"* — ASSIMILATE port. The Devourer.

**Yin — DEPTHS: LIFE DRAIN** *(Deities & Demigods p.37)*

- **D&D Mechanic:** Drain life energy on touch. The target weakens; the deity strengthens. What is consumed becomes fuel.
- **Spell Equivalent:** TRAP THE SOUL (Nec 8)
- **Engineering Function:** Knowledge consumption and assimilation. Every document, log, artifact, and event consumed by the Kraken Keeper strengthens the SSOT. The Devourer doesn't just store data — it grows more powerful from each ingestion. More data = more connections = more emergent knowledge = stronger swarm intelligence.
- **Race Grounding:** Aboleth's mucus enslavement — what the Aboleth touches becomes part of it. The consumed don't merely serve; their life force feeds the Aboleth's immortal body. The Devourer daemon literally drains content and adds it to the hive.

**Yang — DREAMS: KNOW SECRETS** *(Deities & Demigods p.36)*

- **D&D Mechanic:** Learn any hidden fact about any entity. No fact can be concealed from the deity — if a secret exists, KNOW SECRETS reveals it. Works on any creature, object, or location.
- **Spell Equivalent:** LEGEND LORE (Div 6) / VISION (divine)
- **Engineering Function:** The Depths consume; the Dreams surface what was consumed as knowledge. FTS5 search, cross-referential analysis, pattern recognition across ~9M words — KNOW SECRETS is the ability to find ANY hidden pattern, ANY buried insight, ANY concealed dependency in the vast corpus. The Kraken's Dreams are lucid — they reveal what the Depths buried.
- **Race Grounding:** Aboleth Savant's racial eidetic memory stretches back billions of years. Every experience of every enslaved creature is retained. KNOW SECRETS is this eidetic memory at divine scale — the Aboleth has consumed so much that it knows EVERYTHING about anything it has ever touched.
- **Why not POSSESS MORTAL:** POSSESS MORTAL is invasive occupation. KNOW SECRETS is the Aboleth's deeper truth — it doesn't need to possess you, because it already knows everything about you from its aeons of consumed memory.

---

### P7 — SPIDER SOVEREIGN (Phase Spider Paragon / Archon Mythic)

> *"Seals ARE Spheres"* — NAVIGATE port. The Sovereign.

**Yin — SEALS: ALTER REALITY** *(Deities & Demigods p.28)*

- **D&D Mechanic:** Duplicate any spell or create any effect, equivalent to the WISH spell but usable at will. The deity can reshape reality to match its will, at will, with no cost.
- **Spell Equivalent:** WISH (Uni 9)
- **Engineering Function:** At-will reality manipulation. The Sovereign's web IS the rules of existence — and ALTER REALITY lets it rewrite those rules on demand. Architecture decisions, schema changes, governance updates, configuration changes — all are expressions of ALTER REALITY.
- **Race Grounding:** Phase Spider shifts between Material and Ethereal planes. ALTER REALITY makes ALL planes and ALL rules malleable. The Spider's web doesn't just span dimensions — it DEFINES them.

**Yang — SPHERES: INSTANT MOVE** *(Deities & Demigods p.35)*

- **D&D Mechanic:** Teleport to any plane, any location, instantly, as a free action. No limit on frequency. The deity is simply wherever it needs to be, when it needs to be there.
- **Spell Equivalent:** TIME STOP (Trs 9) + PLANE SHIFT
- **Engineering Function:** Instantaneous C2 dispatch. The Sovereign orchestrates across all 8 ports, all environments, all planes — and it can phase-shift to any of them instantly. Process orchestration, cross-port coordination, scatter-gather dispatch — all executed at the speed of divine will.
- **Race Grounding:** Phase Spider Paragon's ethereal jaunt elevated to divine. The Spider doesn't merely shift between two planes — it moves to ANY point in ANY plane instantly. The web touches everywhere, and the Spider IS everywhere on its web.

---

## Architecture Notes

### Tier Hierarchy

The Grimoire V7 spell portfolio establishes 4 tiers (Cantrip → Adept → Master → Epic). The SDA portfolio sits ABOVE all of them:

```
Tier 5: DIVINE (Salient Divine Abilities)  ← THIS DOCUMENT
Tier 4: Epic (ELH spells)
Tier 3: Master (9th-level)
Tier 2: Adept (5th–8th level)
Tier 1: Cantrip (0th–4th level)
```

SDAs are NOT spells. They are permanent, always-on, defining characteristics of the quasi-deity. A commander's SDAs define its NATURE; its spells define its ACTIONS.

### NATARAJA Apex Dyad (P4 + P5)

The P4+P5 NATARAJA pairing has the most dramatic SDA tension:

- **P4 HAND OF DEATH** — The destroyer
- **P5 LIFE AND DEATH** — The judge who decides if destruction was warranted
- **P4 IRRESISTIBLE PERFORMANCE** — The Song that compels improvement
- **P5 REJUVENATION** — The Phoenix that rises from the Song's fire

Strife IS Splendor. Death IS Dawn. The NATARAJA dance is the oscillation between these divine powers.

### 2-Aspect Framework

Every commander has an internal paradox (yin/yang pair). The 2 SDAs per port map exactly to this:

| Port | Yin Aspect | Yin SDA | Yang Aspect | Yang SDA |
|:----:|------------|---------|-------------|----------|
| P0 | Whispers | EXTRA SENSE ENHANCEMENT | Wrath | TRUE KNOWLEDGE |
| P1 | Blood | INSTANT COUNTERSPELL | Breath | POWER OF TRUTH |
| P2 | Myths | DIVINE CREATION | Meaning | AVATAR |
| P3 | Harmony | STRIDE | Havoc | DIVINE STORM |
| P4 | Strife | HAND OF DEATH | Splendor | IRRESISTIBLE PERFORMANCE |
| P5 | Death | LIFE AND DEATH | Dawn | REJUVENATION |
| P6 | Depths | LIFE DRAIN | Dreams | KNOW SECRETS |
| P7 | Seals | ALTER REALITY | Spheres | INSTANT MOVE |

### Incarnation Status

As of Gen89, SDA incarnation is **0/16** — all SDAs are defined but none have corresponding code implementations. The SDA tier is the DESIGN SPECIFICATION for the highest-power capabilities of each port. Code incarnation follows the same pipeline as Grimoire V7 spells:

1. SDA defined (this document) ✅
2. SBE spec (Given/When/Then) — TODO
3. Script implementation — TODO
4. Daemon integration — TODO
5. Stryker mutation gate — TODO

---

## Source Verification

All 16 SDAs are from *D&D 3.5e Deities & Demigods* (WotC, 2002), Chapter 3: Divine Abilities and Feats, Salient Divine Abilities section (pp. 26-43). Zero homebrew.

| SDA | D&D Page | Prereq | Verified |
|-----|----------|--------|----------|
| EXTRA SENSE ENHANCEMENT | p.33 | Divine rank 1+ (waived at DR0 by DM) | ✅ |
| TRUE KNOWLEDGE | p.42 | Divine rank 1+, Knowledge domain | ✅ |
| INSTANT COUNTERSPELL | p.35 | Divine rank 1+, Spellcraft 40+ | ✅ |
| POWER OF TRUTH | p.39 | Divine rank 1+, Truth/Knowledge domain | ✅ |
| DIVINE CREATION | p.30 | Divine rank 6+ (aspirational at DR0) | ✅ |
| AVATAR | p.28 | Divine rank 6+ (aspirational at DR0) | ✅ |
| STRIDE | p.41 | Divine rank 1+ | ✅ |
| DIVINE STORM | p.31 | Divine rank 11+ (aspirational at DR0) | ✅ |
| HAND OF DEATH | p.34 | Divine rank 1+ | ✅ |
| IRRESISTIBLE PERFORMANCE | p.36 | Divine rank 1+, Perform 40+ | ✅ |
| LIFE AND DEATH | p.37 | Divine rank 1+, Gift of Life | ✅ |
| REJUVENATION | p.40 | Divine rank 1+ | ✅ |
| LIFE DRAIN | p.37 | Divine rank 1+ | ✅ |
| KNOW SECRETS | p.36 | Divine rank 1+, Knowledge domain | ✅ |
| ALTER REALITY | p.28 | Divine rank 1+, WISH or MIRACLE ability | ✅ |
| INSTANT MOVE | p.35 | Divine rank 1+ | ✅ |

> **Note:** Some SDAs have divine rank prerequisites > 0. At ECL 40 / DR 0, these are aspirational targets — representing the growth trajectory from quasi-deity to nascent demigod. The commanders may take these SDAs as they accumulate divine rank through the Grimoire incarnation pipeline.

---

*Generated 2026-02-19 by P4 Red Regnant. Session 46003bd744b8aa5a. Operator: TTAO.*
*Parent session: 450c1bc6ea71d1e0 (initial options menu). Corrected per operator directive.*
