"""
Query Gen88 SSOT for all cold-start exemplar patterns:
- blessed pointers (PAL system)
- .env / env config
- pre-commit hooks
- governance gates
- git setup patterns
- hfo_pointers_blessed.json
- braided mission thread
- config files
"""
import sqlite3, json, textwrap

DB = r'c:\hfoDev\hfo_gen_89_hot_obsidian_forge\2_gold\resources\hfo_gen89_ssot.sqlite'
conn = sqlite3.connect(DB)
cursor = conn.cursor()

queries = {
    "BLESSED POINTERS JSON": """
        SELECT content FROM documents WHERE source_path = 'hfo_pointers_blessed.json'
    """,
    "AGENTS.MD (Gen88)": """
        SELECT content FROM documents WHERE source_path = 'AGENTS.md'
    """,
    "BRAIDED MISSION THREAD": """
        SELECT substr(content, 1, 5000) FROM documents WHERE source_path LIKE 'braided_mission_thread%'
    """,
    "GOVERNANCE GATE DOCS": """
        SELECT id, title, bluf, substr(content, 1, 2000) FROM documents
        WHERE title LIKE '%governance%' OR title LIKE '%gate%' OR title LIKE '%precommit%' OR title LIKE '%pre-commit%'
        LIMIT 10
    """,
    "POINTER/PAL DOCS": """
        SELECT id, title, bluf, substr(content, 1, 3000) FROM documents
        WHERE (title LIKE '%pointer%' OR content LIKE '%hfo_pointers%' OR title LIKE '%PAL%' OR title LIKE '%path abstraction%')
        AND doc_type IN ('reference','explanation','how_to','doctrine','config_markdown','config_json','config')
        LIMIT 10
    """,
    "ENV/SECRET DOCS": """
        SELECT id, title, bluf, substr(content, 1, 2000) FROM documents
        WHERE (title LIKE '%.env%' OR content LIKE '%HFO_SECRET%' OR content LIKE '%HFO_ROOT%' OR content LIKE '%dotenv%')
        AND doc_type IN ('reference','explanation','how_to','doctrine','config_markdown','config')
        LIMIT 10
    """,
    "GIT SETUP DOCS": """
        SELECT id, title, bluf, substr(content, 1, 2000) FROM documents
        WHERE (title LIKE '%gitignore%' OR title LIKE '%git setup%' OR content LIKE '%pre-commit%hook%')
        AND doc_type IN ('reference','explanation','how_to','doctrine','config_markdown')
        LIMIT 10
    """,
    "COLD START DOCS": """
        SELECT id, title, bluf, substr(content, 1, 2000) FROM documents
        WHERE (title LIKE '%cold start%' OR title LIKE '%bootstrap%' OR title LIKE '%capsule%' OR bluf LIKE '%cold start%')
        LIMIT 10
    """,
    "CONFIG SOURCE DOCS (all 5)": """
        SELECT id, title, source_path, doc_type, word_count, bluf FROM documents WHERE source = 'config'
    """,
    "CONTRACTS": """
        SELECT id, title, substr(content, 1, 3000) FROM documents WHERE source_path LIKE 'contracts/%'
    """,
    "STIGMERGY - GENESIS + BOOTSTRAP": """
        SELECT id, event_type, timestamp, substr(data_json, 1, 2000) FROM stigmergy_events
        WHERE event_type LIKE '%genesis%' OR event_type LIKE '%bootstrap%' OR event_type LIKE '%cold%' OR event_type LIKE '%FIRST_SCREAM%'
        ORDER BY timestamp LIMIT 10
    """,
    "FTS: pointer resolve": """
        SELECT id, title, bluf FROM documents
        WHERE id IN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH 'pointer resolve blessed')
        LIMIT 10
    """,
    "FTS: precommit hook lint gate": """
        SELECT id, title, bluf FROM documents
        WHERE id IN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH 'precommit OR pre-commit OR hook OR lint gate')
        LIMIT 10
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
                if len(val_str) > 4000:
                    val_str = val_str[:4000] + "\n... [TRUNCATED]"
                print(f"  col[{i}]: {val_str}")
            print("  ---")
    except Exception as e:
        print(f"  ERROR: {e}")
    print()

conn.close()
