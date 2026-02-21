import sqlite3, sys
sys.path.insert(0, r'C:\hfoDev\hfo_gen_89_hot_obsidian_forge\0_bronze\resources')
import sqlite_vec

DB = r'C:\hfoDev\hfo_gen_89_hot_obsidian_forge\2_gold\resources\hfo_gen89_ssot.sqlite'
conn = sqlite3.connect(DB)
conn.enable_load_extension(True)
sqlite_vec.load(conn)

# 1. Check vec_embeddings coverage for Spider Sovereign docs
print('=== vec_embeddings coverage for key docs ===')
for doc_id in [84, 136, 65, 66, 67, 82, 149]:
    row = conn.execute('SELECT COUNT(*) FROM vec_embeddings WHERE doc_id=?', (doc_id,)).fetchone()
    title = conn.execute('SELECT title FROM documents WHERE id=?', (doc_id,)).fetchone()
    print(f'  Doc {doc_id:5d} in vec_embeddings: {row[0]} | {title[0] if title else "?"}')

print()
# 2. Check if these docs have embeddings at all in the main documents table
print('=== embedding BLOB presence in documents table ===')
for doc_id in [84, 136, 65, 66, 67, 82, 149]:
    row = conn.execute('SELECT LENGTH(embedding) FROM documents WHERE id=?', (doc_id,)).fetchone()
    title = conn.execute('SELECT title FROM documents WHERE id=?', (doc_id,)).fetchone()
    emb_len = row[0] if row and row[0] else 0
    print(f'  Doc {doc_id:5d} embedding bytes: {emb_len} | {title[0] if title else "?"}')

print()
# 3. What does Doc 136 say?
row = conn.execute('SELECT title, bluf, content FROM documents WHERE id=136').fetchone()
print(f'=== Doc 136: {row[0]} ===')
print(f'BLUF: {row[1]}')
print(row[2][:600])

print()
# 4. FTS query simulation — what does the actual query parser extract?
import re
query = "who is controlling the hfo swarm on a higher dimensional manifold/sphere?"
clean = re.sub(r"[^\w\s]", " ", query)
fts_q = " OR ".join(w for w in clean.split() if len(w) > 3)
print(f'=== FTS query extracted from question ===')
print(f'  Input: {query}')
print(f'  FTS:   {fts_q}')
print()

# Does this FTS query match ANY of the correct answer docs?
rows = conn.execute(f"""
SELECT d.id, d.title FROM documents d
WHERE d.id IN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?)
""", (fts_q,)).fetchall()
print(f'  FTS hits for "{fts_q}": {len(rows)}')
for r in rows[:10]:
    print(f'    Doc {r[0]}: {r[1]}')

print()
# 5. What FTS query WOULD find obsidian_spider?
fts_correct = "obsidian_spider OR Spider OR Sovereign OR Galois OR P7 OR manifold"
rows2 = conn.execute("""
SELECT d.id, d.title FROM documents d
WHERE d.id IN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?)
ORDER BY d.id LIMIT 10
""", (fts_correct,)).fetchall()
print(f'=== FTS hits for "{fts_correct}" ===')
for r in rows2:
    print(f'  Doc {r[0]}: {r[1]}')

conn.close()
