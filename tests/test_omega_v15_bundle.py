"""Validation test: verifies both Omega v15 LLM context bundle files exist and contain required content.
Session: b9481b23a1930f60 | PREY8 nonce: E6496F | 2026-02-21"""
import os
import re

BUNDLE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "hfo_gen_90_hot_obsidian_forge", "0_bronze", "2_resources"
)

FILE1 = os.path.join(BUNDLE_DIR, "omega_v15_context_bundle_state_of_union.md")
FILE2 = os.path.join(BUNDLE_DIR, "omega_v15_rewrite_charter.md")


def test_file1_exists():
    assert os.path.isfile(FILE1), f"File 1 missing: {FILE1}"


def test_file1_has_three_critical_bugs():
    content = open(FILE1, encoding="utf-8").read()
    assert "Bug 1" in content
    assert "Bug 2" in content
    assert "Bug 3" in content


def test_file1_has_six_antipatterns():
    content = open(FILE1, encoding="utf-8").read()
    for i in range(1, 7):
        assert f"AP-{i}" in content, f"Missing AP-{i}"


def test_file1_has_six_gherkin_specs():
    content = open(FILE1, encoding="utf-8").read()
    for i in range(1, 7):
        assert f"SPEC {i}" in content, f"Missing SPEC {i}"


def test_file1_has_v14_grudge016():
    content = open(FILE1, encoding="utf-8").read()
    assert "GRUDGE_016" in content
    assert "Green Lie" in content or "100%" in content


def test_file1_has_gen90_forge_section():
    content = open(FILE1, encoding="utf-8").read()
    assert "HFO Gen90" in content
    assert "HFO_OMEGA_v15" in content


def test_file2_exists():
    assert os.path.isfile(FILE2), f"File 2 missing: {FILE2}"


def test_file2_has_definition_of_done():
    content = open(FILE2, encoding="utf-8").read()
    assert "Definition of Done" in content or "definition of done" in content.lower()


def test_file2_has_banned_patterns():
    content = open(FILE2, encoding="utf-8").read()
    assert "BANNED" in content or "banned" in content.lower() or "NEVER" in content


def test_file2_has_atdd_enforcement():
    content = open(FILE2, encoding="utf-8").read()
    assert "ATDD" in content or "RED" in content
