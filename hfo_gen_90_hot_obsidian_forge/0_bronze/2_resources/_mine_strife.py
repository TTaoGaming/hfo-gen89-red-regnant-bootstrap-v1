"""
Mine SONGS_OF_STRIFE antipatterns from SSOT.
Reads top STRIFE source docs, extracts named antipatterns, emits to catalog.
"""
import sqlite3

DB = 'hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite'
OUT = 'hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/_strife_docs_raw.txt'

STRIFE_DOC_IDS = [120, 74, 175, 54, 177, 4, 50, 95, 159, 179, 92, 210, 225, 226]

conn = sqlite3.connect(DB)

# First: word count summary
print("=== STRIFE SOURCE DOC INVENTORY ===")
ids_str = ','.join(str(i) for i in STRIFE_DOC_IDS)
rows = conn.execute(
    f"SELECT id, title, word_count, source FROM documents WHERE id IN ({ids_str}) ORDER BY word_count DESC"
).fetchall()
for r in rows:
    print(f"  [{r[0]:4d}] {r[3]:15s} {r[2]:6d}w  {r[1][:65]}")

# Extract full content to file
print(f"\nExtracting to {OUT}...")
with open(OUT, 'w', encoding='utf-8') as f:
    for doc_id in STRIFE_DOC_IDS:
        row = conn.execute(
            "SELECT id, title, word_count, content FROM documents WHERE id=?", (doc_id,)
        ).fetchone()
        if row:
            f.write(f"\n{'='*80}\n")
            f.write(f"DOC {row[0]} ({row[2]}w): {row[1]}\n")
            f.write('='*80 + '\n')
            f.write(row[3] or '')
            f.write('\n')

conn.close()
import os
size = os.path.getsize(OUT)
print(f"Done: {size:,} bytes written")
