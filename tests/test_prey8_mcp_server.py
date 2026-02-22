import sys
from pathlib import Path
from pytest_mock import MockerFixture
import pytest
from datetime import datetime

# Add the resources directory to sys.path so we can import the MCP server
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hfo_gen_90_hot_obsidian_forge" / "0_bronze" / "2_resources"))

import hfo_prey8_mcp_server as prey8  # type: ignore[import-not-found]


@pytest.fixture(autouse=True)
def _isolate_sessions() -> object:
    """Clear all PREY8 session state before and after each test.

    This prevents cross-test contamination via the shared prey8._sessions dict.
    """
    prey8._sessions.clear()
    yield
    prey8._sessions.clear()


def test_split_csv() -> None:
    assert prey8._split_csv("a, b, c") == ["a", "b", "c"]
    assert prey8._split_csv("  foo  , bar,") == ["foo", "bar"]
    assert prey8._split_csv("") == []
    assert prey8._split_csv(None) == []

def test_nonce() -> None:
    nonce1 = prey8._nonce()
    nonce2 = prey8._nonce()
    assert len(nonce1) == 6
    assert len(nonce2) == 6
    assert nonce1 != nonce2

def test_chain_hash() -> None:
    h = prey8._chain_hash("parent", "nonce123", '{"data": 1}')
    assert len(h) == 64  # SHA256 hex digest length

def test_content_hash() -> None:
    h1 = prey8._content_hash({"a": 1, "b": 2})
    h2 = prey8._content_hash({"b": 2, "a": 1})
    assert h1 == h2
    assert len(h1) == 64

def test_semantic_anti_slop_check() -> None:
    # Should return False for slop (too short)
    assert not prey8._semantic_anti_slop_check("short")
    
    # Should return False for slop (too few words but long enough)
    assert not prey8._semantic_anti_slop_check("supercalifragilistic string")
    
    # Should return False for slop (repeated words)
    assert not prey8._semantic_anti_slop_check("asdf asdf asdf asdf asdf asdf asdf asdf asdf asdf asdf")
    
    # Should return False for slop (common phrases)
    assert not prey8._semantic_anti_slop_check("asdf this is a long string that starts with asdf")
    
    # Should return True for clean text
    assert prey8._semantic_anti_slop_check("This is a perfectly valid and sufficiently long sentence that should pass the check.")

def test_validate_agent_empty(mocker: MockerFixture) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    result = prey8._validate_agent("", "PERCEIVE")
    assert result["status"] == "GATE_BLOCKED"
    assert "DENY_BY_DEFAULT" in result["reason"]

def test_validate_agent_unknown(mocker: MockerFixture) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    result = prey8._validate_agent("unknown_agent", "PERCEIVE")
    assert result["status"] == "GATE_BLOCKED"
    assert "DENY_BY_DEFAULT" in result["reason"]

def test_validate_agent_unauthorized_gate(mocker: MockerFixture) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    # p0_lidless_legion is only allowed PERCEIVE
    result = prey8._validate_agent("p0_lidless_legion", "EXECUTE")
    assert result["status"] == "GATE_BLOCKED"
    assert "LEAST_PRIVILEGE" in result["reason"]

def test_validate_agent_authorized(mocker: MockerFixture) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    result = prey8._validate_agent("p0_lidless_legion", "PERCEIVE")
    assert result is None  # None means validation passed

def test_validate_agent_dynamic_swarm(mocker: MockerFixture) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    result = prey8._validate_agent("p1_dynamic_agent", "PERCEIVE")
    assert result is None
    assert "p1_dynamic_agent" in prey8.AGENT_REGISTRY

def test_get_session() -> None:
    prey8._sessions.pop("test_agent", None)
    session = prey8._get_session("test_agent")
    assert session["agent_id"] == "test_agent"
    assert session["phase"] == "idle"
    
    # Should return the same session
    session2 = prey8._get_session("test_agent")
    assert session is session2

def test_cloudevent() -> None:
    event = prey8._cloudevent("test.event", {"foo": "bar"}, "test_subject", "test_agent")
    assert event["type"] == "test.event"
    assert event["subject"] == "test_subject"
    assert event["agent_id"] == "test_agent"
    assert event["data"]["foo"] == "bar"
    assert event["data"]["agent_id"] == "test_agent"
    assert "signature" in event
    assert "trace_id" in event
    assert "span_id" in event

def test_session_state_path() -> None:
    path = prey8._session_state_path("test_agent")
    assert path.name == ".prey8_session_test_agent.json"
    
    # Test sanitization
    path2 = prey8._session_state_path("test/agent\\with..dots")
    assert path2.name == ".prey8_session_test_agent_with_dots.json"

