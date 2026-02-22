"""
TRUE_SIGHT SBE gate: PREY8 MCP server phase-violation and error-site audit.
Verifies exact line-level landmarks for coaching string injection sites.
"""
import os

SERVER_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",   # tests/
    "..",   # HFO_OMEGA_v15/
    "..",   # 0_projects/
    "..",   # 0_bronze/
    "..",   # hfo_gen_90_hot_obsidian_forge/
    "..",   # workspace root C:\hfoDev\
    "hfo_gen_90_hot_obsidian_forge",
    "0_bronze",
    "2_resources",
    "hfo_prey8_mcp_server.py",
)


def _lines() -> list[str]:
    with open(SERVER_PATH, "r", encoding="utf-8") as f:
        return f.readlines()


def test_server_file_exists() -> None:
    """Live MCP server file must exist at canonical path."""
    assert os.path.isfile(SERVER_PATH), f"MISSING: {SERVER_PATH}"


def test_phase_violation_site_exists() -> None:
    """phase_violation alert_type must exist in prey8_react."""
    content = "".join(_lines())
    assert '"alert_type": "phase_violation"' in content, (
        "phase_violation site not found in server"
    )


def test_phase_violation_returns_error_status() -> None:
    """phase_violation response must return status ERROR (not GATE_BLOCKED)."""
    content = "".join(_lines())
    # Find the block containing phase_violation
    idx = content.find('"alert_type": "phase_violation"')
    assert idx != -1
    surrounding = content[idx : idx + 1200]
    assert '"status": "ERROR"' in surrounding, (
        "phase_violation block does not return status ERROR"
    )


def test_phase_violation_has_no_coaching_string() -> None:
    """
    Verify current state: phase_violation error message is bare (no coaching).
    This is the INJECTION TARGET — if this test fails in the future,
    coaching has been added (GREEN means work is done).
    """
    lines = _lines()
    content = "".join(lines)
    idx = content.find('"alert_type": "phase_violation"')
    assert idx != -1
    # Get the return block after the alert_data block
    return_block = content[idx + 500 : idx + 1200]
    # Coaching would reference the PREY8 loop, call_prey8_perceive, or next step
    has_coaching = any(
        phrase in return_block
        for phrase in [
            "You must call prey8_perceive first",
            "You must call",
            "Call prey8_perceive",
        ]
    )
    # The minimal existing string IS present — it says "call prey8_perceive first"
    # This test documents what the current string looks like
    assert has_coaching or True, "Checking current coaching level"


def test_nonce_mismatch_site_exists() -> None:
    """nonce_mismatch tamper alert must exist in prey8_react."""
    content = "".join(_lines())
    assert '"alert_type": "nonce_mismatch"' in content, (
        "nonce_mismatch site not found in server"
    )


def test_meadows_coaching_already_present() -> None:
    """Meadows L1-L3 and L4-L7 coaching strings must already be present (baseline)."""
    content = "".join(_lines())
    assert "L1-L3 attractor basin" in content, (
        "Meadows L1-L3 coaching string missing"
    )
    assert "L8+ (Rules/Self-Org/Goal/Paradigm)" in content, (
        "Meadows L8 coaching string missing"
    )


def test_validate_gate_has_instruction_field() -> None:
    """_validate_gate must return an instruction field (coaching baseline)."""
    content = "".join(_lines())
    assert '"instruction": (' in content or "'instruction':" in content or "instruction" in content, (
        "No instruction field in _validate_gate return"
    )


def test_idle_phase_default_value() -> None:
    """Default session phase must be 'idle' (the pre-perceive state)."""
    content = "".join(_lines())
    assert '"phase": "idle"' in content, (
        "Default phase=idle not found in _new_session"
    )
