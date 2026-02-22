"""Extract the full GRUDGE registry from the SSOT."""
import sqlite3, re

conn = sqlite3.connect('hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite')

# 1. Try to find BOOK_OF_BLOOD as an ingested doc
results = conn.execute(
    "SELECT id, title, word_count, source_path FROM documents WHERE id IN "
    "(SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?) ORDER BY word_count DESC LIMIT 10",
    ('BOOK_OF_BLOOD OR "book of blood"',)
).fetchall()
print("=== BOOK_OF_BLOOD docs ===")
for r in results:
    print(f"  [{r[0]:4d}] {r[2]:6d}w  path:{r[3]}  title:{r[1][:60] if r[1] else 'N/A'}")

# 2. Search FTS for all numbered GRUDGE entries
results2 = conn.execute(
    "SELECT id, title, word_count FROM documents WHERE id IN "
    "(SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?) ORDER BY word_count DESC LIMIT 20",
    ('GRUDGE_002 OR GRUDGE_004 OR GRUDGE_005 OR GRUDGE_006 OR GRUDGE_007 OR GRUDGE_008 OR GRUDGE_009',)
).fetchall()
print("\n=== Docs with GRUDGE_002-009 ===")
for r in results2:
    print(f"  [{r[0]:4d}] {r[2]:6d}w  {r[1][:70] if r[1] else 'N/A'}")

# 3. Find all GRUDGE_NNN patterns anywhere in SSOT
results3 = conn.execute(
    "SELECT id, title, word_count FROM documents WHERE id IN "
    "(SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?) ORDER BY word_count DESC LIMIT 20",
    ('GRUDGE_011 OR GRUDGE_012 OR GRUDGE_013 OR GRUDGE_014 OR GRUDGE_018 OR GRUDGE_020 OR GRUDGE_021',)
).fetchall()
print("\n=== Docs with GRUDGE_011-021 ===")
for r in results3:
    print(f"  [{r[0]:4d}] {r[2]:6d}w  {r[1][:70] if r[1] else 'N/A'}")

# 4. Check braided mission thread (doc 7855) for GRUDGE table
row = conn.execute("SELECT content FROM documents WHERE id=7855").fetchone()
if row:
    content = row[0]
    grudge_lines = [l for l in content.split('\n') if re.search(r'GRUDGE_\d+', l) or 'BOOK_OF_BLOOD' in l or 'antipattern' in l.lower()]
    print(f"\n=== Braided thread GRUDGE lines ({len(grudge_lines)} total) ===")
    for l in grudge_lines[:60]:
        print(f"  {l[:110]}")

conn.close()