def test_save_and_load_session(mocker: MockerFixture, tmp_path: object) -> None:
    # Mock the session state directory to use a temporary path
    mocker.patch("hfo_prey8_mcp_server.SESSION_STATE_DIR", tmp_path)
    
    # Create and modify a session
    prey8._sessions.pop("test_agent", None)
    session = prey8._get_session("test_agent")
    session["session_id"] = "test_session_123"
    session["phase"] = "perceived"
    
    # Save it
    prey8._save_session("test_agent")
    
    # Load it back
    loaded = prey8._load_session("test_agent")
    assert loaded is not None
    assert loaded["session_id"] == "test_session_123"
    assert loaded["phase"] == "perceived"
    assert loaded["agent_id"] == "test_agent"

def test_load_session_not_found(mocker: MockerFixture, tmp_path: object) -> None:
    mocker.patch("hfo_prey8_mcp_server.SESSION_STATE_DIR", tmp_path)
    loaded = prey8._load_session("nonexistent_agent")
    assert loaded is None

def test_clear_session_file(mocker: MockerFixture, tmp_path: object) -> None:
    mocker.patch("hfo_prey8_mcp_server.SESSION_STATE_DIR", tmp_path)
    
    # Create a session file
    path = prey8._session_state_path("test_agent")
    path.write_text('{"session_id": "123"}')
    assert path.exists()
    
    # Clear it
    prey8._clear_session_file("test_agent")
    assert not path.exists()

def test_detect_memory_loss(mocker: MockerFixture) -> None:
    # Mock the database connection and query results
    mock_conn = mocker.MagicMock()
    mocker.patch("hfo_prey8_mcp_server._get_conn", return_value=mock_conn)
    
    # Mock perceives: one closed, one orphaned
    mock_conn.execute.side_effect = [
        [
            (1, "2026-01-01T00:00:00Z", '{"data": {"nonce": "closed_nonce", "session_id": "s1", "probe": "test1"}}'),
            (2, "2026-01-01T00:01:00Z", '{"data": {"nonce": "orphan_nonce", "session_id": "s2", "probe": "test2"}}')
        ],
        [
            (3, "2026-01-01T00:02:00Z", '{"data": {"perceive_nonce": "closed_nonce"}}')
        ]
    ]
    
    orphans = prey8._detect_memory_loss()
    assert len(orphans) == 1
    assert orphans[0]["perceive_nonce"] == "orphan_nonce"
    assert orphans[0]["session_id"] == "s2"

def test_record_memory_loss(mocker: MockerFixture) -> None:
    mock_write = mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=42)
    
    orphan_data = {"perceive_nonce": "orphan_nonce", "session_id": "s2"}
    row_id = prey8._record_memory_loss(orphan_data, "test_recovery", "test_agent")
    
    assert row_id == 42
    mock_write.assert_called_once()
    event = mock_write.call_args[0][0]
    assert event["type"] == "hfo.gen90.prey8.memory_loss"
    assert event["data"]["loss_type"] == "session_state_reset"
    assert event["data"]["recovery_source"] == "test_recovery"
    assert event["data"]["agent_id"] == "test_agent"
    assert event["data"]["orphaned_perceive_nonce"] == "orphan_nonce"

def test_validate_gate_valid(mocker: MockerFixture) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    fields = {
        "observations": ["obs1"],
        "memory_refs": ["ref1"],
        "stigmergy_digest": "digest"
    }
    result = prey8._validate_gate("PERCEIVE", fields, "test_agent")
    assert result is None

def test_validate_gate_missing_fields(mocker: MockerFixture) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    fields = {
        "observations": ["obs1"],
        # missing memory_refs
        "stigmergy_digest": "digest"
    }
    result = prey8._validate_gate("PERCEIVE", fields, "test_agent")
    assert result is not None
    assert result["status"] == "GATE_BLOCKED"
    assert "memory_refs" in result["missing_fields"]

def test_validate_gate_empty_fields(mocker: MockerFixture) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    fields = {
        "observations": [], # empty list
        "memory_refs": ["ref1"],
        "stigmergy_digest": "   " # empty string after strip
    }
    result = prey8._validate_gate("PERCEIVE", fields, "test_agent")
    assert result is not None
    assert result["status"] == "GATE_BLOCKED"
    assert "observations" in result["empty_fields"]
    assert "stigmergy_digest" in result["empty_fields"]

