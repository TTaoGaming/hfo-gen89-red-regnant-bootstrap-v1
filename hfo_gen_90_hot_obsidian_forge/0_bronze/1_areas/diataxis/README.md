# Diataxis Library (Bronze)

This is the bronze staging area for the Diataxis library.

## Medallion Architecture Enforcement

**CRITICAL:** You cannot write directly to the `2_gold` layer. All new artifacts must be created here in `0_bronze`.

### Promotion Process

1. **Bronze (0):** Trust nothing. Raw ingestion. May contain hallucinations, duplicates, stale data.
2. **Silver (1):** Human-reviewed or automated-validation-passed. Factual claims verified.
3. **Gold (2):** Hardened. Cross-referenced. Tested against invariants.

To promote an artifact from Bronze to Silver to Gold, it must pass explicit validation gates.

## Structure

- `1_tutorials/`: Walkthroughs that teach a complete workflow from start to finish.
- `2_how_to_guides/`: Recipes for solving specific problems. Each has a concrete goal and proof step.
- `3_reference/`: Authoritative lookup documents.
- `4_explanations/`: Deep dives, trade studies, and theoretical background.
