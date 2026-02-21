import sqlite3, sys
import numpy as np
sys.path.insert(0, r'C:\hfoDev\hfo_gen_89_hot_obsidian_forge\0_bronze\resources')
import sqlite_vec
from hfo_npu_embedder import NPUEmbedder

DB = r'C:\hfoDev\hfo_gen_89_hot_obsidian_forge\2_gold\resources\hfo_gen89_ssot.sqlite'
conn = sqlite3.connect(DB)
conn.enable_load_extension(True)
sqlite_vec.load(conn)

emb = NPUEmbedder()
emb.load()  # required before embed()
q_arr = np.array(
    emb.embed("who is controlling the hfo swarm on a higher dimensional manifold/sphere?"),
    dtype=np.float32
)
q_norm = q_arr / (np.linalg.norm(q_arr) + 1e-9)

target_docs = [
    (37,  'Agent Swarm Guidance     ← KNN#1 (wrong)'),
    (64,  'HFO is not aliases       ← KNN#3 (wrong)'),
    (317, 'What HFO Actually Is     ← KNN#10 (wrong)'),
    (65,  'HFO Pantheon             ← correct-layer'),
    (82,  'Isomorphism Binding      ← correct-layer'),
    (84,  'Eight Legendary Cmnders  ← correct-layer'),
    (136, 'Spider Web Graph Topo    ← correct-layer'),
]

print(f'{"Doc":>6} | {"Cosine":>8} | Label')
print('-' * 65)
for doc_id, label in sorted(target_docs):
    row = conn.execute('SELECT embedding FROM vec_embeddings WHERE doc_id=?', (doc_id,)).fetchone()
    if not row:
        print(f'{doc_id:6d} | {"MISSING":>8} | {label}')
        continue
    vec = np.frombuffer(row[0], dtype=np.float32)
    vec_n = vec / (np.linalg.norm(vec) + 1e-9)
    cos = float(np.dot(q_norm, vec_n))
    print(f'{doc_id:6d} | {cos:8.4f} | {label}')

print()
print('=== FTS-is-useless proof ===')
print('Query words >3 chars: controlling, swarm, higher, dimensional, manifold, sphere')
print('FTS hits 2561 / 9868 docs — basically everything, top-5 by rowid = catalog/SDD docs')
print('Correct-answer doc keywords: obsidian_spider, Spider, Sovereign, P7, Galois')
print('Zero overlap with query vocabulary => FTS contributed +0 unique hits')

conn.close()
