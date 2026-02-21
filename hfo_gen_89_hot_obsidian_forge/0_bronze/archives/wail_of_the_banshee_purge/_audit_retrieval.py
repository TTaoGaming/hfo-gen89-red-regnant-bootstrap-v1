import sys, sqlite3, time
sys.path.insert(0, r"c:\hfoDev\hfo_gen_89_hot_obsidian_forge\0_bronze\resources")
from hfo_shodh_query import fts_search, knn_search, _expand_fts_query, QueryEmbedder, load_sqlite_vec

DB = r"c:\hfoDev\hfo_gen_89_hot_obsidian_forge\2_gold\resources\hfo_gen89_ssot.sqlite"
conn = sqlite3.connect(DB)
load_sqlite_vec(conn)

emb = QueryEmbedder(device="NPU")
emb.load(verbose=False)
print(f"Embedder: {emb.device}")

questions = [
    ("who is controlling the hfo swarm on a higher dimensional manifold", "OBSIDIAN_SPIDER"),
    ("what is the red team commander",                                    "Red Regnant / P4"),
    ("what is COAST in the gesture FSM",                                  "COAST Governor"),
    ("what is MAP ELITE",                                                 "Pareto frontier spike factory"),
    ("what is a quine in HFO",                                            "QUINE federation"),
]

PASS = 0
for q, expected in questions:
    t0 = time.perf_counter()
    qv = emb.embed(q)
    knn = knn_search(conn, qv, top_k=5, vec_loaded=True)
    fts = fts_search(conn, q, limit=20)
    ms = (time.perf_counter()-t0)*1000
    all_titles = " ".join((r["title"] or "") for r in (knn+fts)[:20]).lower()
    hit = any(kw.lower() in all_titles for kw in expected.lower().replace("/"," ").split())
    PASS += int(hit)
    status = "PASS" if hit else "MISS"
    knn0 = knn[0]["title"][:55] if knn else "none"
    fts0 = fts[0]["title"][:55] if fts else "none"
    print(f"[{status}] {q[:52]}")
    print(f"       KNN[0]: {knn0}  ({knn[0]['score']:.3f} cosine)" if knn else "       KNN: empty")
    print(f"       FTS[0]: {fts0}")
    print(f"       expected: {expected}  [{ms:.0f}ms]")
    print()

print(f"RETRIEVAL: {PASS}/{len(questions)} pass")
conn.close()