def test_validate_gate_invalid_meadows_level(mocker: MockerFixture) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    fields = {
        "shared_data_refs": ["ref1"],
        "navigation_intent": "intent",
        "meadows_level": 14, # invalid
        "meadows_justification": "justification",
        "sequential_plan": ["plan"],
        "tactical_plan": "This is a perfectly valid and sufficiently long sentence that should pass the check.",
        "strategic_plan": "This is a perfectly valid and sufficiently long sentence that should pass the check.",
        "sequential_thinking": "This is a perfectly valid and sufficiently long sentence that should pass the check.",
        "cynefin_classification": "complex"
    }
    result = prey8._validate_gate("REACT", fields, "test_agent")
    assert result is not None
    assert result["status"] == "GATE_BLOCKED"
    assert any("meadows_level" in f for f in result["empty_fields"])

def test_prey8_perceive_success(mocker: MockerFixture) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    mock_conn = mocker.MagicMock()
    mocker.patch("hfo_prey8_mcp_server._get_conn", return_value=mock_conn)
    
    # Mock the database queries to return safe defaults
    mock_cursor = mocker.MagicMock()
    mock_conn.execute.return_value = mock_cursor
    
    mock_cursor.fetchone.side_effect = [
        None, # last_yield_row
        (100,), # doc_count
        (1000,), # event_count
        None, None, None, None # ladder queries
    ]
    mock_cursor.fetchall.return_value = []
    mock_cursor.__iter__.return_value = iter([])
    
    result = prey8.prey8_perceive(
        agent_id="p0_lidless_legion",
        probe="test probe",
        observations="obs1, obs2",
        memory_refs="ref1",
        stigmergy_digest="override continuity"
    )
    
    assert "nonce" in result
    assert "chain_hash" in result
    assert "session_id" in result
    assert "gate_receipt" in result
    
    # Verify session state was updated

    session = prey8._load_session("p0_lidless_legion")
    assert session["phase"] == "perceived"
    assert session["perceive_nonce"] == result["nonce"]

def test_prey8_react_success(mocker: MockerFixture) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    
    # Setup session state
    prey8._sessions.pop("p1_web_weaver", None)
    session = prey8._get_session("p1_web_weaver")
    session["phase"] = "perceived"
    session["perceive_nonce"] = "test_nonce"
    session["session_id"] = "test_session"
    session["chain"] = [{"chain_hash": "parent_hash"}]
    
    result = prey8.prey8_react(
        agent_id="p1_web_weaver",
        perceive_nonce="test_nonce",
        analysis="test analysis",
        tactical_plan="This is a perfectly valid and sufficiently long sentence that should pass the check.",
        strategic_plan="This is a perfectly valid and sufficiently long sentence that should pass the check.",
        sequential_thinking="This is a perfectly valid and sufficiently long sentence that should pass the check.",
        cynefin_classification="complex",
        shared_data_refs="ref1, ref2",
        navigation_intent="intent",
        meadows_level=8, # Valid level >= 8
        meadows_justification="justification",
        sequential_plan="step1, step2"
    )
    
    assert "react_token" in result
    assert "chain_hash" in result
    assert "gate_receipt" in result
    assert result["gate_receipt"]["passed"]
    
    # Verify session state was updated
    assert session["phase"] == "reacted"
    assert session["react_token"] == result["react_token"]

def test_prey8_react_phase_violation(mocker: MockerFixture) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    
    # Setup session state in wrong phase
    prey8._sessions.pop("p1_web_weaver", None)
    session = prey8._get_session("p1_web_weaver")
    session["phase"] = "idle"
    
    result = prey8.prey8_react(
        agent_id="p1_web_weaver",
        perceive_nonce="test_nonce",
        analysis="test analysis",
        tactical_plan="plan",
        strategic_plan="plan",
        sequential_thinking="thinking",
        cynefin_classification="complex",
        shared_data_refs="ref1",
        navigation_intent="intent",
        meadows_level=8,
        meadows_justification="justification",
        sequential_plan="step1"
    )
    
    assert result["status"] == "ERROR"
    assert "phase violation" in result.get("tamper_evidence", "").lower()

