"""Extract raw content from Singer docs 267, 270, 271, 272 to file."""
import sqlite3

DB = 'hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite'
OUT = 'hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/_singer_docs_raw.txt'
conn = sqlite3.connect(DB)

with open(OUT, 'w', encoding='utf-8') as f:
    for doc_id in [267, 270, 271, 272]:
        row = conn.execute("SELECT id, title, content FROM documents WHERE id=?", (doc_id,)).fetchone()
        if row:
            f.write(f"\n{'='*80}\n")
            f.write(f"DOC {row[0]}: {row[1]}\n")
            f.write('='*80 + '\n')
            f.write(row[2] or '')
            f.write('\n')

conn.close()
print("Done")
