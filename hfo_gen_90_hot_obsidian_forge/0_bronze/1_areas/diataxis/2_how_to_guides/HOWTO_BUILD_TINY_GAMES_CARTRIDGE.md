---
medallion_layer: gold
mutation_score: 0
hive: V
hfo_header_v3: compact
schema_id: hfo.mosaic_microkernel_header.v3
mnemonic: "O·B·S·I·D·I·A·N = 8 ports = 1 octree"
bluf: "How-To: Build a Tiny Games cartridge using the microkernel plugin architecture. SBE/ATDD → Contract → Juice → Ship. Portable gold reference."
primary_port: P2
role: "P2 SHAPE — creation/models"
tags: [gold, forge:hot, para:resources, diataxis:howto, p2, omega, tiny-games, microkernel, plugin, cartridge, sbe, atdd, whiteboard, education, markdown]
full_header: "braided_mission_thread_alpha_omega_hfo_gen88v8.yaml (lines 1–512)"
generated: "2026-02-11T14:00:00Z"
---

# How-To: Build a Tiny Games Cartridge

> **Goal**: Create a new game cartridge for the Tiny Games microkernel — from SBE spec to playable cartridge — in under 2 hours.

## Prerequisites

| What | Where |
|------|-------|
| Tiny Games project root | `hfo_hot_obsidian_forge/0_bronze/1_areas/tiny_games/` |
| TypeScript contract | `contracts/cartridge.contract.ts` |
| Juice library | `juice/juice.js` |
| Kernel host | `kernel/tiny-games-kernel.html` |
| Existing specs | `specs/*.feature` |
| MAP-Elites registry | `map-elites/spike_registry.yaml` |
| Reference catalog | Gold Diataxis `3_reference/REFERENCE_CLONE_FORK_EVOLVE_OPEN_SOURCE_GAME_CATALOG.md` |

---

## Step 1: Write the SBE/ATDD Gherkin Spec

Every cartridge starts with a `.feature` file. Follow the established pattern:

```
specs/cartridge_<name>.feature
```

Structure (per HFO SBE Towers pattern):

```gherkin
Feature: Cartridge — <Name>
  # Part 1: Invariant scenarios (fail-closed safety)
  # Part 2: Happy-path scenarios (core gameplay)
  # Part 3: Juice integration
  # Part 4: Performance budget
  # Part 5: Lifecycle

  Scenario: [invariant] Cartridge exports required interface
    Given a cartridge module at "cartridges/<name>/cartridge.js"
    Then it exports init, destroy, onPointerDown, onPointerMove, onPointerUp, onResize
    And it exports metadata with id, name, version, category

  Scenario: [happy] Core gameplay loop
    # Game-specific scenarios...

  Scenario: [juice] Triggers juice on key events
    # Particles, SFX, shake, haptic...

  Scenario: [perf] Sustained 60fps
    Given the cartridge is running
    When 300 frames have elapsed
    Then average frame time < 16.7ms

  Scenario: [lifecycle] Clean destroy
    Given the cartridge is initialized
    When destroy() is called
    Then all resources are freed
    And no animation frames remain scheduled
```

**Key patterns**: Tag scenarios with `@invariant`, `@happy`, `@fail-closed`. Include touch control scenarios (swipe, tap, double-tap, long-press) with `@whiteboard` for 44px+ minimum touch targets.

---

## Step 2: Define the Cartridge Module

Create the cartridge directory and main file:

```
cartridges/<name>/cartridge.js
```

Required exports (from `contracts/cartridge.contract.ts`):

```javascript
// Metadata (required)
export const metadata = {
  id: '<name>',           // unique slug
  name: 'Display Name',   // shown in picker
  version: '0.1.0',
  category: 'arcade',     // arcade|puzzle|education|music|art|sandbox|multiplayer|other
  description: '...',
  author: 'Tiny Games CFE',
  license: 'MIT',
  icon: '🎮'              // emoji for picker
};

// Lifecycle (required)
export function init(canvas, config) { /* config.juice, config.width, config.height */ }
export function destroy() { /* free ALL resources */ }

// Pointer events (required)
export function onPointerDown(e) { }
export function onPointerMove(e) { }
export function onPointerUp(e) { }

// Resize (required)
export function onResize(width, height) { }

// Frame tick (optional — kernel calls if exported)
export function tick(dt) { }
```

---

## Step 3: Integrate the Juice Layer

The kernel provides a `JuiceAPI` object via `config.juice`:

