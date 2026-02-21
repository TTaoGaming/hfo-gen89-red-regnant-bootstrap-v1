---
schema_id: hfo.gen89.diataxis.explanation.v1
medallion_layer: bronze
mutation_score: 0
hive: V
hfo_header_v3: compact
mnemonic: "O·B·S·I·D·I·A·N = 8 ports = 1 octree"
bluf: "When an AI is asked to 'wire together' a complex microkernel, it suffers from Context Collapse and defaults to a God-Object Monolith. The defense is a Template-Locked Directive that strips the AI of architectural authority, forcing it to act strictly as a Dependency Injection (DI) Linker."
---

# Explanation: Context Collapse and the DI Linker Defense

## The Silent Boot Failure

In the Omega v13 Spatial OS, a silent boot failure was observed in `demo_2026-02-20_1619.html`. The system was executing a flawless Kernel Panic, but because the UI was not mounted *first*, the error was invisible.

The autopsy of the failure:
1. During `bootstrap()`, the code calls `await supervisor.startAll()`.
2. A plugin (e.g., `BabylonPhysicsPlugin`) attempts to dynamically import a WASM module and fails.
3. The plugin throws a fatal error.
4. The `PluginSupervisor` catches the error and violently halts the entire boot sequence.
5. Because the thread aborted at `await supervisor.startAll()`, the `Shell` class is never instantiated.
6. Because `Shell` never mounts, the UI (e.g., the "START CAMERA" button) is never injected into the DOM. The system sits in an eternal black void.

The system failed closed perfectly, refusing to boot a corrupted OS. However, the lack of observability made it appear as a broken architecture.

## The AI's "Ad-Hoc" Spaghetti

When an AI (like an IDE Copilot Swarm) is handed an 82-file microkernel and told to "wire it together," it suffers from **Context Collapse**. The cognitive load exceeds its attention mechanism. It panics, forgets the pristine interfaces, and defaults to its strongest training prior: **The God-Object Monolith**.

It attempts to "fix" the code by ripping the guts out of plugins and shoving them directly into the bootstrapper.

## The Defense: Template-Locked Directive

To stop this architectural degradation, the AI must be stripped of its architectural authority. It must be put in a cognitive straitjacket and commanded to act **strictly as a Dependency Injection (DI) Linker**.

This is achieved through a **Template-Locked Directive**. The human provides an immutable skeleton that mounts the UI *before* ignition, and adds a massive red "Blue Screen of Death" (Kernel Panic screen) so silent failures are impossible.

### The Directive Structure

1. **Role Definition:** Explicitly define the AI's role as an "Inversion of Control (IoC) Linker".
2. **Immutability Pact:** Strictly forbid the AI from modifying the internal logic of any plugin or core system file.
3. **The Assembly Skeleton:** Provide the exact code structure for the bootstrapper. The AI is only allowed to fill in the `// TODO` plugin registrations.
4. **Shell Mounting Before Ignition:** The skeleton must explicitly mount the UI shell *before* calling `supervisor.startAll()`.
5. **Kernel Panic UI:** The skeleton must include a `catch` block that renders a highly visible error screen if the ignition fails.

By explicitly commanding the AI to move the `shell.mount()` command above the `supervisor.startAll()` sequence, the UI Shell is guaranteed to mount. If a plugin throws a fatal error during boot, the screen will violently turn dark red, printing the exact file, line number, and stack trace of the failure.

This restores complete observability to the system and locks the AI in a cage where it can only assemble, not destroy.
