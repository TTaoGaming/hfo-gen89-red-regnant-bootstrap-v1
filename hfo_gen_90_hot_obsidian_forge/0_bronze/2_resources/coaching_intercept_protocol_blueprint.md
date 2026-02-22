# PREY8 MCP Server: Coaching Intercept Protocol Blueprint

**TARGET:** PREY8 Python MCP Server (`hfo_prey8_mcp_server.py`)
**OBJECTIVE:** Implement a "fail-closed with guidance" protocol to coach LLMs when they violate the PREY8 phase order.

## 1. The Problem: Silent Failures & Confusion
Currently, when an AI agent violates the PREY8 state machine (e.g., calling `prey8_execute` before `prey8_perceive`), the server throws hard errors or generic "phase_violation" messages. This confuses the LLM, leading to wasted tool calls or session abandonment.

## 2. The Solution: Coaching Intercept Protocol
We must intercept phase violations and return highly specific, actionable coaching strings. The response must:
1. Block the action (Fail-Closed).
2. State the exact error and the current phase.
3. Provide the exact command/tool call required to recover.

## 3. The 4 Violation Patterns & Coaching Strings

### Pattern A: Action from Idle
**Trigger:** Calling `prey8_react`, `prey8_execute`, or `prey8_yield` when the session state is `IDLE` (no active nonce).
**Coaching String:**
```json
{
  "status": "GATE_BLOCKED",
  "error": "PHASE VIOLATION (BLOCKED): You attempted to call {tool_name} but your session is IDLE. You likely have amnesia from a new chat window. Recovery Action: Call prey8_perceive with your agent_id to rehydrate your identity and state from SQLite."
}
```

### Pattern B: Skipping React
**Trigger:** Calling `prey8_execute` immediately after `prey8_perceive` (current phase is `PERCEIVED`), skipping the `prey8_react` phase.
**Coaching String:**
```json
{
  "status": "GATE_BLOCKED",
  "error": "PHASE VIOLATION (BLOCKED): You attempted to call prey8_execute but your session is in the PERCEIVED phase. You skipped the React phase. Recovery Action: Call prey8_react with your perceive_nonce to formulate your plan before executing."
}
```

### Pattern C: Double React
**Trigger:** Calling `prey8_react` when the session is already in the `REACTED` phase.
**Coaching String:**
```json
{
  "status": "GATE_BLOCKED",
  "error": "PHASE VIOLATION (BLOCKED): You attempted to call prey8_react but your session is already in the REACTED phase. You cannot react twice in a row. Recovery Action: Call prey8_execute with your react_token to perform your planned actions, or prey8_yield to close the session."
}
```

### Pattern D: Stale Nonce
**Trigger:** Providing a nonce or token that does not match the current active session state (e.g., using a nonce from a previous turn).
**Coaching String:**
```json
{
  "status": "GATE_BLOCKED",
  "error": "CRYPTOGRAPHIC VIOLATION (BLOCKED): The nonce or token you provided ({provided_token}) is stale or invalid for the current session state. Recovery Action: Check your most recent tool response for the correct token, or call prey8_session_status to retrieve your current valid tokens."
}
```

## 4. Implementation Directives
1. Update the state machine validation logic in `hfo_prey8_mcp_server.py`.
2. Intercept these specific state transitions and return the exact JSON strings above instead of generic exceptions.
3. Ensure the HTTP status code remains 200 OK so the LLM can read the JSON payload (do not throw 500s for coaching).
