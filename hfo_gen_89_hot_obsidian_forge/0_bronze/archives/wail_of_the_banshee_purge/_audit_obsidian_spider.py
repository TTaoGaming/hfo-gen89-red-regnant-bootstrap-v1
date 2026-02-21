import sqlite3

DB = r'C:\hfoDev\hfo_gen_89_hot_obsidian_forge\2_gold\resources\hfo_gen89_ssot.sqlite'
conn = sqlite3.connect(DB)

# 1. Find all docs that reference obsidian_spider directly
print('=== FTS: obsidian_spider OR "spider sovereign" OR "spider web" ===')
rows = conn.execute("""
SELECT d.id, d.title, d.port, d.source
FROM documents d
WHERE d.id IN (
    SELECT rowid FROM documents_fts
    WHERE documents_fts MATCH 'obsidian_spider OR "spider sovereign" OR "Spider Sovereign"'
)
ORDER BY d.id LIMIT 30
""").fetchall()
for r in rows:
    print(f'  Doc {r[0]:5d} | {r[2] or "P-"} | {r[3]:<15} | {r[1]}')

print()
# 2. Check what's in the vec_embeddings table — does Doc 136 / Spider Sovereign docs have embeddings?
print('=== vec_embeddings coverage for key docs ===')
for doc_id in [84, 136, 65, 66, 67, 82, 149]:
    row = conn.execute('SELECT COUNT(*) FROM vec_embeddings WHERE doc_id=?', (doc_id,)).fetchone()
    title = conn.execute('SELECT title FROM documents WHERE id=?', (doc_id,)).fetchone()
    print(f'  Doc {doc_id:5d} in vec_embeddings: {row[0]} | {title[0] if title else "?"}')

print()
# 3. What does the Galois lattice / manifold look like for P7 Spider Sovereign
print('=== Doc 136 content snippet ===')
row = conn.execute('SELECT title, bluf, content FROM documents WHERE id=136').fetchone()
if row:
    print(f'BLUF: {row[1]}')
    print(row[2][:800])

print()
# 4. Check if the embedding for the query "higher dimensional manifold sphere" 
# is cosine-close to Spider Sovereign docs — let's check titles/bluf similarity manually
print('=== All docs with port=P7 or title containing spider/obsidian ===')
rows2 = conn.execute("""
SELECT id, title, bluf FROM documents
WHERE title LIKE '%spider%' OR title LIKE '%Spider%' OR title LIKE '%obsidian_spider%'
   OR title LIKE '%P7%' OR port='P7'
LIMIT 20
""").fetchall()
for r in rows2:
    print(f'  Doc {r[0]}: {r[1]}')
    print(f'    {r[2][:100]}')

conn.close()
