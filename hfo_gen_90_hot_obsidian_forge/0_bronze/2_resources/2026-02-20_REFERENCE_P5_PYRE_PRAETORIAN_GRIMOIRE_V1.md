---
medallion_layer: bronze
mutation_score: 0
hive: V
hfo_header_v3: compact
schema_id: hfo.diataxis.reference.p5_grimoire.v1
mnemonic: "O·B·S·I·D·I·A·N = 8 ports = 1 octree"
title: "P5 Pyre Praetorian Grimoire — Complete Spell List v1"
bluf: >-
  Complete P5 spell list: 21 spells across Cantrip→Epic tiers. Three focus
  spells fully detailed: CONTINGENCY (auto-remediation triggers, 6th level),
  PRISMATIC_WALL (8-layer defense-in-depth health audit, 7th level),
  GREATER_RESURRECTION (improved Phoenix Protocol, 5th level). Every spell
  maps to existing code or explicit implementation TODO. D&D school: Evocation.
  MOSAIC tile: DEFEND. Powerword: IMMUNIZE. Workflow: DETECT→QUARANTINE→GATE→HARDEN→TEACH.
primary_port: P5
secondary_ports: [P2, P4]
commander: Pyre Praetorian
role: "P5 IMMUNIZE — blue team / gates"
tags: [bronze, forge:hot, diataxis:reference, p5, pyre-praetorian, grimoire,
      spellbook, contingency, prismatic-wall, resurrection, defense-in-depth,
      fail-closed, nataraja, evocation]
diataxis_type: reference
cross_references:
  - "SSOT #101: REFERENCE_OBSIDIAN_OCTAVE_8_SIGNATURE_SPELLS_V1"
  - "SSOT #411: REFERENCE_P5_PRISMATIC_WALL_DEFENSE_IN_DEPTH_V1"
  - "SSOT #85:  REFERENCE_LEGENDARY_COMMANDER_ABILITIES_SPELLBOOK_V1"
  - "SSOT #49:  REFERENCE_EPIC_SPELL_PROPOSALS_PER_PORT_V1"
  - "SSOT #128: Powerword Spellbook — 8 Legendary Commander Workflows"
  - "SSOT #9860: EXPLANATION_NATARAJA_WAIL_OF_THE_BANSHEE_GEN89_PHOENIX_PROTOCOL_V1"
  - "SSOT #69:  REFERENCE_HFO_PANTHEON_DND_DR0_CHARACTER_SHEETS (P5=Cleric/Sacred Exorcist/Risen Martyr)"
  - "SSOT #289: EXPLANATION_SELF_MYTH_WARLOCK_STAT_SHEET"
prey8_chain:
  session_id: 6b1e6bafdaba7ce9
  perceive_nonce: "3D887F"
  react_token: "9BC030"
  execute_token: "56B1CB"
generated: "2026-02-20"
author: "P4 Red Regnant (design) + TTAO (doctrine)"
---

# P5 PYRE PRAETORIAN GRIMOIRE — Complete Spell List (v1)

> **☲ Li (Fire) — Purifying, Illuminating, Consuming Weakness**
> *"That which does not kill us makes us stronger."* — Friedrich Nietzsche
> *"Exception creep: security bypass becomes default."* — Grimoire v11.1 Red Team

> **The Dancer of Death and Dawn does not fight fire with fire.**
> **She IS the fire. What she touches either becomes stronger or becomes ash.**
> **There is no middle ground. There is no exception. There is no bypass.**

---

## 0. Identity Card

