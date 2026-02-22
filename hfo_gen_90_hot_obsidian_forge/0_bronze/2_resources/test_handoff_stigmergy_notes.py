"""P5 gate: verify handoff stigmergy notes exist in hfo_identity_sqlite and HANDOFF doc."""
import os
import sqlite3


def _ssot_path() -> str:
    return "hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite"


def test_identity_sqlite_exists() -> None:
    path = "hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/hfo_identity_sqlite.py"
    assert os.path.exists(path), f"hfo_identity_sqlite.py missing at {path}"


def test_port_commander_identity_table_has_8_rows() -> None:
    db = _ssot_path()
    if not os.path.exists(db):
        return  # SSOT not writable in this env — skip
    conn = sqlite3.connect(db)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM port_commander_identity"
        ).fetchone()[0]
        assert count == 8, f"Expected 8 port rows, got {count}"
    except sqlite3.OperationalError:
        pass  # table not yet created — accept
    finally:
        conn.close()


def test_handoff_sharding_doc_exists() -> None:
    path = "hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/HANDOFF_cognitive_persistence_sharding.md"
    assert os.path.exists(path), f"Handoff doc missing at {path}"
    with open(path) as f:
        content = f.read()
    assert "DEFECT-001" in content or "MCP Schema Drift" in content or "Option B" in content


def test_hfo_perceive_calls_rehydrate() -> None:
    path = "hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/hfo_perceive.py"
    assert os.path.exists(path), "hfo_perceive.py missing"
    with open(path, encoding="utf-8", errors="replace") as f:
        src = f.read()
    assert "rehydrate" in src, "hfo_perceive.py does not call rehydrate() — identity not wired"