def test_prey8_execute_success(mocker: MockerFixture, tmp_path: Path) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    mocker.patch("hfo_prey8_mcp_server._find_root", return_value=tmp_path)
    
    # Create the test file and artifact
    test_file = tmp_path / "test_file.py"
    test_file.write_text("def test_foo() -> None: pass")
    
    artifact_file = tmp_path / "file1.py"
    artifact_file.write_text("print('hello')")
    
    # Mock the test file execution to pass
    mocker.patch("subprocess.run", return_value=mocker.MagicMock(returncode=0, stdout="passed", stderr=""))
    
    # Setup session state
    prey8._sessions.pop("p2_mirror_magus", None)
    session = prey8._get_session("p2_mirror_magus")
    session["phase"] = "reacted"
    session["react_token"] = "test_token"
    session["session_id"] = "test_session"
    session["chain"] = [{"chain_hash": "parent_hash"}]
    # Set started_at to the past so mtime check passes
    session["started_at"] = "2020-01-01T00:00:00Z"
    
    result = prey8.prey8_execute(
        agent_id="p2_mirror_magus",
        react_token="test_token",
        action_summary="test action",
        sbe_given="This is a perfectly valid and sufficiently long sentence that should pass the check.",
        sbe_when="This is a perfectly valid and sufficiently long sentence that should pass the check.",
        sbe_then="This is a perfectly valid and sufficiently long sentence that should pass the check.",
        artifacts="file1.py",
        p4_adversarial_check="check",
        sbe_test_file="test_file.py"
    )
    
    assert "execute_token" in result
    assert "chain_hash" in result
    assert "gate_receipt" in result
    assert result["gate_receipt"]["passed"]
    
    # Verify session state was updated
    assert session["phase"] == "executing"
    assert len(session["execute_tokens"]) == 1
    assert session["execute_tokens"][0]["token"] == result["execute_token"]

def test_prey8_execute_phase_violation(mocker: MockerFixture) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    
    # Setup session state in wrong phase
    prey8._sessions.pop("p2_mirror_magus", None)
    session = prey8._get_session("p2_mirror_magus")
    session["phase"] = "idle"
    
    result = prey8.prey8_execute(
        agent_id="p2_mirror_magus",
        react_token="test_token",
        action_summary="test action",
        sbe_given="given",
        sbe_when="when",
        sbe_then="then",
        artifacts="file1.py",
        p4_adversarial_check="check",
        sbe_test_file="test_file.py"
    )
    
    assert result["status"] == "ERROR"
    assert "Cannot Execute" in result["error"]

def test_prey8_execute_token_mismatch(mocker: MockerFixture) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    
    # Setup session state
    prey8._sessions.pop("p2_mirror_magus", None)
    session = prey8._get_session("p2_mirror_magus")
    session["phase"] = "reacted"
    session["react_token"] = "correct_token"
    
    result = prey8.prey8_execute(
        agent_id="p2_mirror_magus",
        react_token="wrong_token",
        action_summary="test action",
        sbe_given="given",
        sbe_when="when",
        sbe_then="then",
        artifacts="file1.py",
        p4_adversarial_check="check",
        sbe_test_file="test_file.py"
    )
    
    assert result["status"] == "ERROR"
    assert "react_token_mismatch" in result.get("alert_type", "") or "TAMPER ALERT" in result.get("error", "")

def test_prey8_yield_success(mocker: MockerFixture, tmp_path: object) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    mocker.patch("hfo_prey8_mcp_server._find_root", return_value=tmp_path)
    
    # Mock the database connection for stored hashes
    mock_conn = mocker.MagicMock()
    mocker.patch("hfo_prey8_mcp_server._get_conn", return_value=mock_conn)
    mock_cursor = mocker.MagicMock()
    mock_cursor.fetchone.return_value = [0]
    mock_cursor.fetchall.return_value = []
    mock_conn.execute.return_value = mock_cursor
    
    # Mock fast checks to pass
    mocker.patch("hfo_prey8_mcp_server._run_fast_checks", return_value=(True, "passed"))
    
    # Clear any prior state for this agent to avoid cross-test contamination
    prey8._sessions.pop("p3_harmonic_hydra", None)
    
    # Setup session state
    session = prey8._get_session("p3_harmonic_hydra")
    session["phase"] = "executing"
    session["session_id"] = "test_session"
    session["chain"] = [{"chain_hash": "parent_hash", "step": "EXECUTE_1"}]
    session["meadows_level"] = 1
    session["cynefin_classification"] = "clear"
    session["started_at"] = "2020-01-01T00:00:00Z"
    
    result = prey8.prey8_yield(
        agent_id="p3_harmonic_hydra",
        summary="test summary",
        delivery_manifest="delivery1",
        test_evidence="test1",
        ai_confidence=85,
        immunization_status="PASSED",
        completion_given="given",
        completion_when="when",
        completion_then="then"
    )
    
    assert result["status"] == "YIELDED"
    assert "stryker_receipt" in result
    assert "sw4_completion_contract" in result
    assert "chain_verification" in result
    assert "gate_receipt" in result
    assert result["gate_receipt"]["passed"]
    
    # Verify session state was cleared
    assert prey8._get_session("p3_harmonic_hydra")["phase"] == "idle"