| Field | Value |
|-------|-------|
| **Port** | P5 |
| **Commander** | Pyre Praetorian — Dancer of Death and Dawn |
| **Powerword** | IMMUNIZE |
| **Signature Spell** | CONTINGENCY (Evocation 6th) |
| **Legendary Ability** | PRISMATIC_WALL (8-layer defense-in-depth) |
| **D&D School** | Evocation (energy, force, warding effects) |
| **MOSAIC Tile** | DEFEND |
| **Trigram** | ☲ Li (Fire) |
| **D&D Class** | Cleric 20 / Sacred Exorcist 10 / Risen Martyr (SSOT #69) |
| **Dyad Partner** | P2 SHAPE (Safety Spine: Creation ↔ Immunization) |
| **Anti-Diagonal Partner** | P4 DISRUPT (NATARAJA: Singer ↔ Dancer) |
| **Workflow** | DETECT → QUARANTINE → GATE → HARDEN → TEACH |
| **Quote** | *"Ever tried. Ever failed. No matter. Try again. Fail again. Fail better."* |
| **Failure Mode** | Exception creep (bypass becomes default) or no feedback (gates block but don't teach) |

### The Dancer's Oath

```
I am the fire that purifies.
I am the gate that closes.
I am the wall that holds.
I am the resurrection that rises.
What I touch either becomes stronger or becomes ash.
There is no exception. There is no bypass.
Fail closed. Always.
```

---

## 1. Spell Tier Overview

| Tier | D&D Level | Spells | Cast Frequency | Automation |
|------|-----------|--------|----------------|------------|
| **Cantrip** | 0 | 4 spells | Always available | Fully automated (Ring 0) |
| **1st Circle** | 1-2 | 3 spells | Every patrol cycle (60-120s) | Automated (T1-T3 tasks) |
| **2nd Circle** | 3-4 | 3 spells | Triggered by conditions | Semi-automated |
| **3rd Circle** | 5 | 2 spells | Daily / on-demand | Operator or P7 initiated |
| **Signature** | 6 | 1 spell | Event-driven (CONTINGENCY) | ⭐ Fully automated when built |
| **Legendary** | 7 | 1 spell | Daily cast | ⭐ Audit + scoring |
| **High Magic** | 8 | 2 spells | Emergency / rare | Manual + automation |
| **Divine** | 9 | 2 spells | Catastrophe / epoch events | NATARAJA cycle |
| **Epic** | Epic | 2 spells | Cross-generational | Architecture-level |
| | | **20 spells total** | | |

---

## 2. The Complete Spell List

### Tier 0 — Cantrips (Ring 0, Always Available, Zero Cost)

*Deterministic checks that never reach the LLM. The fire that tests before it burns.*

| # | Spell | D&D Analog | HFO Function | Code Artifact | Status |
|---|-------|-----------|--------------|---------------|--------|
| C1 | **STABILIZE** | Stabilize (Cleric cantrip) | System health pulse — Ollama online, disk free, SSOT size, event count | `hfo_p5_pyre_praetorian.py` → `check_ollama_online()`, `check_disk_free_gb()`, `check_ssot_size_mb()`, `count_stigmergy_events()` | ✅ EXISTS |
| C2 | **DETECT MAGIC** | Detect Magic | Quick anomaly scan — orphaned nonces, stale sessions, pointer drift | `hfo_p5_pyre_praetorian.py` → `check_orphaned_nonces()` | ✅ EXISTS |
| C3 | **RESISTANCE** | Resistance | Resource ceiling enforcement — RAM, VRAM, disk thresholds against CEILINGS dict | `hfo_p5_pyre_praetorian.py` → `CEILINGS{}`, `resource_governance_preflight()` | ✅ EXISTS |
| C4 | **GUIDANCE** | Guidance | Check blessed pointer registry resolves — all PAL keys → valid paths | `hfo_pointers.py check` | ✅ EXISTS |

**Ring 0 Principle:** These never fail with an exception. They return structured
data (dict/list) or a sentinel value. They are the Dancer's heartbeat — always
on, always measuring.

---

### 1st Circle — Patrol Spells (Automated, Every Cycle)

*The Dancer's daily patrol. These run on every daemon cycle (60-120s).*

| # | Spell | D&D Analog | HFO Function | Code Artifact | Status |
|---|-------|-----------|--------------|---------------|--------|
| 1 | **PURIFICATION RITUAL** | Purify Food & Drink | SSOT integrity sweep — run all Ring 0 cantrips, write health event if anomaly found | `hfo_p5_daemon.py` → `IntegrityPatrolTask` (T1, every 120s) | ✅ EXISTS |
| 2 | **SANCTUARY** | Sanctuary | Session orphan reaper — find perceives without yields, auto-close after threshold, protect SSOT from accumulation | `hfo_p5_daemon.py` → `SessionOrphanReaper` (T2, every 300s) | ✅ EXISTS |
| 3 | **SHIELD OF FAITH** | Shield of Faith | Ollama model governance — enforce approved model list, unload unauthorized models from VRAM, maintain model lifecycle | `hfo_p5_daemon.py` → `OllamaModelGovernanceTask` (T3, every 600s) | ✅ EXISTS |

**1st Circle Principle:** Patrol spells run autonomously. They write stigmergy
events ONLY when anomalies are found (not on normal cycles — learned from the
spam incident). Silent when healthy, loud when sick.

---

### 2nd Circle — Watchdog Spells (Triggered, Conditional)

*These fire when specific conditions are detected. The Dancer's reflexes.*

| # | Spell | D&D Analog | HFO Function | Code Artifact | Status |
|---|-------|-----------|--------------|---------------|--------|
| 4 | **ZONE OF TRUTH** | Zone of Truth | 7-class anomaly detector — event_storm, memory_leak, pointer_drift, orphan_spike, heartbeat_gap, resource_ceiling, model_drift | `hfo_p5_daemon.py` → `AnomalyPatrolTask` (T4, every 60s) | ✅ EXISTS |
| 5 | **AUGURY** | Augury | LLM policy analyst — when anomaly detected, invoke AI to classify severity and recommend response | `hfo_p5_daemon.py` → `LLMPolicyAnalystTask` (T5, triggered by T4) | ✅ EXISTS |
| 6 | **DEATH WARD** | Death Ward | Rate limiter / circuit breaker — prevent SSOT write storms, terminal spawn floods, daemon cascade failures | `hfo_p5_daemon.py` → event throttle in Phoenix + quiet mode in banish | ⚠️ PARTIAL (guards exist but not unified as spell) |

**2nd Circle Principle:** Watchdog spells are reactive-within-bounds. They
detect anomalies (ZONE OF TRUTH), analyze them (AUGURY), and apply circuit
breakers (DEATH WARD). But they never auto-remediate — that's CONTINGENCY's job.

---

### 3rd Circle — Command Spells (Operator/P7 Initiated)

*These require deliberate invocation. The Dancer acts on command.*

| # | Spell | D&D Analog | HFO Function | Code Artifact | Status |
|---|-------|-----------|--------------|---------------|--------|
| 7 | **DISPEL MAGIC** | Dispel Magic | Clean daemon kill — `spell_banish(name, quiet=True)` with /F /T force-kill, no dialog, no spam | `hfo_p7_spell_gate.py` → `spell_banish()` with quiet mode | ✅ EXISTS |
| 8 | **REMOVE CURSE** | Remove Curse | Clear stuck state — reset spell gate state file, clear stale nonces, clean orphaned PID locks | `.p7_spell_gate_state.json` reset + orphan reaper manual trigger | ⚠️ PARTIAL |

---

### Focus Spell 1 — 5th Level: GREATER RESURRECTION ⭐

*The Phoenix Protocol elevated. Not a crude restart — a conscious, gated, fail-closed rebirth.*

---

#### 📜 GREATER RESURRECTION — Full Spell Card

| Field | Value |
|-------|-------|
| **D&D Spell** | Greater Resurrection (Necromancy/Conjuration 7th in 3.5e, reduced to 5th here for P5 tier structure) |
| **D&D Effect** | *"Restores life to a creature dead up to 10 years. Closes all wounds, cures diseases, restores lost body parts. The subject is alive and whole."* |
| **D&D School** | Necromancy (life/death manipulation) |
| **HFO Level** | 5th (3rd Circle — significant, daily budget) |
| **Material Component** | SSOT phylactery (the database IS the diamond worth 25,000 gp) |
| **Casting Time** | 1 patrol cycle (120s) |
| **Range** | All registered daemons in spell gate |
| **Duration** | Until next death |

##### HFO Fit

| HFO Field | Value |
|-----------|-------|
| **Function** | Daemon fleet resurrection with fail-closed pre-checks, cooldown windows, rate limiting, and graduated response |
| **Code Artifact** | `hfo_p5_daemon.py` → `SpellGatePhoenixTask` (T6, every 120s) |
| **Trigger** | Daemon marked `is_persistent=True` + state shows not running + cooldown expired |
| **Gate** | Feature flag `HFO_DAEMON_P5_BOOT_SUMMON_FLEET` must be `true` |
| **Fail-Closed** | Default OFF. Every resurrection gated by: (1) feature flag, (2) cooldown timer, (3) max retry count, (4) resource preflight |

##### Why "Greater" — Improvements Over Basic Resurrection

The original Phoenix (before this session's spam incident) was a **basic Raise Dead**:
- Crude: kill then restart, every cycle
- Noisy: SSOT event on every patrol cycle, even when nothing happened
- Hungry: no resource preflight, would resurrect into resource starvation
- Blind: no cooldown, would resurrect a crashlooper immediately

**GREATER RESURRECTION** adds:

| Improvement | D&D Analog | Implementation |
|-------------|-----------|----------------|
| **Cooldown window** | "Cannot be raised again for 1 day" | 300s minimum between resurrections per daemon |
| **Quiet mode** | "No material cost below 7th level" | `spell_banish(quiet=True)` — no prints, no SSOT events on clean operations |
| **Resource preflight** | "Diamond worth 25,000 gp required" | Check disk, RAM, VRAM, Ollama status before resurrecting |
| **Max retry count** | "Can only be cast once per creature per day" | 3 resurrections per daemon per hour, then escalate to operator |
| **Event throttle** | "Only the gods hear the prayer" | SSOT event ONLY when actual resurrection occurs, not on silent OK cycles |
| **is_persistent flag** | "Only the faithful may be raised" | Only daemons with `is_persistent=True` in DaemonSpec are eligible |
| **Graduated response** | "Raise Dead < Resurrection < Greater" | 1st attempt: gentle restart. 2nd: full kill+restart. 3rd: notify operator, stop trying |
| **Feature flag gate** | "The cleric must have the spell prepared" | `HFO_DAEMON_P5_BOOT_SUMMON_FLEET=true` required in .env |

##### Pseudocode

```python
async def cast_greater_resurrection(spell_gate_state: dict) -> ResurrectionReceipt:
    """
    GREATER_RESURRECTION: Daemon fleet resurrection with fail-closed gates.
    
    Improvement over basic Raise Dead:
    - Cooldown windows prevent crash-loop resurrection
    - Resource preflight prevents resurrecting into starvation
    - Event throttle prevents SSOT write storms
    - Graduated response escalates on repeated failures
    - Feature flag gate requires explicit operator authorization
    """
    
    # ── DETECT: Who is dead? ──
    dead_daemons = []
    for name, spec in spell_gate_state.items():
        if not spec.is_persistent:
            continue                          # Only the faithful may be raised
        if spec.is_alive():
            continue                          # The living need no resurrection
        if spec.cooldown_remaining_s() > 0:
            continue                          # Cannot be raised again yet
        if spec.resurrection_count_this_hour >= 3:
            continue                          # Max retries — escalate instead
            escalate_to_operator(f"{name} died 3× this hour")
        dead_daemons.append(name)
    
    if not dead_daemons:
        return ResurrectionReceipt(action="NONE", resurrected=[])  # Silent OK
    
    # ── QUARANTINE: Check if resurrection is safe ──
    preflight = resource_governance_preflight()  # Ring 1 check
    if not preflight.safe:
        return ResurrectionReceipt(
            action="BLOCKED",
            reason=f"Resource starvation: {preflight.violations}",
            resurrected=[]
        )
    
    # ── GATE: Feature flag check ──
    if not env_flag("HFO_DAEMON_P5_BOOT_SUMMON_FLEET"):
        return ResurrectionReceipt(action="DISABLED", resurrected=[])
    
    # ── HARDEN: Perform the resurrection ──
    resurrected = []
    for name in dead_daemons:
        attempt = spec.resurrection_count_this_hour + 1
        
        if attempt == 1:
            # Gentle restart — just summon
            result = spell_summon_familiar(name, force=False, quiet=True)
        elif attempt == 2:
            # Full kill + restart — banish first
            spell_banish(name, quiet=True)
            await asyncio.sleep(2)
            result = spell_summon_familiar(name, force=True, quiet=True)
        else:
            # 3rd attempt — give up, notify operator
            escalate_to_operator(f"{name} refuses resurrection")
            continue
        
        if result.success:
            resurrected.append(name)
            spec.last_resurrection = now()
            spec.resurrection_count_this_hour += 1
    
    # ── TEACH: Write SSOT event ONLY if work was done ──
    if resurrected:
        write_p5_event("hfo.gen89.p5.greater_resurrection", {
            "resurrected": resurrected,
            "dead_found": len(dead_daemons),
            "blocked": len(dead_daemons) - len(resurrected),
            "preflight": preflight.summary,
        })
    
    return ResurrectionReceipt(
        action="RESURRECTED",
        resurrected=resurrected,
        cooldown_applied=True,
    )
```

##### SBE Spec (Tier 1 — Invariant Scenarios)

```gherkin
Feature: GREATER_RESURRECTION — Daemon Fleet Revival

  # Tier 1: Invariant (MUST NOT violate)
  Scenario: Dead persistent daemon is resurrected
    Given daemon "singer" has is_persistent=True and is not running
    And cooldown has expired (>300s since last resurrection)
    And resource preflight passes
    And feature flag HFO_DAEMON_P5_BOOT_SUMMON_FLEET=true
    When GREATER_RESURRECTION patrol runs
    Then daemon "singer" is restarted
    And exactly 1 SSOT event is written

  Scenario: Non-persistent daemon is NOT resurrected
    Given daemon "tremorsense" has is_persistent=False and is not running
    When GREATER_RESURRECTION patrol runs
    Then daemon "tremorsense" remains dead
    And 0 SSOT events are written

  Scenario: Crash-looping daemon escalates after 3 attempts
    Given daemon "meadows" has resurrection_count_this_hour=3
    When GREATER_RESURRECTION patrol runs
    Then daemon "meadows" is NOT restarted
    And operator escalation notification is generated

  Scenario: Resource starvation blocks all resurrection
    Given disk_free_gb < 2.0 OR ram_available_mb < 500
    When GREATER_RESURRECTION patrol runs
    Then no daemons are resurrected
    And receipt shows action="BLOCKED" with resource details

  Scenario: Silent cycle writes nothing
    Given all persistent daemons are alive
    When GREATER_RESURRECTION patrol runs
    Then 0 SSOT events are written
    And no log output is produced
```

---

### Focus Spell 2 — 6th Level: CONTINGENCY ⭐⭐ (SIGNATURE SPELL)

*The signature spell of the Pyre Praetorian. Pre-choreographed defense.*

---

#### 📜 CONTINGENCY — Full Spell Card

| Field | Value |
|-------|-------|
| **D&D Spell** | Contingency (Evocation 6th) |
| **D&D Effect** | *"You store a spell of 5th level or lower that triggers automatically when a stated condition occurs. The trigger must be clear, unambiguous, and detectable. The stored spell fires without your action."* |
| **D&D School** | Evocation (force/energy effects) |
| **HFO Level** | 6th (Signature — the defining P5 spell) |
| **Material Component** | SSOT database + contingency_state.json (the ivory statuette worth 1,500 gp) |
| **Casting Time** | 10 minutes (to register a new contingency trigger) |
| **Range** | Self (the P5 daemon) |
| **Duration** | Until triggered or 24 hours (daily recast in morning ritual) |

##### HFO Fit

| HFO Field | Value |
|-----------|-------|
| **Function** | Pre-programmed auto-remediation triggers. Each contingency is a (condition → response) pair registered in advance. When the condition fires, the response executes WITHOUT agent intervention. |
| **Code Artifact** | `hfo_p5_contingency.py` (EXISTS but needs CONTINGENCY trigger engine) |
| **Trigger System** | Event-driven: conditions evaluated on every T4 Anomaly Detection cycle (60s) |
| **Gate** | Each contingency has its own fail-closed gate — the trigger MUST match exactly, no fuzzy matching |

##### The CONTINGENCY Architecture

The D&D Contingency spell stores ONE spell that fires on ONE condition. The
HFO CONTINGENCY stores MULTIPLE triggers, each with its own response spell:

```
CONTINGENCY REGISTRY (contingency_state.json):
┌─────────────────────────────────────────────────────────────────────┐
│  Trigger Condition              │ Response Spell    │ Max Fires/hr │
├─────────────────────────────────┼───────────────────┼──────────────┤
│ event_storm > 50 events/min     │ DEATH_WARD        │ 1            │
│ orphan_sessions > 5             │ SANCTUARY (reap)  │ 3            │
│ disk_free_gb < 2.0              │ DISPEL_MAGIC(all) │ 1            │
│ pointer_drift > 3 keys          │ GUIDANCE (check)  │ 2            │
│ heartbeat_gap > 600s            │ GREATER_RESURRECT │ 1            │
│ ssot_size_mb > 500              │ ALERT (operator)  │ 1            │
│ model_unauthorized_loaded       │ SHIELD_OF_FAITH   │ 3            │
│ gate_blocked_storm > 30/hr      │ DEATH_WARD        │ 1            │
│ daemon_crash_loop (3× in 1hr)   │ DISPEL_MAGIC(one) │ 3            │
│ memory_loss_detected            │ ALERT + SANCTUARY │ 1            │
└─────────────────────────────────┴───────────────────┴──────────────┘
```

##### The 10 Default Contingencies

| # | Name | Condition | Response | Severity |
|---|------|-----------|----------|----------|
| **CT-01** | **EVENT_STORM** | >50 stigmergy events/min sustained 2 min | Cast DEATH_WARD: throttle writers, pause non-essential daemons | 🔴 CRITICAL |
| **CT-02** | **ORPHAN_FLOOD** | >5 orphaned sessions in last hour | Cast SANCTUARY: trigger immediate reaper sweep | 🟡 WARNING |
| **CT-03** | **DISK_CRITICAL** | Free disk <2 GB on SSOT drive | Cast DISPEL_MAGIC(all): kill all daemons, protect SSOT | 🔴 CRITICAL |
| **CT-04** | **POINTER_DRIFT** | >3 PAL pointer keys fail to resolve | Cast GUIDANCE: full pointer check + alert operator | 🟡 WARNING |
| **CT-05** | **HEARTBEAT_DEAD** | No heartbeat from any daemon for >600s | Cast GREATER_RESURRECTION: full Phoenix patrol | 🟠 HIGH |
| **CT-06** | **SSOT_BLOAT** | SSOT database >500 MB | Alert operator + write governance event | 🟡 WARNING |
| **CT-07** | **MODEL_INTRUSION** | Unauthorized Ollama model detected in VRAM | Cast SHIELD_OF_FAITH: unload unauthorized model | 🟠 HIGH |
| **CT-08** | **GATE_STORM** | >30 PREY8 gate_blocked events in 1 hour | Cast DEATH_WARD: something is hammering the gates | 🟠 HIGH |
| **CT-09** | **CRASH_LOOP** | Same daemon dies 3× within 1 hour | Cast DISPEL_MAGIC(that daemon): stop trying, alert | 🔴 CRITICAL |
| **CT-10** | **MEMORY_LOSS** | `prey8_detect_memory_loss` finds new orphans | Cast SANCTUARY + Alert: reap orphans, notify operator | 🟡 WARNING |

##### Why These 10 — Adversarial Justification

Each contingency maps to a **real failure mode observed in Gen88-89**:

| Contingency | Historical Evidence |
|-------------|-------------------|
| CT-01 EVENT_STORM | This session: Phoenix wrote SSOT event every 120s cycle = spam |
| CT-02 ORPHAN_FLOOD | SSOT shows 263 ghost sessions from Gen88→89 migration |
| CT-03 DISK_CRITICAL | Gen88 Epoch 5 death: hardware migration killed everything |
| CT-04 POINTER_DRIFT | Pointer check failures are a known PAL fragility |
| CT-05 HEARTBEAT_DEAD | Web rhythm graph showed 4/8 ports SILENT (P0-P3) |
| CT-06 SSOT_BLOAT | SSOT is 149 MB and growing — unchecked growth is debt |
| CT-07 MODEL_INTRUSION | Llama 3.2-vision 7.9GB loaded without authorization (this session) |
| CT-08 GATE_STORM | 166 gate_blocked events = 30% of traffic in latest analysis |
| CT-09 CRASH_LOOP | meadows daemon crashed immediately due to `--daemon` (wrong CLI arg) |
| CT-10 MEMORY_LOSS | PREY8 detect_memory_loss found multiple orphaned sessions |

##### Pseudocode

```python
class ContingencyEngine:
    """
    The CONTINGENCY spell engine. Evaluates registered triggers on every
    anomaly detection cycle and fires the stored response spell.
    
    Fail-closed: unknown conditions are NOT matched. Only exact triggers fire.
    Rate-limited: each contingency has a max_fires_per_hour.
    Logged: every firing writes a CloudEvent to SSOT.
    """
    
    def __init__(self, state_path: Path = CONTINGENCY_STATE):
        self.triggers: list[ContingencyTrigger] = self._load_defaults()
        self.fire_log: dict[str, list[datetime]] = {}
    
    def evaluate(self, anomaly_report: AnomalyReport) -> list[ContingencyFiring]:
        """Called by T4 AnomalyPatrolTask on every cycle."""
        firings = []
        
        for trigger in self.triggers:
            if not trigger.condition_met(anomaly_report):
                continue
            
            # Rate limit check
            fires_this_hour = len([
                t for t in self.fire_log.get(trigger.name, [])
                if t > now() - timedelta(hours=1)
            ])
            if fires_this_hour >= trigger.max_fires_per_hour:
                continue  # Already fired enough — don't spam
            
            # Fire the stored spell
            result = trigger.response_spell.cast()
            
            # Log the firing
            self.fire_log.setdefault(trigger.name, []).append(now())
            firings.append(ContingencyFiring(
                trigger=trigger.name,
                condition=trigger.condition_description,
                response=trigger.response_spell.name,
                result=result,
                severity=trigger.severity,
            ))
        
        # Write SSOT event if any fired
        if firings:
            write_p5_event("hfo.gen89.p5.contingency_fired", {
                "firings": [f.to_dict() for f in firings],
                "total_triggers_evaluated": len(self.triggers),
                "total_fired": len(firings),
            })
        
        return firings
    
    def arm(self, trigger: ContingencyTrigger):
        """Register a new contingency trigger. The 'arm' subcommand."""
        # Validate: condition must be machine-checkable
        if not trigger.is_deterministic():
            raise FailClosedError("Contingency conditions must be deterministic")
        self.triggers.append(trigger)
        self._save_state()
    
    def status(self) -> dict:
        """Show all armed contingencies and their recent fire history."""
        return {
            "armed": len(self.triggers),
            "triggers": [t.to_dict() for t in self.triggers],
            "fires_last_hour": sum(
                len([t for t in times if t > now() - timedelta(hours=1)])
                for times in self.fire_log.values()
            ),
        }

class ContingencyTrigger:
    name: str                    # CT-01, CT-02, etc.
    condition_type: str          # threshold, count, absence, pattern
    condition_params: dict       # The exact parameters to match
    response_spell: Spell        # The stored spell to cast
    max_fires_per_hour: int      # Rate limit
    severity: str                # CRITICAL, HIGH, WARNING
    
    def condition_met(self, report: AnomalyReport) -> bool:
        """Deterministic condition check. No fuzzy matching. No AI."""
        if self.condition_type == "threshold":
            return report.get_metric(self.condition_params["metric"]) \
                   > self.condition_params["threshold"]
        elif self.condition_type == "count":
            return report.count_in_window(
                self.condition_params["event_type"],
                self.condition_params["window_s"]
            ) > self.condition_params["max_count"]
        elif self.condition_type == "absence":
            return report.time_since_last(
                self.condition_params["event_type"]
            ) > self.condition_params["absence_threshold_s"]
        else:
            return False  # Unknown type = fail closed = don't fire
```

##### CLI Interface

```bash
# Show all armed contingencies
python hfo_p5_contingency.py status

# Audit all contingencies (dry-run evaluation)
python hfo_p5_contingency.py cast

# Arm a new custom contingency
python hfo_p5_contingency.py arm \
    --name "CT-11_CUSTOM" \
    --condition "threshold:events_per_min>100" \
    --response "DEATH_WARD" \
    --severity "CRITICAL" \
    --max-fires 1

# Show firing history
python hfo_p5_contingency.py history

# Disarm a contingency
python hfo_p5_contingency.py disarm CT-08
```

##### SBE Spec

```gherkin
Feature: CONTINGENCY — Auto-Remediation Triggers

  Scenario: Event storm triggers DEATH_WARD
    Given CT-01 EVENT_STORM is armed with threshold 50 events/min
    And the anomaly detector reports 75 events/min sustained 2 min
    When the ContingencyEngine evaluates the anomaly report
    Then CT-01 fires the DEATH_WARD response
    And 1 SSOT event "hfo.gen89.p5.contingency_fired" is written
    And the event contains trigger="CT-01_EVENT_STORM"

  Scenario: Rate limit prevents spam
    Given CT-01 has max_fires_per_hour=1
    And CT-01 already fired 23 minutes ago
    When another event storm is detected
    Then CT-01 does NOT fire again
    And no SSOT event is written

  Scenario: Unknown condition type fails closed
    Given a trigger has condition_type="fuzzy_match"
    When the ContingencyEngine evaluates
    Then the trigger does NOT fire (fail-closed on unknown type)

  Scenario: Multiple contingencies can fire simultaneously
    Given CT-03 DISK_CRITICAL and CT-09 CRASH_LOOP are both triggered
    When the ContingencyEngine evaluates
    Then both response spells fire
    And 1 SSOT event contains 2 firings
```

---

### Focus Spell 3 — 7th Level: PRISMATIC WALL ⭐⭐⭐ (LEGENDARY ABILITY)

*The crown jewel. 8 layers of defense. Each a different death. No shortcut.*

---

#### 📜 PRISMATIC WALL — Full Spell Card

| Field | Value |
|-------|-------|
| **D&D Spell** | Prismatic Wall (Abjuration 9th in D&D, 7th here for P5 tier structure) |
| **D&D Effect** | *"7 layers of light. Each a different damage type. Each with a different counter. You must defeat ALL layers to get through. There is no shortcut."* |
| **D&D School** | Abjuration (warding, protection) + Evocation (force effects) |
| **HFO Level** | 7th (Legendary — the most powerful recurring P5 ability) |
| **Material Component** | The entire octree (all 8 ports) |
| **Casting Time** | 1 daily ritual (~30s for full 8-layer audit) |
| **Range** | System-wide (all 8 ports) |
| **Duration** | Until next daily cast |

##### HFO Fit

| HFO Field | Value |
|-----------|-------|
| **Function** | 8-layer defense-in-depth health audit (one layer per port). Each layer blocks a different class of failure. All 8 must pass for PRISMATIC status. |
| **Code Artifact** | `hfo_p5_pyre_praetorian.py` → planned `PrismaticWall` class |
| **Reference** | SSOT #411: REFERENCE_P5_PRISMATIC_WALL_DEFENSE_IN_DEPTH_V1 |
| **Formula** | $\text{HFO\_PRISMATIC\_WALL} = \bigcap_{i=0}^{7} \text{Gate}_i$ (fail-closed at every layer) |

##### The 8 Layers

| Layer | Color | Port | Gate Type | What It Blocks | Check Implementation | Tier |
|-------|-------|------|-----------|---------------|---------------------|------|
| **L0** | 🔴 Red | P0 OBSERVE | Perception Gate | Hallucinated state | Date check, SSOT count, health pulse, daemon status | T4 |
| **L1** | 🟠 Orange | P1 BRIDGE | Contract Gate | Schema violations | PAL pointer resolution, .env validation, SSOT schema check | T4 |
| **L2** | 🟡 Yellow | P2 SHAPE | Creation Gate | Unmedallioned artifacts | Medallion column check, header validation, content_hash uniqueness | T6 |
| **L3** | 🟢 Green | P3 INJECT | Delivery Gate | Payload corruption | Stigmergy event schema validation, CloudEvent structure check | T6 |
| **L4** | 🔵 Blue | P4 DISRUPT | Adversarial Gate | AI Theater | Mutation score >0 check, PREY8 gate_blocked count, Book of Blood | T6 |
| **L5** | 🟣 Indigo | P5 IMMUNIZE | Immunity Gate | Governance bypass | This spell's own health, contingency status, reaper health | T4 |
| **L6** | 🟤 Violet | P6 ASSIMILATE | Memory Gate | Amnesia / corruption | SSOT write verification, orphan ratio, yield ratio | T4 |
| **L7** | ⚪ White | P7 NAVIGATE | Coherence Gate | Drift / desync | Spell gate state, braided thread, daemon fleet census | T4 |

##### Health States

$$\text{Wall Health} = \frac{\sum_{i=0}^{7} \text{LayerScore}_i}{8}$$

Where LayerScore: PASS=1.0, DEGRADED=0.5, FAIL=0.0

| State | Score Range | Visual | Meaning |
|-------|------------|--------|---------|
| **PRISMATIC** | 1.0 (8/8 pass) | 🌈 | All layers holding. Full defense. |
| **FRACTURED** | 0.75–0.99 (6-7 pass) | 🔶 | Minor gaps. Schedule remediation. |
| **BREACHED** | 0.50–0.74 (4-5 pass) | 🔴 | Major gaps. Immediate attention. |
| **DARK** | <0.50 (<4 pass) | ⚫ | Defense collapsed. Emergency. |

##### Tier Classification (from doc 85)

| Tier | Meaning | Layer Count (expected Gen89) |
|------|---------|-----|
| **T2** | Structurally enforced (machine-gated, no human needed) | 0 (aspirational) |
| **T4** | Partially enforced (automated check, human review) | 5 (L0, L1, L5, L6, L7) |
| **T6** | Cooperative (human-only, agent recommends) | 3 (L2, L3, L4) |

##### Pseudocode

```python
class PrismaticWall:
    """
    PRISMATIC_WALL: 8-layer defense-in-depth health audit.
    Daily cast. Each layer is an independent gate.
    Health score = mean of all layer scores.
    """
    
    LAYERS = [
        Layer(0, "Red",    "P0 OBSERVE",    "Perception Gate",  check_perception),
        Layer(1, "Orange", "P1 BRIDGE",     "Contract Gate",    check_contracts),
        Layer(2, "Yellow", "P2 SHAPE",      "Creation Gate",    check_creation),
        Layer(3, "Green",  "P3 INJECT",     "Delivery Gate",    check_delivery),
        Layer(4, "Blue",   "P4 DISRUPT",    "Adversarial Gate", check_adversarial),
        Layer(5, "Indigo", "P5 IMMUNIZE",   "Immunity Gate",    check_immunity),
        Layer(6, "Violet", "P6 ASSIMILATE", "Memory Gate",      check_memory),
        Layer(7, "White",  "P7 NAVIGATE",   "Coherence Gate",   check_coherence),
    ]
    
    def cast(self) -> PrismaticReport:
        """Daily cast — check all 8 layers."""
        results = []
        for layer in self.LAYERS:
            try:
                result = layer.check_fn()
                results.append(LayerResult(
                    layer=layer,
                    status=result.status,  # PASS, DEGRADED, FAIL
                    details=result.details,
                    tier=result.tier,       # T2, T4, T6
                ))
            except Exception as e:
                # Any exception = FAIL (fail-closed)
                results.append(LayerResult(
                    layer=layer,
                    status="FAIL",
                    details=f"Exception: {e}",
                    tier="T6",
                ))
        
        score = sum(r.score for r in results) / 8
        state = (
            "PRISMATIC" if score == 1.0 else
            "FRACTURED" if score >= 0.75 else
            "BREACHED"  if score >= 0.50 else
            "DARK"
        )
        
        report = PrismaticReport(
            state=state,
            score=score,
            layers=results,
            timestamp=now(),
        )
        
        # Write SSOT event
        write_p5_event("hfo.gen89.p5.prismatic_wall.cast", {
            "state": state,
            "score": score,
            "layers": {r.layer.name: r.status for r in results},
            "pass_count": sum(1 for r in results if r.status == "PASS"),
            "fail_count": sum(1 for r in results if r.status == "FAIL"),
        })
        
        return report

    def status(self) -> dict:
        """Show last cast results."""
        return self._load_last_cast()
    
    def improve(self) -> dict:
        """Show roadmap: which layers to promote from T6→T4→T2."""
        last = self._load_last_cast()
        roadmap = []
        for layer_result in last.layers:
            if layer_result.tier == "T6":
                roadmap.append({
                    "layer": layer_result.layer.name,
                    "current_tier": "T6",
                    "next_step": "Write automated check function",
                    "target_tier": "T4",
                })
            elif layer_result.tier == "T4":
                roadmap.append({
                    "layer": layer_result.layer.name,
                    "current_tier": "T4",
                    "next_step": "Add to pre-commit hook or CI gate",
                    "target_tier": "T2",
                })
        return {"roadmap": roadmap, "t2_count": ..., "t4_count": ..., "t6_count": ...}
```

##### Layer Check Implementations (What Each Layer Audits)

```python
def check_perception() -> LayerCheck:
    """L0 Red — Perception Gate: Is the system perceiving reality correctly?"""
    checks = [
        ("date_sanity", abs((now() - last_ssot_write()).days) < 7),
        ("ssot_accessible", Path(SSOT_DB).exists()),
        ("ssot_readable", can_query_ssot()),
        ("doc_count_sane", 9000 < get_doc_count() < 20000),
        ("event_count_growing", get_event_count() > 9000),
    ]
    return score_checks(checks)

def check_contracts() -> LayerCheck:
    """L1 Orange — Contract Gate: Do schemas and contracts hold?"""
    checks = [
        ("pal_resolves", all_pointers_resolve()),
        ("env_valid", env_file_valid()),
        ("ssot_schema_intact", ssot_schema_matches_expected()),
        ("fts_index_alive", fts_search_works("test")),
    ]
    return score_checks(checks)

def check_creation() -> LayerCheck:
    """L2 Yellow — Creation Gate: Are artifacts properly medallioned?"""
    checks = [
        ("all_docs_have_medallion", no_null_medallion_docs()),
        ("content_hash_unique", no_duplicate_hashes()),
        ("headers_valid", sample_header_validation()),
    ]
    return score_checks(checks)

def check_delivery() -> LayerCheck:
    """L3 Green — Delivery Gate: Are payloads delivered intact?"""
    checks = [
        ("stigmergy_schema_valid", validate_recent_events_schema()),
        ("no_corrupt_json", no_corrupt_json_in_recent_events()),
        ("cloudevent_specversion", all_recent_events_have_specversion()),
    ]
    return score_checks(checks)

def check_adversarial() -> LayerCheck:
    """L4 Blue — Adversarial Gate: Has work been adversarially tested?"""
    checks = [
        ("prey8_yield_ratio", get_yield_ratio() > 0.3),
        ("gate_blocked_reasonable", gate_blocked_per_hour() < 50),
        ("no_stale_react_tokens", no_react_tokens_older_than_24h()),
    ]
    return score_checks(checks)

def check_immunity() -> LayerCheck:
    """L5 Indigo — Immunity Gate: Is P5 itself healthy?"""
    checks = [
        ("p5_daemon_registered", "pyre" in spell_gate_state()),
        ("contingencies_armed", contingency_count() >= 5),
        ("reaper_healthy", last_reaper_run() < timedelta(hours=1)),
        ("no_exception_creep", no_disabled_contingencies()),
    ]
    return score_checks(checks)

def check_memory() -> LayerCheck:
    """L6 Violet — Memory Gate: Is memory intact?"""
    checks = [
        ("ssot_write_recent", last_ssot_write() < timedelta(hours=6)),
        ("orphan_ratio_low", orphan_ratio() < 0.5),
        ("no_memory_loss_events", recent_memory_loss_count() == 0),
        ("yield_ratio_healthy", get_yield_ratio() > 0.3),
    ]
    return score_checks(checks)

def check_coherence() -> LayerCheck:
    """L7 White — Coherence Gate: Is the web holding?"""
    checks = [
        ("spell_gate_state_valid", spell_gate_state_parseable()),
        ("pal_pointers_all_resolve", all_pointers_resolve()),
        ("daemon_fleet_census", at_least_n_daemons_registered(3)),
        ("braided_thread_exists", braided_thread_accessible()),
    ]
    return score_checks(checks)
```

##### CLI Interface

```bash
# Daily cast — check all 8 layers
python hfo_p5_prismatic_wall.py cast

# Show last cast results
python hfo_p5_prismatic_wall.py status

# Show improvement roadmap (T6→T4→T2)
python hfo_p5_prismatic_wall.py improve

# Check a single layer
python hfo_p5_prismatic_wall.py layer 0    # Red / Perception
python hfo_p5_prismatic_wall.py layer 4    # Blue / Adversarial

# JSON output for machine consumption
python hfo_p5_prismatic_wall.py cast --json
```

##### SBE Spec

```gherkin
Feature: PRISMATIC_WALL — 8-Layer Defense-in-Depth

  Scenario: All layers pass = PRISMATIC
    Given all 8 layer checks return PASS
    When PRISMATIC_WALL is cast
    Then the state is "PRISMATIC" with score 1.0
    And the SSOT event shows pass_count=8, fail_count=0

  Scenario: One layer fails = FRACTURED
    Given 7 layers pass and L4 Adversarial returns FAIL
    When PRISMATIC_WALL is cast
    Then the state is "FRACTURED"
    And the report identifies L4 as the gap

  Scenario: Four layers fail = DARK
    Given only 4 layers pass
    When PRISMATIC_WALL is cast
    Then the state is "DARK" with score 0.5
    And an emergency alert is generated

  Scenario: Layer check throws exception = FAIL (fail-closed)
    Given L3 Delivery check raises ConnectionError
    When PRISMATIC_WALL is cast
    Then L3 is scored as FAIL (not UNKNOWN, not skipped)
    And the details contain the exception message
```

---

### 8th Level — High Magic (Emergency / Rare)

| # | Spell | D&D Analog | HFO Function | Code | Status |
|---|-------|-----------|--------------|------|--------|
| 9 | **ANTIMAGIC FIELD** | Antimagic Field (Abjuration 6th, treated as 8th for HFO power) | Full quarantine mode — isolate untrusted code/agents in sandbox. Nothing gets in, nothing gets out. Zero blast radius. | Planned: `hfo_p5_antimagic_field.py` | ❌ TODO |
| 10 | **HOLY AURA** | Holy Aura (Abjuration 8th) | Complete governance spine validation — validate ALL Silk Web protocols (SW-1 through SW-5), ALL medallion boundaries, ALL pre-commit hooks. The full P5 audit. | Planned: comprehensive `cast --full` mode | ❌ TODO |

---

### 9th Level — Divine Magic (Catastrophe / Epoch Events)

| # | Spell | D&D Analog | HFO Function | Code | Status |
|---|-------|-----------|--------------|------|--------|
| 11 | **TRUE RESURRECTION** | True Resurrection (Cleric 9th) | Full system rebuild from SSOT phylactery — Gen(N-1) → Gen(N). The Phoenix Protocol phases 10-12. Everything dies; only the database survives; everything is rebuilt. | `gen89_ssot_packer.py` + manual operator work | ⚠️ EXISTS (manual, operator-only) |
| 12 | **MIRACLE** | Miracle (Cleric 9th) | NATARAJA dance invocation — full P4+P5 cycle. P4 WAIL_OF_THE_BANSHEE kills everything; P5 TRUE_RESURRECTION rebuilds. The cosmic dance. Only the operator can invoke. | Manual: NATARAJA_Score = P4_kill_rate × P5_rebirth_rate | ❌ CONCEPTUAL |

---

### Epic Level — Cross-Generational (Architecture-Level)

| # | Spell | D&D Analog | HFO Function | Code | Status |
|---|-------|-----------|--------------|------|--------|
| 13 | **GREATER CONTINGENCY** | Greater Contingency (Epic) | Contingency triggers that persist across generation deaths. Stored in SSOT, survive Gen N → Gen N+1. The Phoenix Overlay — defense patterns that evolve through death. | Planned: SSOT-backed contingency registry | ❌ TODO |
| 14 | **PRISMATIC SPHERE** | Prismatic Sphere (Epic enhanced Prismatic Wall) | Self-enclosing defense — the wall wraps around the system into a sphere. 360° coverage, no gaps, no blind spots. P5 defending P5 defending P5... a strange loop. | Aspirational: fully automated T2 on all 8 layers | ❌ ASPIRATIONAL |

---

## 3. Code-to-Spell Mapping

*What already exists and what spell it corresponds to.*

| Code Artifact | Spell(s) | Status |
|--------------|----------|--------|
| `hfo_p5_pyre_praetorian.py` → `check_ollama_online()` | C1 STABILIZE | ✅ |
| `hfo_p5_pyre_praetorian.py` → `check_disk_free_gb()` | C1 STABILIZE | ✅ |
| `hfo_p5_pyre_praetorian.py` → `check_ssot_size_mb()` | C1 STABILIZE | ✅ |
| `hfo_p5_pyre_praetorian.py` → `count_stigmergy_events()` | C1 STABILIZE | ✅ |
| `hfo_p5_pyre_praetorian.py` → `check_orphaned_nonces()` | C2 DETECT MAGIC | ✅ |
| `hfo_p5_pyre_praetorian.py` → `CEILINGS{}` | C3 RESISTANCE | ✅ |
| `hfo_p5_pyre_praetorian.py` → `resource_governance_preflight()` | C3 RESISTANCE | ✅ |
| `hfo_pointers.py check` | C4 GUIDANCE | ✅ |
| `hfo_p5_daemon.py` → `IntegrityPatrolTask` (T1) | Spell 1 PURIFICATION RITUAL | ✅ |
| `hfo_p5_daemon.py` → `SessionOrphanReaper` (T2) | Spell 2 SANCTUARY | ✅ |
| `hfo_p5_daemon.py` → `OllamaModelGovernanceTask` (T3) | Spell 3 SHIELD OF FAITH | ✅ |
| `hfo_p5_daemon.py` → `AnomalyPatrolTask` (T4) | Spell 4 ZONE OF TRUTH | ✅ |
| `hfo_p5_daemon.py` → `LLMPolicyAnalystTask` (T5) | Spell 5 AUGURY | ✅ |
| `hfo_p5_daemon.py` → event throttle + quiet mode | Spell 6 DEATH WARD | ⚠️ PARTIAL |
| `hfo_p7_spell_gate.py` → `spell_banish(quiet=True)` | Spell 7 DISPEL MAGIC | ✅ |
| `.p7_spell_gate_state.json` reset | Spell 8 REMOVE CURSE | ⚠️ PARTIAL |
| `hfo_p5_daemon.py` → `SpellGatePhoenixTask` (T6) | **Spell 9 GREATER RESURRECTION** | ✅ (upgraded this session) |
| `hfo_p5_contingency.py` (planned) | **Spell 10 CONTINGENCY** | ❌ NEEDS BUILD |
| Planned: `hfo_p5_prismatic_wall.py` | **Spell 11 PRISMATIC WALL** | ❌ NEEDS BUILD |

---

## 4. Implementation Priority (The Build Roadmap)

| Priority | Spell | Why Now | LOC Estimate | Dependencies |
|----------|-------|---------|-------------|-------------|
| **P0** | CONTINGENCY | The #1 gap identified by SSOT #9860. Without auto-remediation triggers, TTAO is manual P5. This is the spell that prevents the next spam incident BEFORE it happens. | ~300 lines | T4 AnomalyPatrolTask (exists), ContingencyTrigger class (new) |
| **P1** | PRISMATIC_WALL | The daily health audit. Without this, there's no system-wide defense visibility. The Dancer is blind. | ~400 lines | All Ring 0 cantrips (exist), 8 layer check functions (5 exist, 3 new) |
| **P2** | DEATH_WARD (unified) | Rate limiters exist in pieces but aren't unified as a spell. One clean circuit breaker API. | ~150 lines | Event throttle (exists), quiet mode (exists) |
| **P3** | ANTIMAGIC_FIELD | Quarantine/sandbox. Critical for testing agent modes safely. | ~200 lines | Need sandbox directory management |
| **P4** | GREATER CONTINGENCY (Epic) | Persist contingencies across generations in SSOT. | ~100 lines (on top of CONTINGENCY) | CONTINGENCY spell + SSOT table |

---

## 5. The Strange Loop — P4↔P5 Nataraja Dance

```
    P4 Red Regnant                    P5 Pyre Praetorian
    DISRUPT                           IMMUNIZE
    ☳ Thunder                         ☲ Fire
    Singer of Strife                  Dancer of Death and Dawn
    
    FESTERING_ANGER finds weakness    CONTINGENCY has pre-armed trigger
              │                                   │
              ▼                                   ▼
    Grudge added to Book of Blood     Trigger fires, response spell cast
              │                                   │
              ▼                                   ▼
    Attack sent: "here's how I        Immunity proven: "here's why that
     broke your wall"                  attack now fails"
              │                                   │
              ▼                                   ▼
    EVOLVE: P4 invents new attack     TEACH: P5 feeds new constraint
     targeting the hardened wall        back to P2 SHAPE + P4 DISRUPT
              │                                   │
              └──────────►NATARAJA◄───────────────┘
                     The Cosmic Dance
                 Creation × Destruction
              NATARAJA_Score = P4_kill × P5_rebirth
```

$$\boxed{\text{NATARAJA\_Score} = \text{P4\_kill\_rate} \times \text{P5\_rebirth\_rate}}$$

**Current Score (Gen89):**
- P4_kill_rate ≈ 1.0 (everything died in Gen88→89 migration)
- P5_rebirth_rate ≈ 0.1 (manual only — TTAO as manual P5)
- **NATARAJA_Score ≈ 0.1** (Singer at full power, Dancer barely operational)

**Target Score:**
- P4_kill_rate ≈ 0.8 (continuous adversarial testing, not catastrophic)
- P5_rebirth_rate ≈ 0.9 (automated: CONTINGENCY + GREATER_RESURRECTION + PRISMATIC_WALL)
- **NATARAJA_Score ≈ 0.72** (healthy dance = strong defense)

---

## 6. The Pyre's Three Vows

### Vow 1: Fail Closed, Always
> Every spell defaults to DENY. If a check fails, the gate closes. If a
> condition is unknown, it is treated as FAIL. There are no exceptions.
> Exception creep is the Dancer's mortal enemy.

### Vow 2: Silent When Healthy, Loud When Sick
> A healthy system is a quiet system. SSOT events are written ONLY when
> anomalies are found, contingencies fire, or resurrections occur. Normal
> patrol cycles produce ZERO output. The silence IS the signal of health.

### Vow 3: Every Gate Teaches
> A blocked gate is not a dead end — it is a lesson. Every CONTINGENCY
> firing, every PRISMATIC_WALL failure, every GREATER_RESURRECTION is
> recorded in the stigmergy trail. Future agents inherit the Dancer's
> memory. The pyre burns; the ashes teach.

---

*P5 Grimoire v1 — designed by P4 Red Regnant, 2026-02-20.*
*PREY8 session 6b1e6bafdaba7ce9, execute token 56B1CB.*
*"That which does not kill us makes us stronger."*
