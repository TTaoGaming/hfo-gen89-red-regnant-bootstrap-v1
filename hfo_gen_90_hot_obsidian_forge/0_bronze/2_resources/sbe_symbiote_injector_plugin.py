"""
SBE contract proof for symbiote_injector_plugin tile.
Runs npx jest test_symbiote_injector_plugin and asserts >=24 tests pass.
T-OMEGA-SYM-001 through T-OMEGA-SYM-007 covering mounts/unmounts, circular
dependency guard, deferred-mount queue, event-bus wiring, error isolation,
and state-change forwarding.
"""
import re
import subprocess


def test_symbiote_injector_plugin_jest_passes() -> None:
    """Given test_symbiote_injector_plugin.ts with T-OMEGA-SYM-001 through SYM-007,
    When npx jest runs it,
    Then >=24 tests pass and 0 fail."""
    result = subprocess.run(
        "npx jest test_symbiote_injector_plugin --no-coverage",
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=r"c:\hfoDev\hfo_gen_90_hot_obsidian_forge\0_bronze\0_projects\HFO_OMEGA_v15",
        timeout=120, shell=True,
    )
    output = result.stdout + result.stderr
    matches = re.findall(r"Tests:\s+(\d+) passed", output)
    assert matches, f"No pass count found in output:\n{output[-2000:]}"
    passed = int(matches[-1])
    assert passed >= 24, (
        f"Expected >=24 tests to pass, got {passed}.\nOutput:\n{output[-2000:]}"
    )
    assert not re.search(r"Tests:.*\d+ failed", output), \
        f"Test failures in summary:\n{output[-2000:]}"
