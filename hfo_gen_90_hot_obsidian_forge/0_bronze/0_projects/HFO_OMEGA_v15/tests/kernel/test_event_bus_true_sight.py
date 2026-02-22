"""
TRUE_SIGHT SBE gate for event_bus audit.
Validates disk reality: src/kernel/event_bus.ts exists, is non-empty, contains no Zod imports.
"""
import os
import re

EVENT_BUS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "src", "kernel", "event_bus.ts"
)
SPEC_PATH = os.path.join(
    os.path.dirname(__file__), "event_bus.spec.ts"
)


def test_src_kernel_event_bus_exists() -> None:
    """SITREP ITEM 1: src/kernel/event_bus.ts must exist on disk."""
    assert os.path.isfile(EVENT_BUS_PATH), f"MISSING: {EVENT_BUS_PATH}"


def test_src_kernel_event_bus_is_non_empty() -> None:
    """SITREP ITEM 2: src/kernel/event_bus.ts must not be empty."""
    size = os.path.getsize(EVENT_BUS_PATH)
    assert size > 0, f"FILE IS EMPTY: {EVENT_BUS_PATH}"


def test_src_kernel_event_bus_no_zod() -> None:
    """SPEC 4 GUARD: src/kernel/event_bus.ts must NOT import from 'zod'."""
    with open(EVENT_BUS_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert not re.search(r"import\s+.*zod", content), "ZOD IMPORT DETECTED in event_bus.ts"


def test_spec_file_exists() -> None:
    """SITREP ITEM 3: tests/kernel/event_bus.spec.ts must exist."""
    assert os.path.isfile(SPEC_PATH), f"MISSING SPEC: {SPEC_PATH}"


def test_spec_enforces_rule5_zombie_guard() -> None:
    """SPEC confirms Rule 5 (zombie listener) guard is present in test suite."""
    with open(SPEC_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert "unsubscribe" in content, "Rule 5 zombie listener test not found in spec"
    assert "GRUDGE GUARD (Rule 5)" in content, "GRUDGE GUARD (Rule 5) label not found in spec"


def test_spec_enforces_spec4_guard() -> None:
    """SPEC 4 guard test must be present in spec file."""
    with open(SPEC_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert "SPEC 4 GUARD" in content, "SPEC 4 GUARD label not found in spec"