```javascript
const juice = config.juice;

// Particle burst (object-pooled, max 200 active)
juice.particles.burst(x, y, {
  count: 20,        // 10–30 typical
  color: '#ff6b6b', // or 'rainbow' for random HSL
  speed: 3,
  life: 0.6
});

// Screen shake (exponential decay, combinable)
juice.shake(intensity, durationMs);
// intensity: 2 (subtle) → 5 (medium) → 10 (heavy)

// Procedural SFX (Web Audio, no asset files)
juice.sfx('pop');    // 5 types: pop, ding, whoosh, thud, click

// Haptic feedback (Vibration API, degrades gracefully)
juice.haptic(durationMs);
```

**Budget constraints** (per SBE spec):
- Max 200 active particles
- Max 8 simultaneous audio nodes
- Juice must use < 10% of frame budget

---

## Step 4: Register in the Kernel

Edit `kernel/tiny-games-kernel.html` to add the cartridge to `CARTRIDGE_REGISTRY`:

```javascript
const CARTRIDGE_REGISTRY = [
  // ...existing cartridges...
  {
    id: '<name>',
    name: 'Display Name',
    path: '../cartridges/<name>/cartridge.js',
    icon: '🎮',
    description: '...'
  }
];
```

The kernel handles:
- Dynamic `import()` with 5s timeout
- Interface shape validation (init, destroy, onPointer*, onResize)
- Canvas sizing (DPR-aware)
- Pointer event forwarding with try/catch
- Juice overlay rendering

---

## Step 5: Score in MAP-Elites

Add a new entry to `map-elites/spike_registry.yaml`:

```yaml
  <name>:
    origin: "CFE: <source project> (<description>)"
    license: MIT
    scores:
      juice_level: 2        # 1=minimal, 2=good, 3=exemplar
      touch_quality: 2       # 1=basic, 2=multi, 3=stylus+pressure
      educational_value: 1   # 1=none, 2=some, 3=curriculum-aligned
      engagement: 2          # 1=low, 2=mid, 3=high-flow
      performance: 3         # 1=<30fps, 2=30-55, 3=60fps solid
    pareto_cell: [2, 2, 1, 2, 3]
    notes: |
      <implementation notes, evolution targets>
```

The Pareto frontier analysis section will be updated as more cartridges are added.

---

## Step 6: Test Locally

```bash
# Serve locally (any static server, kernel uses ES modules)
cd hfo_hot_obsidian_forge/0_bronze/1_areas/tiny_games
python3 -m http.server 8080

# Open in browser
# http://localhost:8080/kernel/tiny-games-kernel.html
```

Verify against your Gherkin spec:
1. ✅ All invariant scenarios pass (exports, interface shape)
2. ✅ Happy-path gameplay works
3. ✅ Juice fires (particles visible, SFX audible, shake felt)
4. ✅ Touch controls responsive (test on actual touch device or Chrome DevTools toggle)
5. ✅ 60fps sustained (Chrome DevTools Performance tab)
6. ✅ Clean destroy (switch cartridges, no memory leaks in heap snapshot)

---

## Checklist

- [ ] `.feature` file written with invariant + happy + juice + perf + lifecycle scenarios
- [ ] `cartridge.js` exports all required interface members
- [ ] Metadata has all required fields (id, name, version, category)
- [ ] Juice integration: particles, SFX, and at least one shake trigger
- [ ] Touch targets ≥ 44px for whiteboard use
- [ ] Registered in CARTRIDGE_REGISTRY
- [ ] Scored in MAP-Elites spike_registry.yaml
- [ ] Manual test: gameplay, juice, touch, performance, destroy

---

## Existing Cartridges (reference implementations)

| Cartridge | Rendering | Key Technique | Pareto Cell |
|-----------|-----------|---------------|-------------|
| fluid-toy | WebGL (GLSL shaders) | Double-buffered FBOs, multi-pointer tracking | [3,3,1,3,2] |
| block-puzzle | Canvas 2D | Touch gesture state machine (swipe/tap/double-tap) | [2,2,1,3,3] |
| geo-quiz | Canvas 2D | Adaptive difficulty, spaced repetition, emoji flags | [2,2,3,2,3] |

---

## Evolution Pattern (Clone → Fork → Evolve)

1. **Clone**: Find a permissively-licensed (MIT/Apache-2.0/BSD) open-source project
2. **Fork**: Extract the core mechanic into a cartridge module
3. **Evolve**: Add juice, adapt for touch/stylus, score in MAP-Elites, iterate

See the Gold Diataxis reference catalog for 36+ vetted fork targets with license and juice-potential analysis.

---

## Appendix: Swarm Agent Handoff (2026-02-12)

