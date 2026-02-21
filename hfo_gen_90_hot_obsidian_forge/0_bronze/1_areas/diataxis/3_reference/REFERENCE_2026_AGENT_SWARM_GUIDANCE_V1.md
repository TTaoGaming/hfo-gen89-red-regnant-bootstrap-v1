---
medallion_layer: bronze
mutation_score: 0
hive: V
hfo_header_v3: compact
schema_id: hfo.mosaic_microkernel_header.v3
mnemonic: "O·B·S·I·D·I·A·N = 8 ports = 1 octree"
bluf: "2026 AI agent swarm landscape: patterns that work, anti-patterns that destroy repos, tool triage, and why HFO already has the core primitives."
primary_port: P0
role: "P0 OBSERVE — landscape reconnaissance"
tags: [bronze, forge:hot, para:resources, diataxis:reference, p0, agent-swarm, 2026, patterns, anti-patterns, openclaw, mcp, containment]
generated: "2026-07-15T15:00:00Z"
sources:
  - "github.com/e2b-dev/awesome-ai-agents — landscape catalog (25.7k stars)"
  - "github.com/topics/ai-agent-framework — 68 repos (Jul 2026)"
  - "github.com/openclaw/openclaw — 186k stars, personal AI assistant"
  - "github.com/inngest/agent-kit — deterministic multi-agent routing + MCP"
  - "github.com/triggerdotdev/trigger.dev — managed AI agents + MCP"
  - "github.com/MervinPraison/PraisonAI — production multi-agent"
  - "E41 — EXPLANATION_PARETO_OPTIMAL_AGENT_ENFORCEMENT_ANTI_GOODHART_V1.md"
  - "EXPLANATION_SBE_SWARM_CI_PRACTICES_V1.md"
---

# R42 — 2026 AI Agent Swarm Guidance: Patterns, Anti-Patterns, and Tool Triage

> **Port 0 · Lidless Legion · OBSERVE · ☷ 000**
>
> A reference document for an operator overwhelmed by the pace of new AI tools.
> What to use, what to skip, and why you already have the core primitives.

---

## BLUF (Bottom Line Up Front)

**You don't need to chase every new framework.** The 2026 landscape has 200+ agent frameworks. Most will be dead in 6 months. The patterns that matter are stable and you already have them:

1. **MCP** (Model Context Protocol) — universal tool integration. You have it.
2. **Stigmergy/blackboard** — swarm coordination without direct messaging. You have it.
3. **Fail-closed gate chains** — SWE-bench invariants + binary checks. You're building it.
4. **SBE/ATDD** — behavioral specs as ground truth. You have the doctrine.
5. **Sandbox containment** — bronze layer + path checks. You have it.

**What you're missing:** Gate 4 (test gating) and Gate 5 (mutation gating) from E41. That's a ~50-line bash/Python addition, not a new framework.

---

## The 2026 Agent Tool Landscape (Triage)

### Tier A: You Already Have This (don't adopt, you'll duplicate)

| Tool / Pattern | What It Does | HFO Equivalent | Status |
|---|---|---|---|
| **MCP** (Anthropic) | Universal tool integration protocol | `hfo_mcp_gateway_hub.py` | Active |
| **Blackboard / stigmergy** | Indirect swarm coordination | `stigmergy_events` + `hfo_blackboard_events.py` | Active |
| **AGENTS.md / CLAUDE.md** | Agent context files | `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md` | Active |
| **Context engineering** | Structured context > bigger context window | Braided mission thread + blessed pointers + PAL | Active |
| **4-beat workflows** | Preflight → Payload → Postflight → Payoff | P4 Toolbox v10/v11 wrappers | Active |
| **Ralph Wiggum loops** | Brute-force iterate until tests pass | P4 4-beat in sequence = Ralph loop | Active |
| **Eval-driven development** | Write the eval before the feature | SBE/ATDD + eval harness template (just built) | New |

### Tier B: Interesting But Low Priority (watch, don't adopt yet)

