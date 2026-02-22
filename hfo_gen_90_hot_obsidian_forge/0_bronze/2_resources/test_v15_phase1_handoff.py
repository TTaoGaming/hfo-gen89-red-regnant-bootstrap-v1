"""
SBE contract test for v15_phase1_handoff_2026-02-21.md
Given Phase 1 tile hardening complete / When handoff doc written / Then doc exists with correct content
"""
import pathlib

DOC = pathlib.Path(__file__).parent / "v15_phase1_handoff_2026-02-21.md"


def test_handoff_doc_exists() -> None:
    assert DOC.exists(), f"Handoff doc missing: {DOC}"


def test_handoff_doc_has_stryker_scores() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "95.08%" in text, "kalman_filter Stryker score missing"
    assert "84.31%" in text, "event_bus Stryker score missing"
    assert "90.18%" in text, "combined score missing"


def test_handoff_doc_has_git_warning() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "git add" in text, "git commit instruction missing"
    assert "stryker.config.json" in text, "stryker.config.json mention missing"


def test_handoff_doc_has_issue_table() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "18066" in text or "DEAD-LETTER" in text, "issue row reference missing"
    assert "equivalent mutant" in text.lower() or "equivalent_mutant" in text, "equivalent mutant note missing"


def test_handoff_doc_has_remaining_tiles() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "gesture_fsm_plugin" in text, "remaining tile gesture_fsm_plugin missing"
    assert "audio_engine_plugin" in text, "remaining tile audio_engine_plugin missing"
