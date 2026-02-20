## SBE / ATDD: Eval Orchestrator (Specification by Example)

Purpose: Minimal-input acceptance tests for the orchestrator and diagnostics. Use these as SBE examples to drive ATDD tests.

1) Run once — One-off SBE (Invariant tier)
Given: Ollama API reachable and model `qwen2.5:7b` is pulled
When: `python hfo_eval_orchestrator.py --model qwen2.5:7b --limit 5 --once` is executed
Then: `hfo_perceive.py` wrote a `hfo.gen89.prey8.perceive` event to `stigmergy_events`
Then: `prey8_eval_harness.py` produced a log file in `0_bronze/resources/orchestrator_outputs`
Then: `hfo_yield.py` wrote a `hfo.gen89.prey8.yield` event to `stigmergy_events`

Acceptance criteria:
- Perceive event written (content_hash present)
- Eval log exists and is non-empty
- Yield event written and references the perceive nonce

2) Continuous run — Happy-path SBE
Given: Orchestrator installed as scheduled task or service
When: System starts or scheduled task triggers
Then: Orchestrator produces at least one recap JSON within 1 hour

Acceptance criteria:
- Recap JSON includes `perceive_nonce`, `eval_returncode`, and `yield_receipt`

3) Diagnostics — Invariant / Monitoring SBE
Given: Windows host with Intel Arc GPU and Python available
When: `diagnose_gpu_npu.ps1` is run
Then: Output contains GPU name and driver version
And: Output shows Ollama `/api/ps` and `/api/tags` responses (or clear error messages)

Notes on minimal user input:
- Model name and limit are the only required CLI inputs for orchestrator; default probe text is auto-generated.
- Service install helpers provided (`windows_service_install.ps1`) minimize interactive steps.