def test_prey8_yield_phase_violation(mocker: MockerFixture) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    
    # Setup session state in wrong phase
    prey8._sessions.pop("p3_harmonic_hydra", None)
    session = prey8._get_session("p3_harmonic_hydra")
    session["phase"] = "idle"
    
    result = prey8.prey8_yield(
        agent_id="p3_harmonic_hydra",
        summary="test summary",
        delivery_manifest="delivery1",
        test_evidence="test1",
        ai_confidence=85,
        immunization_status="PASSED",
        completion_given="given",
        completion_when="when",
        completion_then="then"
    )
    
    assert result["status"] == "ERROR"
    assert "Cannot Yield" in result["error"]

def test_prey8_yield_invalid_status(mocker: MockerFixture) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    
    # Setup session state
    prey8._sessions.pop("p3_harmonic_hydra", None)
    session = prey8._get_session("p3_harmonic_hydra")
    session["phase"] = "executing"
    
    result = prey8.prey8_yield(
        agent_id="p3_harmonic_hydra",
        summary="test summary",
        delivery_manifest="delivery1",
        test_evidence="test1",
        ai_confidence=85,
        immunization_status="INVALID", # Should be PASSED/FAILED/PARTIAL
        completion_given="given",
        completion_when="when",
        completion_then="then"
    )
    
    assert result["status"] == "GATE_BLOCKED"
    assert "immunization_status must be one of" in result["error"]

def test_prey8_yield_insufficient_confidence(mocker: MockerFixture) -> None:
    mocker.patch("hfo_prey8_mcp_server._write_stigmergy", return_value=1)
    
    # Setup session state
    prey8._sessions.pop("p3_harmonic_hydra", None)
    session = prey8._get_session("p3_harmonic_hydra")
    session["phase"] = "executing"
    session["meadows_level"] = 8 # Requires >= 90 confidence
    session["started_at"] = datetime.now().isoformat()
    session["session_id"] = "test_session_id"
    
    result = prey8.prey8_yield(
        agent_id="p3_harmonic_hydra",
        summary="test summary",
        delivery_manifest="delivery1",
        test_evidence="test1",
        ai_confidence=85, # Too low for level 8
        immunization_status="PASSED",
        completion_given="given",
        completion_when="when",
        completion_then="then"
    )
    
    assert result["status"] == "GATE_BLOCKED"
    assert "Dynamic Constraint Failed" in result["error"]

def test_prey8_fts_search(mocker: MockerFixture) -> None:
    mock_conn = mocker.MagicMock()
    mocker.patch("hfo_prey8_mcp_server._get_conn", return_value=mock_conn)
    
    mock_conn.execute.return_value = [
        (1, "title1", "bluf1", "source1", "port1", "doc_type1", 100)
    ]
    
    results = prey8.prey8_fts_search("query")
    assert len(results) == 1
    assert results[0]["id"] == 1
    assert results[0]["title"] == "title1"

def test_prey8_read_document(mocker: MockerFixture) -> None:
    mock_conn = mocker.MagicMock()
    mocker.patch("hfo_prey8_mcp_server._get_conn", return_value=mock_conn)
    
    mock_conn.execute.return_value.fetchone.return_value = (
        1, "title1", "bluf1", "source1", "port1", "doc_type1", "medallion1",
        "tags1", 100, "hash1", "path1", "content1", "{}"
    )
    
    result = prey8.prey8_read_document(1)
    assert result["id"] == 1
    assert result["title"] == "title1"
    assert result["content"] == "content1"

def test_prey8_query_stigmergy(mocker: MockerFixture) -> None:
    mock_conn = mocker.MagicMock()
    mocker.patch("hfo_prey8_mcp_server._get_conn", return_value=mock_conn)
    
    mock_conn.execute.return_value = [
        (1, "type1", "2020-01-01", "subject1", "source1", '{"data": {"key": "value"}}')
    ]
    
    results = prey8.prey8_query_stigmergy()
    assert len(results) == 1
    assert results[0]["id"] == 1
    assert results[0]["data"]["key"] == "value"

def test_prey8_session_status(mocker: MockerFixture) -> None:
    prey8._sessions.pop("p7_spider_sovereign", None)
    session = prey8._get_session("p7_spider_sovereign")
    session["phase"] = "idle"
    
    result = prey8.prey8_session_status("p7_spider_sovereign")
    assert result["agent_id"] == "p7_spider_sovereign"
    assert result["phase"] == "idle"
    assert "prey8_perceive" in result["available_next_tools"]