| Tool | What It Does | Why Wait |
|---|---|---|
| **OpenClaw** (186k stars) | Personal AI assistant with skills + clawhub | It's an assistant platform, not a coding agent. Skills are useful but you'd need to build HFO-specific ones. Watch until skill quality matures. |
| **trigger.dev** | Managed AI agents + MCP + serverless | Cloud-hosted, costs money. Your local-first approach works fine for a solo dev on Chromebook. |
| **inngest/agent-kit** | Deterministic multi-agent routing in TypeScript | Good architecture ideas but HFO's bash wrappers already do deterministic routing via the 4-beat. |
| **PraisonAI** | Production multi-agent with low-code | Python-based but adds a framework layer you don't need. Your agents are already structured. |
| **Stryker.js** | Mutation testing | **Worth integrating** for Gate 5, but it's a tool not a framework. Add it to postflight. |

### Tier C: Skip (tool fatigue traps)

| Tool | Why Skip |
|---|---|
| **AutoGPT / BabyAGI variants** | 2023-era. No structured evaluation. Unbounded loops = context rot. |
| **n8n / Zapier Central** | Workflow automation, not code quality. Wrong abstraction for HFO's problem. |
| **CrewAI / MetaGPT / ChatDev** | Multi-agent frameworks that add a framework layer between you and the LLM. You already orchestrate via blackboard — adding another layer adds complexity without adding enforcement. |
| **SwarmZero** | Decentralized swarms — interesting research, premature for production. |
| **Most "AI coding agent" startups** | 6-month half-life. If they're still alive in Jan 2027, then look. |

---

## 6 Patterns That Work in 2026

### Pattern 1: Context Engineering > Prompt Engineering

**The shift:** 2024-2025 was "prompt engineering" (write the perfect instruction). 2026 is "context engineering" (give the model the right information at the right time).

**You're already doing this:**
- Blessed pointers (PAL) = structured context resolution
- Braided mission thread = canonical state in one file
- Pheromone context reads = relevance-weighted recent context
- Preflight forms = task-specific context gathering

**Anti-pattern:** Writing longer and longer system prompts. The model doesn't need more instructions — it needs better-structured inputs.

### Pattern 2: Fail-Closed Gate Chains (Not LLM-as-Judge)

**The principle:** Every gate in the chain is a binary code check (`exit 0` or `exit 1`). No LLM evaluates anything. (E41 Option 1)

**Why this wins:** ICRH (Pan et al. 2024) proves that LLM-evaluating-LLM is structurally gameable. The only defense is decoupled evaluation — the evaluation mechanism is code that the agent cannot modify.

**You're building this:** v10 wrapper already has 7 hard gates. Adding Gate 4 (test invariants) and Gate 5 (mutation score) completes the lattice.

### Pattern 3: SBE/ATDD as Ground Truth

**The principle:** Human writes the behavioral spec BEFORE the agent runs. Agent's job is to make the spec pass, not to look impressive.

**Why this wins:** Behavioral specs define outcomes, not proxy metrics. You can't Goodhart on "Given insufficient balance, When transfer attempted, Then error 402."

**You have the doctrine.** The gap is enforcement: make the wrapper REJECT turns without `Given/When/Then` in the query field.

### Pattern 4: Bronze Sandbox Containment

**The principle:** Experimental work happens in a containment zone where failure is expected and acceptable. Agents build freely but CANNOT write to production paths.

**Implementation:**
```
Bronze (sandbox)  ──promotion gates──►  Silver (verified)  ──promotion gates──►  Gold (blessed)
```

**This is the answer to "I need a VM":** For 95% of work, a path-based containment check is sufficient. Docker is for external tool experiments. VMs are for untrusted third-party frameworks.

### Pattern 5: Stigmergy for Swarm Coordination

**The principle:** Agents don't message each other directly. They read/write shared state (blackboard, pheromone trails). The environment IS the communication channel.

**Why this wins over direct agent-to-agent messaging:**
- No single point of failure (no coordinator node)
- Naturally handles asynchronous, rate-limited agents
- Temporal decoupling — agent A's output is available to agent B hours later
- Merge-safe — pheromone reinforcement is monotonic (add-only)

**You have this:** `stigmergy_events` + ACO pheromone VIEW + dual-write.

### Pattern 6: Eval-Driven Development

**The principle (from Anthropic, Jan 2026):** Write the eval before the feature. If you can't define what success looks like in machine-verifiable terms, you're not ready to build.

**The eval harness template** (just built) operationalizes this: fill in the Gherkin specs and verification commands BEFORE the agent runs
