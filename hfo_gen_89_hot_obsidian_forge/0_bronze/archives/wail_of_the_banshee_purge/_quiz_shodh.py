"""
_quiz_shodh.py — Multi-question quiz against Shodh (no NPU — retrieve only).
Runs FTS+KNN retrieval, shows top doc, reports expected answer.
Skips synthesis to stay fast.
"""
import sqlite3, sys, re, time
sys.path.insert(0, r"c:\hfoDev\hfo_gen_89_hot_obsidian_forge\0_bronze\resources")
from hfo_shodh_query import fts_search, knn_search, _expand_fts_query, assemble_context
from hfo_shodh_query import QueryEmbedder

DB = r"c:\hfoDev\hfo_gen_89_hot_obsidian_forge\2_gold\resources\hfo_gen89_ssot.sqlite"
conn = sqlite3.connect(DB)

QUESTIONS = [
    # (question, expected_entity_or_concept)
    ("who is the red team commander of HFO?",                              "Red Regnant / P4"),
    ("what does the kraken keeper do?",                                    "P6 ASSIMILATE"),
    ("what is COAST in the gesture system?",                               "inertia / dwell timer / L4 Meadows"),
    ("how does HFO preserve knowledge across catastrophe?",               "federation stem-cell quine"),
    ("what are the 8 ports of the HFO octree?",                           "OBSIDIAN mnemonic"),
    ("what is a GRUDGE guard?",                                            "negative spec / regression protection"),
    ("what is MAP ELITE?",                                                 "Pareto frontier spike factory"),
    ("what is the Obsidian Hourglass?",                                    "8^N fractal timescale"),
    ("what delivers payloads in the HFO system?",                         "Harmonic Hydra / P3 INJECT"),
    ("what is the braided mission thread?",                                "Alpha+Omega mission thread"),
    ("what is ATDD?",                                                      "acceptance test driven development"),
    ("what is the medallion architecture?",                               "bronze silver gold HFO layers"),
    ("what is the Galois anti-diagonal pairing?",                         "port dyad symmetry"),
    ("what is Omega v13?",                                                 "gesture substrate microkernel"),
    ("who is the Spider Sovereign?",                                       "P7 NAVIGATE OBSIDIAN_SPIDER"),
    ("what is stigmergy in HFO?",                                         "CloudEvents indirect coordination"),
    ("what is the Pyre Praetorian?",                                       "P5 IMMUNIZE / Azure Phoenix"),
    ("what is a portable artifact?",                                       "gold medallion context capsule quine"),
    ("what is the Lidless Legion?",                                        "P0 OBSERVE / sensing"),
    ("what are the 8 powerwords?",                                         "OBSIDIAN compression seeds"),
]

# Embed with GPU
print("Loading embedder...")
embedder = QueryEmbedder(device="NPU")
embedder.load(verbose=False)
print(f"Embedder ready on {embedder.device}\n")

print(f"{'#':>2}  {'QUESTION':<55} {'TOP FTS DOC':<40} {'FTS EXPANDED QUERY'}")
print("-" * 160)

results_table = []
for i, (q, expected) in enumerate(QUESTIONS, 1):
    t0 = time.perf_counter()
    fts_q_expanded = _expand_fts_query(q)
    fts = fts_search(conn, q, limit=3)
    q_vec = embedder.embed(q)
    knn = knn_search(conn, q_vec, top_k=5, vec_loaded=False)
    elapsed = (time.perf_counter() - t0) * 1000

    top_fts = fts[0]["title"][:38] if fts else "(no FTS hit)"
    top_knn = knn[0]["title"][:38] if knn else "(no KNN)"
    expanded_preview = fts_q_expanded[:60] if fts_q_expanded else "(empty)"

    print(f"{i:>2}. {q:<55} FTS: {top_fts:<40} [{elapsed:.0f}ms]")
    print(f"     expected: {expected}")
    print(f"     expanded: {expanded_preview}")
    print(f"     knn[0]:   {top_knn}")
    # Show whether expected concept appears in top-5 combined
    all_titles = " ".join((r["title"] or "") for r in (fts + knn)[:8]).lower()
    hit = any(kw.lower() in all_titles for kw in expected.replace("/", " ").split())
    print(f"     PASS: {'YES ✓' if hit else 'NO ✗  ←── MISS'}")
    print()
    results_table.append((q, expected, hit, fts_q_expanded))

# Summary
passed = sum(1 for *_, h, __ in results_table if h)
print(f"\n{'='*72}")
print(f"  QUIZ RESULT: {passed}/{len(QUESTIONS)} questions retrieved correct domain")
print(f"{'='*72}")
print("\nMISSES (need alias table expansion):")
for q, exp, hit, fts_q in results_table:
    if not hit:
        print(f"  - {q!r}")
        print(f"    expected: {exp}")
        print(f"    expanded FTS: {fts_q[:80]}")

conn.close()