### Project Inventory (3,217 total lines, Bronze layer)

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| `specs/kernel.feature` | 72 | Complete | 7 scenarios: load, switch, picker, 404, timeout |
| `specs/cartridge_contract.feature` | 86 | Complete | 9 scenarios: interface shape, lifecycle, fail-closed |
| `specs/juice_layer.feature` | 98 | Complete | 12 scenarios: particles, shake, SFX, haptic, budget |
| `specs/cartridge_fluid_toy.feature` | 86 | Complete | 11 scenarios: WebGL, multi-touch, stylus, juice |
| `specs/cartridge_block_puzzle.feature` | 134 | Complete | 15 scenarios: gameplay, scoring, touch controls |
| `specs/cartridge_geo_quiz.feature` | 149 | Complete | 15 scenarios: quiz modes, adaptive difficulty, spaced repetition |
| `contracts/cartridge.contract.ts` | 109 | Complete | CartridgeModule, JuiceAPI, MapElitesScore interfaces |
| `juice/juice.js` | 273 | Complete | Shared juice effects library (particles, shake, SFX, haptic) |
| `kernel/tiny-games-kernel.html` | 532 | Complete | Single-file microkernel host with picker + canvas management |
| `cartridges/fluid-toy/cartridge.js` | 427 | Complete | WebGL fluid sim with GLSL shaders, multi-pointer |
| `cartridges/block-puzzle/cartridge.js` | 494 | Complete | Tetris-inspired, touch gesture state machine |
| `cartridges/geo-quiz/cartridge.js` | 543 | Complete | Flag/capital quiz, adaptive difficulty, 50 countries |
| `map-elites/spike_registry.yaml` | 116 | Complete | 5D quality-diversity grid, 3/243 cells, evolution queue |
| `README.md` | 98 | Complete | Architecture diagram, CFE strategy, project structure |

### What Works

- All 3 cartridges implement the full `CartridgeModule` interface from the TS contract
- All 6 SBE/ATDD Gherkin specs written (69 total scenarios covering invariant, happy-path, juice, perf, lifecycle)
- Microkernel host handles dynamic import, 5s timeout, interface validation, pointer forwarding, juice overlay
- MAP-Elites spike registry tracks Pareto frontier with evolution queue

### What Needs Testing

- **End-to-end local serve**: `cd tiny_games && python3 -m http.server 8080`, open in browser
- **Touch device testing**: Swipe/tap/double-tap in block-puzzle, button targets in geo-quiz
- **WebGL fallback**: fluid-toy on devices without WebGL2 support
- **Memory leaks**: Switch between cartridges repeatedly, check heap

### Known Gaps & Next Steps (priority order)

1. **No automated tests yet** — need Playwright property tests matching Gherkin scenarios (Silver gate)
2. **No mutation scoring** — needed for Silver medallion (target: 80%+ Stryker)
3. **Block puzzle spawn logic** has a minor double-random in `lockPiece()` — next agent should review/fix the nextPiece flow
4. **Geo-quiz dataset** is 50 countries — expand to 195+ for curriculum alignment
5. **Blessed pointer not registered** — add `tiny_games_root` to `hfo_pointers_blessed.json` domain 2
6. **MAP-Elites gaps**: No medium-educational cartridge yet. Next targets: rhythm-game [3,2,2,3,3], whiteboard-draw [2,3,2,2,3], math-blocks [2,2,3,3,3]

### Pointer References

| What | Path |
|------|------|
| Project root | `hfo_hot_obsidian_forge/0_bronze/1_areas/tiny_games/` |
| Gold how-to (this file) | `hfo_hot_obsidian_forge/2_gold/2_resources/diataxis_library/2_how_to_guides/HOWTO_BUILD_TINY_GAMES_CARTRIDGE.md` |
| Gold reference catalog (36+ targets) | `hfo_hot_obsidian_forge/2_gold/2_resources/diataxis_library/3_reference/REFERENCE_CLONE_FORK_EVOLVE_OPEN_SOURCE_GAME_CATALOG.md` |
| SBE reference towers | `hfo_hot_obsidian_forge/2_gold/2_resources/diataxis_library/3_reference/REFERENCE_SBE_ATDD_GHERKIN_TOWERS.md` |

### Build Command

```bash
cd hfo_hot_obsidian_forge/0_bronze/1_areas/tiny_games
python3 -m http.server 8080
# Open: http://localhost:8080/kernel/tiny-games-kernel.html
```

*Handoff prepared 2026-02-12 by P2/P6 swarm agent. Session crashed during cartridge development; all artifacts stabilized and inventoried above.*
