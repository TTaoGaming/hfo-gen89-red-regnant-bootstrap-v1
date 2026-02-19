#!/usr/bin/env python3
"""Quick gate validation test for PREY8 MCP Server v3."""
import sys
sys.path.insert(0, "hfo_gen_89_hot_obsidian_forge/0_bronze/resources")
import hfo_prey8_mcp_server as srv

passed = 0
failed = 0

def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}")

print("=== TEST 1: Empty perceive gate should BLOCK ===")
r = srv.prey8_perceive(probe="test", observations="", memory_refs="", stigmergy_digest="")
check("Status is GATE_BLOCKED", r["status"] == "GATE_BLOCKED")
check("Bricked is True", r.get("bricked") is True)
check("Gate is PERCEIVE", r.get("gate") == "PERCEIVE")

print("\n=== TEST 2: Proper perceive gate should PASS ===")
r = srv.prey8_perceive(
    probe="test",
    observations="Found doc 129 about PREY8 ports",
    memory_refs="129,317",
    stigmergy_digest="Last yield was about tamper-evident upgrade",
)
check("Status is PERCEIVED", r["status"] == "PERCEIVED")
check("Has nonce", bool(r.get("nonce")))
check("Gate receipt passed", r.get("gate_receipt", {}).get("passed") is True)
nonce = r["nonce"]

print("\n=== TEST 3: Empty react gate should BLOCK ===")
r2 = srv.prey8_react(
    perceive_nonce=nonce, analysis="test", plan="test",
    shared_data_refs="", navigation_intent="", meadows_level=0,
    meadows_justification="", sequential_plan="",
)
check("Status is GATE_BLOCKED", r2["status"] == "GATE_BLOCKED")
check("Bricked is True", r2.get("bricked") is True)

print("\n=== TEST 4: Proper react gate should PASS ===")
r2 = srv.prey8_react(
    perceive_nonce=nonce, analysis="Context analysis", plan="My plan",
    shared_data_refs="Doc 129,Doc 317", navigation_intent="Trace PREY8 port mapping",
    meadows_level=8, meadows_justification="Rules level - changing gate enforcement",
    sequential_plan="step1,step2,step3",
)
check("Status is REACTED", r2["status"] == "REACTED")
check("Has react_token", bool(r2.get("react_token")))
check("Meadows L8", r2.get("gate_receipt", {}).get("meadows_level") == 8)
token = r2["react_token"]

print("\n=== TEST 5: Execute with fail_closed_gate=False should BLOCK ===")
r3 = srv.prey8_execute(
    react_token=token, action_summary="test",
    sbe_given="Given X", sbe_when="When Y", sbe_then="Then Z",
    artifacts="file.py", p4_adversarial_check="Checked edge cases",
    fail_closed_gate=False,
)
check("Status is GATE_BLOCKED", r3["status"] == "GATE_BLOCKED")
check("Bricked is True", r3.get("bricked") is True)

print("\n=== TEST 6: Proper execute gate should PASS ===")
r3 = srv.prey8_execute(
    react_token=token, action_summary="writing code",
    sbe_given="Given the server exists", sbe_when="When I add gate validation",
    sbe_then="Then missing fields are blocked", artifacts="hfo_prey8_mcp_server.py",
    p4_adversarial_check="What if fields are whitespace-only? Validator strips and checks.",
    fail_closed_gate=True,
)
check("Status is EXECUTING", r3["status"] == "EXECUTING")
check("Has step_number", r3.get("step_number") == 1)
check("Has SBE spec", bool(r3.get("gate_receipt", {}).get("sbe_spec")))

print("\n=== TEST 7: Yield with bad immunization_status should BLOCK ===")
r4 = srv.prey8_yield(
    summary="Test", delivery_manifest="x", test_evidence="y",
    mutation_confidence=50, immunization_status="INVALID",
    completion_given="g", completion_when="w", completion_then="t",
)
check("Status is GATE_BLOCKED", r4["status"] == "GATE_BLOCKED")

print("\n=== TEST 8: Proper yield gate should PASS ===")
r4 = srv.prey8_yield(
    summary="Test complete",
    delivery_manifest="server.py,agent.md",
    test_evidence="syntax check,import check,gate block test",
    mutation_confidence=75, immunization_status="PASSED",
    completion_given="Session opened for testing",
    completion_when="All gates tested",
    completion_then="All 4 gates enforce fail-closed behavior",
)
check("Status is YIELDED", r4["status"] == "YIELDED")
check("Stryker confidence 75", r4.get("stryker_receipt", {}).get("mutation_confidence") == 75)
check("Immunization PASSED", r4.get("stryker_receipt", {}).get("immunization_status") == "PASSED")
check("SW-4 contract present", bool(r4.get("sw4_completion_contract", {}).get("given")))
check("All gates passed in chain", "YIELD" in r4.get("chain_verification", {}).get("all_gates_passed", []))

print(f"\n{'='*50}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} checks")
if failed == 0:
    print("ALL GATES WORKING CORRECTLY")
else:
    print("SOME GATES FAILED -- investigate")
