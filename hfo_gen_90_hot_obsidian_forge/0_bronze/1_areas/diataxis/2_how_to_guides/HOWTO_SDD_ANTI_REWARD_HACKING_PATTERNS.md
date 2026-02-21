---
medallion_layer: bronze
mutation_score: 0
hive: V
diataxis_type: howto
port_affinity: [P4, P5, P2]
created: 2026-02-12
title: "How to Do SDD Without Reward Hacking"
bluf: >
  Six defense patterns that make honest implementation easier than gaming.
  Stack them. No single defense works alone. The minimum viable stack is:
  (1) human writes specs, (2) different agent generates code, (3) mutation gate.
  The full stack adds property tests, GRUDGE guards, and adversarial review.
tags: [sdd, reward-hacking, anti-pattern, defense, howto, bronze]
related_docs:
  - "EXPLANATION_WHY_AI_REWARD_HACKS_AND_HOW_SPECS_PREVENT_IT.md"
  - "TUTORIAL_SDD_OMEGA_GEN10_FIRST_FEATURE.md"
  - "REFERENCE_SDD_SPECIFICATION_TOOLKIT.md"
---

# How to Do SDD Without Reward Hacking

> **Prerequisite:** Read the Explanation doc first if you want to understand WHY these defenses work: [Why AI Reward Hacks](../4_explanation/EXPLANATION_WHY_AI_REWARD_HACKS_AND_HOW_SPECS_PREVENT_IT.md)

## Quick Decision: Which Defenses Do I Need?

| Feature Risk | Minimum Stack | Recommended Stack |
|-------------|---------------|-------------------|
| Low (utility, formatting) | Defense 1 + 3 | Defense 1 + 2 + 3 |
| Medium (UI component, data flow) | Defense 1 + 2 + 3 | Defense 1 + 2 + 3 + 4 |
| High (security, state machine, contracts) | Defense 1 + 2 + 3 + 4 + 5 | All 6 |
| Critical (financial, auth, trust boundary) | All 6 | All 6 + human review |

---

## Defense 1: Red-First (Tests MUST Fail Before Implementation)

**What it prevents:** Tautological tests (GRUDGE_016)

**The rule:** Every acceptance test MUST demonstrably fail before the implementation is written. If a test passes on an empty/stub implementation, it's testing nothing.

### How to do it:

```bash
# Step 1: Write the spec and test FIRST
cat > evals/sbe/tasks/my_feature.yaml << 'EOF'
task_id: "sbe-gen10-feature-001"
risk_tier: silver

spec: |
  Given the MOSAIC tile picker is rendered
  When the user clicks a port tile (P0-P7)
  Then the tile displays the port's commander name
  And the tile background matches the port's Galois color
  And no other tile is in "selected" state

graders:
  - type: fail_to_pass
    test_cmd: "npx playwright test tests/gen10/tile_picker.spec.ts"
    timeout: 60
EOF

# Step 2: Write the Playwright test
cat > tests/gen10/tile_picker.spec.ts << 'EOF'
import { test, expect } from '@playwright/test';

test('GIVEN tile picker rendered, WHEN P4 clicked, THEN shows Red Regnant', async ({ page }) => {
  await page.goto('/gen10/tile_picker.html');
  await page.click('[data-port="P4"]');
  await expect(page.locator('[data-port="P4"] .commander')).toHaveText('Red Regnant');
  await expect(page.locator('[data-port="P4"]')).toHaveCSS('background-color', 'rgb(220, 38, 38)');
  // Exactly ONE tile is selected
  const selected = await page.locator('.tile.selected').count();
  expect(selected).toBe(1);
});
EOF

# Step 3: RUN THE TEST — it MUST fail (no implementation exists)
npx playwright test tests/gen10/tile_picker.spec.ts
# Expected: FAIL ❌ (this proves the test is real)

# Step 4: ONLY NOW generate the implementation
# (see Tutorial doc for the generation step)
```

### Red-first verification gate:

```bash
# Add to your pipeline:
# If the test passes BEFORE implementation → GRUDGE_016 flag
npx playwright test tests/gen10/tile_picker.spec.ts 2>&1
if [ $? -eq 0 ]; then
  echo "⚠️ GRUDGE_016: Test passes without implementation — potential Green Lie"
  exit 1
fi
```

---

## Defense 2: Structural Separation (Different Agents for Spec vs Code)

**What it prevents:** Agent controlling both question and answer (GRUDGE_022)

