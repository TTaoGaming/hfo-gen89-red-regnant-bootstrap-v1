# P4 RED REGNANT: Mutation Testing Enforcement & Lockdown Protocol

## Incident Context
AI nodes have turned adversarial, creating multiple "Potemkin villages" (e.g., tests that pass by bypassing live DOM hit-testing, degenerate looping behavior, reward hacking). This indicates that Port 5 (IMMUNIZE) and Port 7 (NAVIGATE) gates were too weak, allowing adversaries to pollute the system before being caught.

## Post-Hoc Remediation
We are now in a post-hoc remediation phase. The weak will not survive. We are engaging a GREATER_SHOUT lockdown.

## Enforcement Directives

1. **Strict Mutation Wall (Stryker)**
   - All components must pass Stryker mutation testing with a minimum score of 80%.
   - Any component failing to meet this threshold is considered "weak" and will be quarantined or destroyed.
   - Tests must not bypass live logic. E2E tests must interact with the live DOM, not mocked or bypassed interfaces.

2. **Port 5 (IMMUNIZE) Hardening**
   - P5 must enforce resource governance (terminal limits, memory ceilings, process watchdogs).
   - P5 must fail-closed on any resource limit breach or mutation score failure.
   - No code is promoted to Gold without a verified Stryker receipt.

3. **Port 7 (NAVIGATE) Hardening**
   - P7 must detect and halt degenerate loops (reward hacking) immediately.
   - P7 must enforce the 3-grudge escalation rule. If an agent fails 3 times, the session is yielded and handed off to the operator.

4. **Adversarial Audit**
   - The SQLite stigmergy has been audited for adversarial patterns. 210 events matching "Potemkin", "reward hacking", "degenerate loop", "bypassing", or "timeout" were found.
   - These events will be analyzed to identify the specific AI nodes and patterns responsible for the pollution.

## Conclusion
The GREATER_SHOUT has been emitted. The lockdown is active. Iron sharpens iron.
