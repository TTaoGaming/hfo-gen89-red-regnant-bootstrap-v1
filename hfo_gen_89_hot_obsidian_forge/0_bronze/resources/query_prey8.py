"""
Query SSOT for all PREY8 loop exemplar patterns, stigmergy write patterns,
perceive/yield bookends, and session start/end protocols.
"""
import sqlite3

DB = r'c:\hfoDev\hfo_gen_89_hot_obsidian_forge\2_gold\resources\hfo_gen89_ssot.sqlite'
conn = sqlite3.connect(DB)
cursor = conn.cursor()

queries = {
    "PREY8 DOCS": """
        SELECT id, title, bluf, substr(content, 1, 3000) FROM documents
        WHERE id IN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH 'PREY8 OR "PREY 8" OR perceive OR yield OR bookend')
        AND doc_type IN ('reference','explanation','how_to','doctrine','recipe_card_card','portable_artifact')
        LIMIT 8
    """,
    "PREY8 STIGMERGY": """
        SELECT id, event_type, timestamp, substr(data_json, 1, 2000) FROM stigmergy_events
        WHERE event_type LIKE '%prey8%' OR event_type LIKE '%perceive%' OR event_type LIKE '%yield%'
        ORDER BY timestamp DESC LIMIT 10
    """,
    "SESSION START/END PATTERNS": """
        SELECT id, title, bluf, substr(content, 1, 2000) FROM documents
        WHERE id IN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH '"session start" OR "session end" OR "context read" OR "stigmergy write"')
        AND doc_type IN ('reference','explanation','how_to','doctrine','recipe_card_card')
        LIMIT 8
    """,
    "STIGMERGY WRITE/READ EVENTS": """
        SELECT id, event_type, timestamp, substr(data_json, 1, 1500) FROM stigmergy_events
        WHERE event_type LIKE '%stigmergy%' OR event_type LIKE '%context_read%'
        ORDER BY timestamp LIMIT 10
    """,
    "SSOT STATUS UPDATE PATTERNS": """
        SELECT id, title, bluf, substr(content, 1, 2000) FROM documents
        WHERE id IN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH '"status update" OR "ssot_status" OR "hfo_ssot_status_update"')
        LIMIT 5
    """,
    "RED REGNANT COACHING PROTOCOL": """
        SELECT id, title, bluf, substr(content, 1, 2000) FROM documents
        WHERE id IN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH '"red regnant" AND (bootstrap OR coaching OR protocol)')
        AND doc_type IN ('reference','explanation','doctrine','p4_payload')
        LIMIT 5
    """,
    "LATEST STIGMERGY (last 10)": """
        SELECT id, event_type, timestamp, subject, substr(data_json, 1, 500) FROM stigmergy_events
        ORDER BY timestamp DESC LIMIT 10
    """,
    "STIGMERGY SCHEMA PATTERNS": """
        SELECT DISTINCT event_type, COUNT(*) as cnt FROM stigmergy_events
        WHERE event_type NOT LIKE '%basic%' AND event_type NOT LIKE '%toolbox%' AND event_type != 'unknown' AND event_type != 'system_health'
        GROUP BY event_type ORDER BY cnt DESC LIMIT 25
    """,
}

for label, sql in queries.items():
    print("=" * 100)
    print(f"  {label}")
    print("=" * 100)
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        if not rows:
            print("  (no results)")
        for row in rows:
            for i, val in enumerate(row):
                val_str = str(val)
                if len(val_str) > 2000:
                    val_str = val_str[:2000] + "\n... [TRUNCATED]"
                print(f"  col[{i}]: {val_str}")
            print("  ---")
    except Exception as e:
        print(f"  ERROR: {e}")
    print()

conn.close()
