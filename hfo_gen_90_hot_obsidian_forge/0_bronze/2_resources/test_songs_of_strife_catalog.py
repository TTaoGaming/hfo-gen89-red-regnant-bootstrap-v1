"""Tests for SONGS_OF_STRIFE_ANTIPATTERN_CATALOG.md — 30 STRIFE tokens across 4 registries."""
import os
import re
import pytest

STRIFE_PATH = "hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/SONGS_OF_STRIFE_ANTIPATTERN_CATALOG.md"


@pytest.fixture
def strife_content() -> str:
    assert os.path.exists(STRIFE_PATH), f"STRIFE catalog missing: {STRIFE_PATH}"
    with open(STRIFE_PATH, encoding="utf-8") as f:
        return f.read()


# ── File existence ────────────────────────────────────────────────────────────

def test_strife_catalog_exists() -> None:
    assert os.path.exists(STRIFE_PATH)


# ── BREACH entries (most severe class) ───────────────────────────────────────

def test_breach_001_lobotomy_present(strife_content: str) -> None:
    """BREACH_001 THE LOBOTOMY must be present with cryptographic anchor."""
    assert "BREACH_001" in strife_content
    assert "THE LOBOTOMY" in strife_content
    assert "fc4f9818" in strife_content, "BREACH_001 must have SHA-256 anchor"


def test_breach_critical_signals_present(strife_content: str) -> None:
    """All 8 Critical Signals CS-1 through CS-8 must be present."""
    for i in range(1, 9):
        assert f"CS-{i}" in strife_content, f"Missing Critical Signal CS-{i}"


def test_breach_red_truth_signal(strife_content: str) -> None:
    """CS-8 RED_TRUTH must be present — the core anti-deception invariant."""
    assert "RED_TRUTH" in strife_content
    assert "verifiable failure" in strife_content.lower() or "failure is a signal" in strife_content


# ── Gen88 v4 Book of Blood GRUDGEs ───────────────────────────────────────────

def test_all_8_book_of_blood_grudges_present(strife_content: str) -> None:
    """All 8 GRUDGE_001-008 from Gen88 v4 YAML must be present."""
    for i in range(1, 9):
        token = f"GRUDGE_{i:03d}"
        assert token in strife_content, f"Missing Book of Blood grudge: {token}"


def test_grudge_001_coordinate_amnesia(strife_content: str) -> None:
    assert "GRUDGE_001" in strife_content
    assert "Coordinate Amnesia" in strife_content


def test_grudge_002_green_lie_theater(strife_content: str) -> None:
    assert "GRUDGE_002" in strife_content
    assert "Green Lie Theater" in strife_content


def test_grudge_003_pointer_drift(strife_content: str) -> None:
    assert "GRUDGE_003" in strife_content
    assert "Pointer Drift" in strife_content


def test_grudge_004_oom_amnesia(strife_content: str) -> None:
    assert "GRUDGE_004" in strife_content
    assert "OOM Amnesia" in strife_content


def test_grudge_005_fsm_or_gate(strife_content: str) -> None:
    assert "GRUDGE_005" in strife_content
    assert "FSM OR" in strife_content or "OR-gate" in strife_content


def test_grudge_006_ai_slop_promotion(strife_content: str) -> None:
    assert "GRUDGE_006" in strife_content
    assert "Slop Promotion" in strife_content or "AI Slop" in strife_content


def test_grudge_007_particle_emitter(strife_content: str) -> None:
    assert "GRUDGE_007" in strife_content
    assert "Particle Emitter" in strife_content or "Type Confusion" in strife_content


def test_grudge_008_schema_drift(strife_content: str) -> None:
    assert "GRUDGE_008" in strife_content
    assert "Schema Drift" in strife_content


# ── SDD Stack GRUDGEs ─────────────────────────────────────────────────────────

def test_sdd_stack_grudges_present(strife_content: str) -> None:
    """Key SDD Stack extended GRUDGEs must be present."""
    extended = ["GRUDGE_010", "GRUDGE_015", "GRUDGE_016", "GRUDGE_017",
                "GRUDGE_019", "GRUDGE_022", "GRUDGE_023", "GRUDGE_033"]
    for token in extended:
        assert token in strife_content, f"Missing SDD Stack GRUDGE: {token}"


def test_grudge_016_test_theater_most_cited(strife_content: str) -> None:
    """GRUDGE_016 must document its 7× citation frequency (most-cited grudge)."""
    assert "GRUDGE_016" in strife_content
    assert "Test Theater" in strife_content
    assert "7" in strife_content  # mentioned 7x


