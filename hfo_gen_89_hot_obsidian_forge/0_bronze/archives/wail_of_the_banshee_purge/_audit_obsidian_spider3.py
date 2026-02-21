import sqlite3, sys, re, struct
import numpy as np
sys.path.insert(0, r'C:\hfoDev\hfo_gen_89_hot_obsidian_forge\0_bronze\resources')
import sqlite_vec

DB = r'C:\hfoDev\hfo_gen_89_hot_obsidian_forge\2_gold\resources\hfo_gen89_ssot.sqlite'
conn = sqlite3.connect(DB)
conn.enable_load_extension(True)
sqlite_vec.load(conn)

# 1. FTS query simulation
query = "who is controlling the hfo swarm on a higher dimensional manifold/sphere?"
clean = re.sub(r"[^\w\s]", " ", query)
fts_q = " OR ".join(w for w in clean.split() if len(w) > 3)
print(f'=== FTS query extracted ===')
print(f'  Input: {query}')
print(f'  FTS:   {fts_q}')
rows = conn.execute(
    "SELECT d.id, d.title FROM documents d "
    "WHERE d.id IN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?)",
    (fts_q,)
).fetchall()
print(f'  FTS hits: {len(rows)}')
for r in rows[:5]:
    print(f'    Doc {r[0]}: {r[1]}')
print()

# 2. Get actual stored embedding vectors for the correct-answer docs
# and compute cosine sim to show why KNN missed them
# First get the query embedding from vec_embeddings by finding a proxy doc
# Actually let's just check what raw KNN returned vs where obsidian_spider docs rank

# Get the query vector — we need to re-embed. Let's load the embedder.
from hfo_npu_embedder import HFOEmbedder
emb = HFOEmbedder()
q_vec = emb.embed(query)
print(f'=== Query embedding: {len(q_vec)}-dim ===')

# Get vectors for key docs from vec_embeddings 
target_docs = {84: 'Eight Legendary Commanders',
               136: 'Spider Web as Graph Topology',
               65: 'HFO Pantheon',
               82: 'Isomorphism Binding',
               37: 'Agent Swarm Guidance (returned)',
               64: 'HFO is not aliases (returned)',
               317: 'What HFO Actually Is (returned)'}

q_arr = np.array(q_vec, dtype=np.float32)
q_norm = q_arr / (np.linalg.norm(q_arr) + 1e-9)

print('=== Cosine similarity: query vs key docs ===')
for doc_id, label in sorted(target_docs.items()):
    row = conn.execute(
        'SELECT embedding FROM vec_embeddings WHERE doc_id=?', (doc_id,)
    ).fetchone()
    if not row:
        print(f'  Doc {doc_id:5d} [{label}]: NO VECTOR')
        continue
    # vec_embeddings stores as binary float32
    blob = row[0]
    vec = np.frombuffer(blob, dtype=np.float32)
    vec_norm = vec / (np.linalg.norm(vec) + 1e-9)
    cos = float(np.dot(q_norm, vec_norm))
    print(f'  Doc {doc_id:5d} [{label}]: cosine={cos:.4f}')

print()
# 3. What FTS query WOULD find the correct docs
fts_correct = "obsidian_spider OR Sovereign OR Galois OR P7"
rows3 = conn.execute(
    "SELECT d.id, d.title FROM documents d "
    "WHERE d.id IN (SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?) LIMIT 8",
    (fts_correct,)
).fetchall()
print(f'=== FTS hits for correct query "{fts_correct}" ===')
for r in rows3:
    print(f'  Doc {r[0]}: {r[1]}')

conn.close()