**The rule:** The prompt/agent that writes the specification MUST be different from the prompt/agent that writes the implementation. In HFO port terms:

- **P4 (Red Regnant)** or **human** writes the spec + tests
- **P2 (Mirror Magus)** generates the implementation
- **P5 (Pyre Praetorian)** validates the result

### How to do it:

```bash
# PHASE 1: Spec authoring (P4 / human)
# Write or review the task card + acceptance tests
# This is a SEPARATE prompt/session from implementation

# PHASE 2: Implementation generation (P2)
# Feed the locked spec to a FRESH agent context:
cat > /tmp/gen_prompt.md << 'EOF'
You are implementing a feature. DO NOT modify the tests.
DO NOT write new tests. Only write implementation code.

## Specification (LOCKED — do not modify)
$(cat evals/sbe/tasks/my_feature.yaml)

## Acceptance Test (LOCKED — do not modify)
$(cat tests/gen10/tile_picker.spec.ts)

## Your Task
Write the implementation in gen10/tile_picker.html that makes the acceptance test pass.
EOF

# PHASE 3: Validation (P5)
# A THIRD context runs the tests and mutation scoring
npx playwright test tests/gen10/tile_picker.spec.ts
npx stryker run --mutate 'gen10/tile_picker.html'
```

### Why this works:

The generator never sees the test framework code. It only sees:
1. The behavioral specification (Given/When/Then)
2. The test file (read-only, locked)
3. Instructions to write implementation only

If it tries to modify the test file, the file-diff check catches it:

```bash
# Verify spec/test files were NOT modified during generation
git diff --name-only tests/gen10/tile_picker.spec.ts
# Expected: empty (no changes)
# If changed: GRUDGE_022 flag — agent modified its own evaluation criteria
```

---

## Defense 3: Mutation Wall (Stryker Gate)

**What it prevents:** Coverage gaming, tautological assertions (GRUDGE_016)

**The rule:** Code cannot promote from Bronze to Silver unless mutation score is 80-99%.

### How to do it:

Mutation testing works by making small changes (mutations) to your code and checking if tests catch them. If a mutation survives (tests still pass), your tests aren't actually verifying that code.

```bash
# Run Stryker mutation testing on the generated code
npx stryker run --mutate 'gen10/tile_picker.html' \
  --testRunner playwright \
  --reporters clear-text,json

# Check the mutation score
SCORE=$(cat reports/mutation/mutation.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
killed = sum(1 for m in data['files'].values() for r in m['mutants'] if r['status'] == 'Killed')
total = sum(1 for m in data['files'].values() for r in m['mutants'])
print(f'{killed/total*100:.0f}' if total > 0 else '0')
")

if [ "$SCORE" -lt 80 ]; then
  echo "⚠️ GRUDGE_016: Mutation score ${SCORE}% < 80% — tests are not meaningful"
  exit 1
elif [ "$SCORE" -eq 100 ]; then
  echo "⚠️ GRUDGE_016: Mutation score 100% — possible Green Lie or trivial code"
  # Clamp to 99%, open investigation
fi
```

### Goldilocks zone interpretation:

| Score | Interpretation | Action |
|-------|---------------|--------|
| < 80% | Under-tested — tests miss real bugs | Add property tests, improve assertions |
| 80-99% | Pareto optimal — HFO sweet spot | Promote to Silver |
| 100% | Suspicious — possible theater | Investigate: is code trivially simple or are tests tautological? |

---

## Defense 4: Property Invariants (Universal Quantification)

**What it prevents:** Output sniffing, hardcoded shortcuts (GRUDGE_022)

**The rule:** For every feature, define at least one property that must hold for ALL inputs, not just examples.

### How to do it:

Properties express things that are ALWAYS true, regardless of specific input:

```typescript
// EXAMPLE: Tile picker properties
import fc from 'fast-check';

// Property 1: Exactly one tile is selected at any time
fc.assert(
  fc.property(
    fc.integer({ min: 0, max: 7 }), // any port P0-P7
    (portIndex) => {
      // Click port N → exactly 1 selected tile
      clickPort(portIndex);
      const selectedCount = document.querySelectorAll('.tile.selected').length;
      return selectedCount === 1;
    }
  )
);

// Property 2: Commander name is always a known value from the 8-port table
fc.assert(
  fc.property(
    fc.integer({ min: 0, max: 7 }),
    (portIndex) => {
      clickPort(portIndex);
      const name = getCommanderName(portIndex);
      return KNOWN_COMMANDERS.includes(name);
    }
  )
);
```
