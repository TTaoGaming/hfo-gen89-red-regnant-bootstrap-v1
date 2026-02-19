import sqlite3, json

DB = r'c:\hfoDev\hfo_gen_89_hot_obsidian_forge\2_gold\resources\hfo_gen89_ssot.sqlite'
conn = sqlite3.connect(DB)
cursor = conn.cursor()

# 1. Full blessed pointers JSON
print("=" * 100)
print("BLESSED POINTERS (full content)")
print("=" * 100)
cursor.execute("SELECT content FROM documents WHERE source_path = 'hfo_pointers_blessed.json'")
row = cursor.fetchone()
if row: print(row[0])

# 2. Full Gen88 AGENTS.md
print("\n" + "=" * 100)
print("GEN88 AGENTS.MD (full content)")
print("=" * 100)
cursor.execute("SELECT content FROM documents WHERE source_path = 'AGENTS.md'")
row = cursor.fetchone()
if row: print(row[0])

# 3. Contracts JSON
print("\n" + "=" * 100)
print("LEGENDARY COMMANDERS INVARIANTS (full)")
print("=" * 100)
cursor.execute("SELECT content FROM documents WHERE source_path LIKE 'contracts/%'")
row = cursor.fetchone()
if row: print(row[0])

# 4. FTS search for .env / env config / dotenv patterns
print("\n" + "=" * 100)
print("FTS: env dotenv secret config")
print("=" * 100)
cursor.execute("""SELECT id, title, substr(content, 1, 2000) FROM documents
WHERE id IN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH 'dotenv OR HFO_SECRET OR HFO_ROOT')
LIMIT 5""")
for row in cursor.fetchall():
    print(f"\n[{row[0]}] {row[1]}")
    print(row[2][:1500])
    print("---")

# 5. FTS for precommit / hook / lint
print("\n" + "=" * 100)
print("FTS: precommit hook validation")
print("=" * 100)
cursor.execute("""SELECT id, title, substr(content, 1, 2000) FROM documents
WHERE id IN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH '"pre-commit" OR precommit OR "governance gate" OR preflight')
AND doc_type IN ('reference','explanation','how_to','doctrine','config_markdown','config','recipe_card_card')
LIMIT 10""")
for row in cursor.fetchall():
    print(f"\n[{row[0]}] {row[1]}")
    print(row[2][:800])
    print("---")

conn.close()
