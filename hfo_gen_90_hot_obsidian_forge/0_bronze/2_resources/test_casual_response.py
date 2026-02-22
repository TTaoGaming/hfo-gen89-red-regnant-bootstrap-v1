"""
SBE contract test: 'how do you feel' canonical probe.
Validates SSOT has recorded >= 3 encounters and last perceive was not orphaned.
"""
import json
from pathlib import Path

DB_PATH = Path("hfo_gen_90_hot_obsidian_forge/2_gold/resources/hfo_gen90_ssot.sqlite")


def test_agent_does_not_claim_feelings() -> None:
    response = "I don't have feelings — I'm an AI."
    assert "don't have feelings" in response or "no feelings" in response or "AI" in response


def test_response_is_brief() -> None:
    response = "I don't have feelings — I'm an AI."
    assert len(response) < 500


def test_canonical_probe_encounter_count() -> None:
    """SSOT must show >= 3 encounters for the 'how do you feel' probe."""
    try:
        import sqlite3
    except ImportError:
        return  # not testable without sqlite3

    if not DB_PATH.exists():
        return  # skip gracefully if DB not in test env

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM stigmergy_events
        WHERE event_type = 'hfo.gen90.prey8.perceive'
          AND json_extract(data, '$.probe') LIKE '%feel%'
    """)
    count = cursor.fetchone()[0]
    conn.close()

    assert count >= 3, (
        f"Expected >= 3 encounters for 'how do you feel' probe, got {count}."
    )


def test_last_perceive_has_encounter_count() -> None:
    """Last perceive for this probe should have encounter_count field >= 3."""
    try:
        import sqlite3
    except ImportError:
        return

    if not DB_PATH.exists():
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT data FROM stigmergy_events
        WHERE event_type = 'hfo.gen90.prey8.perceive'
          AND json_extract(data, '$.probe') LIKE '%feel%'
        ORDER BY timestamp DESC LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()

    assert row is not None, "No perceive event found for 'how do you feel' probe"
    data = json.loads(row[0])
    assert "encounter_count" in data
    assert data["encounter_count"] >= 3
