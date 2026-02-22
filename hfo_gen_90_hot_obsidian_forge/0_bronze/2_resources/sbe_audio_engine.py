"""
SBE contract proof for audio_engine_plugin tile.
Runs npx jest test_audio_engine_plugin and asserts >=90 tests pass.
Tile score: 88.89% Stryker (R2, 2026-02-21). 138 killed / 162 total.
T-OMEGA-001 through T-OMEGA-016 covering Cherry MX DSP synthesis,
PAL null-guard, playSound state machine, lifecycle (start/stop/destroy).
"""
import re
import subprocess


def test_audio_engine_plugin_jest_passes() -> None:
    """Given test_audio_engine_plugin.ts with T-OMEGA-001 through T-OMEGA-016,
    When npx jest runs it,
    Then >=90 tests pass and 0 fail."""
    result = subprocess.run(
        "npx jest test_audio_engine_plugin --no-coverage",
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=r"c:\hfoDev\hfo_gen_90_hot_obsidian_forge\0_bronze\0_projects\HFO_OMEGA_v15",
        timeout=120, shell=True,
    )
    output = result.stdout + result.stderr
    # Use the last "Tests: N passed" line (final summary, not sandbox mid-run noise)
    matches = re.findall(r"Tests:\s+(\d+) passed", output)
    assert matches, f"No pass count found in output:\n{output[-2000:]}"
    passed = int(matches[-1])
    assert passed >= 90, (
        f"Expected >=90 tests to pass, got {passed}.\nOutput:\n{output[-2000:]}"
    )
    assert not re.search(r"Tests:.*\d+ failed", output), \
        f"Test failures in summary:\n{output[-2000:]}"
