"""
SBE contract proof for plugin_supervisor tile.
Runs npx jest test_plugin_supervisor and asserts >=40 tests pass.
Session: 9c426b31a2097ad2 (nonce 10AB2B) — confirmed 51/51 Jest + 85.85% Stryker.
"""
import re
import subprocess

def test_plugin_supervisor_jest_passes() -> None:
    """Given test_plugin_supervisor.ts in Jest format,
    When npx jest runs it,
    Then >=40 tests pass and 0 fail."""
    result = subprocess.run(
        "npx jest test_plugin_supervisor --no-coverage",
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=r"c:\hfoDev\hfo_gen_90_hot_obsidian_forge\0_bronze\0_projects\HFO_OMEGA_v15",
        timeout=120, shell=True
    )
    output = result.stdout + result.stderr
    # Check pass count
    m = re.search(r"Tests:\s+(\d+) passed", output)
    assert m, f"No pass count found in output:\n{output[-2000:]}"
    passed = int(m.group(1))
    assert passed >= 40, f"Expected >=40 tests to pass, got {passed}. Output:\n{output[-2000:]}"
    # Check no failures in the summary line (console.error messages also say "failed", so only inspect summary)
    assert not re.search(r"Tests:.*\d+ failed", output), \
        f"Test failures in summary:\n{output[-2000:]}"
