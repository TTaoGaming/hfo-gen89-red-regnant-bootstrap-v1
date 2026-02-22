"""pytest: Verify obsidian_blackboard and spells tables exist in SSOT with expected data."""
import sqlite3
import pytest

DB = 'hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite'


@pytest.fixture(scope='module')
def conn():
    c = sqlite3.connect(DB)
    yield c
    c.close()


def test_obsidian_blackboard_table_exists(conn):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='obsidian_blackboard'"
    ).fetchone()
    assert row is not None, "obsidian_blackboard table missing"


def test_obsidian_blackboard_has_8_tiles(conn):
    count = conn.execute("SELECT COUNT(*) FROM obsidian_blackboard").fetchone()[0]
    assert count == 8, f"Expected 8 tiles, got {count}"


def test_event_bus_tile_active(conn):
    row = conn.execute(
        "SELECT status, assignee FROM obsidian_blackboard WHERE tile_key='event_bus'"
    ).fetchone()
    assert row is not None, "event_bus tile missing"
    assert row[0] in ('claimed', 'in_progress', 'hardening'), f"Expected active status, got {row[0]}"
    assert row[1] == 'p7_spider_sovereign', f"Expected p7_spider_sovereign, got {row[1]}"


def test_spells_table_exists(conn):
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='spells'"
    ).fetchone()
    assert row is not None, "spells table missing"


def test_spells_has_3_entries(conn):
    count = conn.execute("SELECT COUNT(*) FROM spells").fetchone()[0]
    assert count == 3, f"Expected 3 spells, got {count}"


def test_genesis_spell_targets_all_tiles(conn):
    row = conn.execute(
        "SELECT status, target_tile FROM spells WHERE spell_key='genesis_stryker_gate'"
    ).fetchone()
    assert row is not None, "genesis_stryker_gate spell missing"
    assert row[0] == 'active'
    assert row[1] is None, "genesis spell should target ALL tiles (NULL)"


def test_spells_link_to_grimoire(conn):
    """All spells with non-null grimoire_id reference a real hfo_grimoire row."""
    for row in conn.execute(
        "SELECT spell_key, grimoire_id FROM spells WHERE grimoire_id IS NOT NULL"
    ):
        exists = conn.execute(
            "SELECT id FROM hfo_grimoire WHERE id=?", (row[1],)
        ).fetchone()
        assert exists, f"Spell {row[0]} references missing grimoire_id {row[1]}"


def test_tiles_have_priority_ordering(conn):
    rows = conn.execute(
        "SELECT tile_key, priority FROM obsidian_blackboard ORDER BY priority"
    ).fetchall()
    priorities = [r[1] for r in rows]
    assert priorities == sorted(priorities), "Tile priorities are not monotonically increasing"
    assert rows[0][0] == 'event_bus', "event_bus should be priority 1 (foundation tile)"
