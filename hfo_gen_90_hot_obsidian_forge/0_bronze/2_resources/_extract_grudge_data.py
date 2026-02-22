"""Extract Book of Blood docs and write to file - UTF-8 safe."""
import sqlite3, re, sys

conn = sqlite3.connect('hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite')

out = open('hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/_grudge_data.txt', 'w', encoding='utf-8')

def w(s):
    out.write(s + '\n')

# Doc 398 - FESTERING_ANGER Book of Blood reference
row = conn.execute("SELECT title, content FROM documents WHERE id=398").fetchone()
if row:
    w("=" * 80)
    w(f"DOC 398: {row[0]}")
    w("=" * 80)
    w(row[1])

w("\n" + "=" * 80)

# Doc 687 - BOOK_OF_BLOOD_GRUDGES.md
row = conn.execute("SELECT title, content FROM documents WHERE id=687").fetchone()
if row:
    w("=" * 80)
    w(f"DOC 687: {row[0]}")
    w("=" * 80)
    w(row[1])

# Doc 7673 - book_of_blood_grudges main file
row = conn.execute("SELECT title, source_path, content FROM documents WHERE id=7673").fetchone()
if row:
    w("=" * 80)
    w(f"DOC 7673: {row[0]} | path: {row[1]}")
    w("=" * 80)
    w(row[2])

# Doc 7672 - README
row = conn.execute("SELECT title, source_path, content FROM documents WHERE id=7672").fetchone()
if row:
    w("=" * 80)
    w(f"DOC 7672: {row[0]} | path: {row[1]}")
    w("=" * 80)
    w(row[2])

# Doc 7934 - legacy bronze report
row = conn.execute("SELECT title, source_path, content FROM documents WHERE id=7934").fetchone()
if row:
    w("=" * 80)
    w(f"DOC 7934: {row[0]} | path: {row[1]}")
    w("=" * 80)
    w(row[2])

# Braided thread - extract GRUDGE section safely
row = conn.execute("SELECT content FROM documents WHERE id=7855").fetchone()
if row:
    content = row[0]
    chunks = re.split(r'(?=id:\s+"GRUDGE_)', content)
    w("\n" + "=" * 80)
    w(f"BRAIDED THREAD - {len(chunks)-1} GRUDGE blocks")
    w("=" * 80)
    for chunk in chunks[1:]:
        lines = chunk.split('\n')[:20]
        w('\n'.join(lines) + '\n---')

# Also search for docs with "pain point" or "STRIFE" token catalog content
results = conn.execute(
    "SELECT id, title, word_count FROM documents WHERE id IN "
    "(SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?) ORDER BY word_count DESC LIMIT 10",
    ('"pain point" OR "pain_point" OR "death spiral"',)
).fetchall()
w("\n" + "=" * 80)
w("Pain point / death spiral docs")
w("=" * 80)
for r in results:
    w(f"  [{r[0]:4d}] {r[2]:6d}w  {r[1][:70] if r[1] else 'N/A'}")

# Death spiral specifically
row = conn.execute(
    "SELECT id, title, content FROM documents WHERE id IN "
    "(SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?) ORDER BY word_count DESC LIMIT 3",
    ('"hallucination" "death spiral"',)
).fetchone()
if row:
    w(f"\nDeath spiral doc [{row[0]}]: {row[1]}")
    # Print lines mentioning death spiral
    for line in row[2].split('\n'):
        if 'death spiral' in line.lower() or 'hallucin' in line.lower():
            w(f"  {line[:120]}")

out.close()
conn.close()

import os
print(f"Written: {os.path.getsize('hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/_grudge_data.txt')} bytes")
