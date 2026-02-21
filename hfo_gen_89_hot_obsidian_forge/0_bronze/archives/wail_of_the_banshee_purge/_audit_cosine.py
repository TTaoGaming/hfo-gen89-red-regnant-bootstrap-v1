import sqlite3, sys, re
import numpy as np
sys.path.insert(0, r'C:\hfoDev\hfo_gen_89_hot_obsidian_forge\0_bronze\resources')
import sqlite_vec
from hfo_npu_embedder import NPUEmbedder

DB = r'C:\hfoDev\hfo_gen_89_hot_obsidian_forge\2_gold\resources\hfo_gen89_ssot.sqlite'
conn = sqlite3.connect(DB)
conn.enable_load_extension(True)
sqlite_vec.load(conn)

# Get query embedding
emb = NPUEmbedder()
q_vec = emb.embed("who is controlling the hfo swarm on a higher dimensional manifold/sphere?")
q_arr = np.array(q_vec, dtype=np.float32)
q_norm = q_arr / (np.linalg.norm(q_arr) + 1e-9)

target_docs = [
    (84,  'Eight Legendary Commanders'),
    (136, 'Spider Web as Graph Topology'),
    (65,  'HFO Pantheon'),
    (82,  'Isomorphism Binding'),
    (37,  'Agent Swarm Guidance  ← KNN#1 returned'),
    (64,  'HFO is not aliases   ← KNN#3 returned'),
    (317, 'What HFO Actually Is ← KNN#10 returned'),
]

print('=== Cosine similarity: query vs docs ===')
print(f'  {"Doc":>6}  {"Cosine":>8}  Label')
for doc_id, label in sorted(target_docs, key=lambda x: x[0]):
    row = conn.execute('SELECT embedding FROM vec_embeddings WHERE doc_id=?', (doc_id,)).fetchone()
    if not row:
        print(f'  {doc_id:>6}   NO VEC   {label}')
        continue
    blob = row[0]
    vec = np.frombuffer(blob, dtype=np.float32)
    vec_norm = vec / (np.linalg.norm(vec) + 1e-9)
    cos = float(np.dot(q_norm, vec_norm))
    print(f'  {doc_id:>6}  {cos:>8.4f}  {label}')

print()

# Also check what rank obsidian_spider docs would get in the full 9868-doc KNN
print('=== Full KNN rank of Spider Sovereign docs ===')
q_bytes = q_arr.tobytes()
rows = conn.execute(
    "SELECT doc_id, distance FROM vec_embeddings WHERE embedding MATCH ? "
    "AND k = 9868 ORDER BY distance LIMIT 9868",
    (q_bytes,)
).fetchall()
rank_map = {r[0]: i+1 for i, r in enumerate(rows)}
for doc_id, label in target_docs:
    rank = rank_map.get(doc_id, 'NOT IN VEC')
    print(f'  Doc {doc_id:>5}: rank {rank}  | {label}')

conn.close()
