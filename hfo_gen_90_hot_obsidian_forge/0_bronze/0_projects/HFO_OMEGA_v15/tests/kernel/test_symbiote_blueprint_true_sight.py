"""
TRUE_SIGHT SBE gate: symbiote_injector_blueprint.md verification.
Asserts all 4 Synthetic Pointer Failure Mode sections exist and contain real code.
"""
import os
import re

BLUEPRINT_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",   # tests/
    "..",   # HFO_OMEGA_v15/
    "..",   # 0_projects/
    "..",   # 0_bronze/
    "2_resources",
    "symbiote_injector_blueprint.md",
)


def _content() -> str:
    with open(BLUEPRINT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def test_blueprint_file_exists() -> None:
    """Blueprint must exist on disk."""
    assert os.path.isfile(BLUEPRINT_PATH), f"MISSING: {BLUEPRINT_PATH}"


def test_blueprint_pointer_capture_has_code() -> None:
    """Failure Mode 1: Pointer Capture section must contain a JS code block."""
    content = _content()
    assert "setPointerCapture" in content, "No setPointerCapture implementation found"
    assert "Element.prototype" in content, "No Element.prototype monkey-patch found"


def test_blueprint_event_cascade_has_code() -> None:
    """Failure Mode 2: Event Cascade section must contain boundary dispatch code."""
    content = _content()
    assert "pointerenter" in content, "No pointerenter boundary cascade found"
    assert "pointerleave" in content, "No pointerleave boundary cascade found"
    assert "dispatchSyntheticMove" in content, "No dispatchSyntheticMove function found"


def test_blueprint_trust_focus_has_code() -> None:
    """Failure Mode 3: Trust/Focus section must contain isTrusted spoof and focus call."""
    content = _content()
    assert "isTrusted" in content, "No isTrusted spoof found"
    assert "target.focus" in content, "No focus() call found"
    assert "dispatchSyntheticDown" in content, "No dispatchSyntheticDown function found"


def test_blueprint_pen_mode_has_code() -> None:
    """Failure Mode 4: Pen Mode section must contain createPointerEvent factory with pointerType pen."""
    content = _content()
    assert "createPointerEvent" in content, "No createPointerEvent factory found"
    assert "pointerType: 'pen'" in content, "No pointerType: 'pen' hardcode found"
    assert "pressure" in content, "No pressure field found"


def test_blueprint_not_vague_bullet_points() -> None:
    """Blueprint must contain actual code blocks, not just prose."""
    content = _content()
    code_blocks = re.findall(r"```(?:javascript|typescript|js|ts)", content)
    assert len(code_blocks) >= 4, (
        f"Expected at least 4 code blocks, found {len(code_blocks)} — blueprint may be vague prose"
    )