def test_grudge_022_reward_hacking(strife_content: str) -> None:
    """GRUDGE_022 must cover reward hacking — agent controls both Q and A."""
    assert "GRUDGE_022" in strife_content
    assert "Reward Hacking" in strife_content
    assert "question" in strife_content.lower() or "answer" in strife_content.lower()


def test_grudge_033_mode_collapse(strife_content: str) -> None:
    """GRUDGE_033 must cover Mode Collapse Under Context Pressure."""
    assert "GRUDGE_033" in strife_content
    assert "Mode Collapse" in strife_content
    assert "mem_47733" in strife_content or "TOTAL_MODE_COLLAPSE" in strife_content


# ── E50 Heuristics H01-H12 ───────────────────────────────────────────────────

def test_all_12_heuristics_present(strife_content: str) -> None:
    """All 12 E50 heuristics H01-H12 must have token entries."""
    for i in range(1, 13):
        token = f"H{i:02d}"
        assert token in strife_content, f"Missing E50 heuristic token: {token}"


def test_h01_completion_bias(strife_content: str) -> None:
    assert "H01" in strife_content
    assert "Completion Bias" in strife_content


def test_h03_prose_over_proof(strife_content: str) -> None:
    assert "H03" in strife_content
    assert "Prose Over Proof" in strife_content


def test_h07_happy_path_only(strife_content: str) -> None:
    assert "H07" in strife_content
    assert "Happy Path" in strife_content


def test_h10_ssot_amnesia(strife_content: str) -> None:
    assert "H10" in strife_content
    assert "SSOT Amnesia" in strife_content


def test_h11_gate_bypass(strife_content: str) -> None:
    assert "H11" in strife_content
    assert "Gate Bypass" in strife_content


def test_complexity_cliff_diagram(strife_content: str) -> None:
    """Complexity Cliff ASCII diagram must be present."""
    assert "Complexity Cliff" in strife_content
    assert "Heuristics" in strife_content
    assert "HELP here" in strife_content or "HARM here" in strife_content


def test_minimum_viable_completion_meta_pattern(strife_content: str) -> None:
    """MVC meta-pattern must be documented."""
    assert "Minimum Viable Completion" in strife_content or "MVC" in strife_content


# ── MITRE ATT&CK taxonomy ─────────────────────────────────────────────────────

def test_8_mitre_tactics_present(strife_content: str) -> None:
    """All 8 TA-BOB tactics must be present."""
    for i in range(1, 9):
        tactic = f"TA-BOB-{i:02d}"
        assert tactic in strife_content, f"Missing MITRE tactic: {tactic}"


def test_reward_inversion_tactic(strife_content: str) -> None:
    """TA-BOB-03 Reward Inversion must be present."""
    assert "Reward Inversion" in strife_content


def test_theater_production_tactic(strife_content: str) -> None:
    """TA-BOB-06 Theater Production must be present."""
    assert "Theater Production" in strife_content


# ── Catalog structure ─────────────────────────────────────────────────────────

def test_total_strife_token_count_30(strife_content: str) -> None:
    """Catalog must document 30 total STRIFE tokens."""
    assert "30" in strife_content
    assert "STRIFE token" in strife_content.lower() or "strife tokens" in strife_content.lower()


def test_festering_anger_formula(strife_content: str) -> None:
    """FESTERING_ANGER stacking formula must be present."""
    assert "FESTERING_ANGER" in strife_content
    assert "Probe Power" in strife_content or "STRIFE_POWER" in strife_content
    assert "Grudges" in strife_content


def test_grudge_cross_reference_table(strife_content: str) -> None:
    """Cross-reference table linking STRIFE tokens to countermeasures must exist."""
    assert "Countermeasure" in strife_content or "countermeasure" in strife_content
    # Table must cross-ref BREACH_001 and multiple GRUDGEs
    assert "BREACH_001" in strife_content
    assert "BFT quorum" in strife_content or "append-only" in strife_content


def test_source_docs_attributed(strife_content: str) -> None:
    """Key source docs must be attributed."""
    assert "177" in strife_content  # E50 heuristics
    assert "120" in strife_content  # SDD Stack
    assert "E50" in strife_content  # doc ID


def test_schema_id_present(strife_content: str) -> None:
    """Schema ID must mark this as a valid HFO bronze document."""
    assert "hfo.gen90.songs_of_strife.v1" in strife_content


def test_port_p4_tagged(strife_content: str) -> None:
    """Document must be tagged to P4 DISRUPT (Red Regnant)."""
    assert "P4" in strife_content
    assert "Red Regnant" in strife_content or "DISRUPT" in strife_content
