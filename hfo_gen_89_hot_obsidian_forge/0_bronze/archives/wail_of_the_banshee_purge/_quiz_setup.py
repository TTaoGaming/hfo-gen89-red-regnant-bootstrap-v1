"""
Inventory all quine documents + run a multi-question quiz against Shodh.
"""
import sqlite3, sys, re, time
from collections import Counter

DB = r"c:\hfoDev\hfo_gen_89_hot_obsidian_forge\2_gold\resources\hfo_gen89_ssot.sqlite"
conn = sqlite3.connect(DB)

# ── 1. Inventory all quines ──────────────────────────────────────────────────
print("=" * 72)
print("  QUINE INVENTORY")
print("=" * 72)
rows = conn.execute("""
    SELECT id, title, source, port, word_count, bluf
    FROM documents
    WHERE lower(title) LIKE '%quine%'
       OR lower(bluf)  LIKE '%quine%'
    ORDER BY word_count DESC
""").fetchall()
for r in rows:
    bluf_snippet = (r[5] or "")[:80].replace("\n", " ").strip()
    title = (r[1] or "---")[:60]
    port  = (r[3] or "P-")[:3]
    src   = (r[2] or "-")[:10]
    print(f"  [{r[0]:5d}] wc={r[4]:5d} | {port:3s} | src={src:10s} | {title}")
    if bluf_snippet:
        print(f"          bluf: {bluf_snippet}")
print(f"\n  Total quine docs: {len(rows)}\n")

# ── 2. Read key quines ───────────────────────────────────────────────────────
KEY_IDS = [53, 282, 110, 157]  # federation quine manifest, quine archetype trade study, gen8 readiness, context capsule
print("=" * 72)
print("  KEY QUINE CONTENT (first 600 chars each)")
print("=" * 72)
for doc_id in KEY_IDS:
    row = conn.execute("SELECT id, title, bluf, content FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not row:
        continue
    content_snippet = (row[3] or "").replace("\n", " ")[:600]
    print(f"\n[Doc {row[0]}] {row[1]}")
    print(f"  BLUF: {(row[2] or '')[:120]}")
    print(f"  BODY: {content_snippet}")

# ── 3. Scan for all _HFO_EXPANSION-style vocabulary in the SSOT ─────────────
# Find the _HFO_EXPANSION dict and read it
print("\n\n" + "=" * 72)
print("  CURRENT _HFO_EXPANSION ALIAS TABLE")
print("=" * 72)
with open(r"c:\hfoDev\hfo_gen_89_hot_obsidian_forge\0_bronze\resources\hfo_shodh_query.py") as f:
    src = f.read()
m = re.search(r"_HFO_EXPANSION\s*=\s*\{(.+?)\n\}", src, re.DOTALL)
if m:
    print(m.group(0)[:3000])
else:
    print("  NOT FOUND")

# ── 4. Extract all ALLCAPS identifiers from the diataxis gold layer ──────────
print("\n\n" + "=" * 72)
print("  TOP ALLCAPS HFO ENTITIES (diataxis docs only)")
print("=" * 72)
docs = conn.execute("SELECT content FROM documents WHERE source='diataxis' LIMIT 160").fetchall()
all_caps = []
_CAPS_RE = re.compile(r'\b([A-Z][A-Z_0-9]{3,})\b')
for (content,) in docs:
    if content:
        all_caps.extend(_CAPS_RE.findall(content))
# Filter noise
NOISE = {"NULL","TRUE","FALSE","HTTP","HTML","CSS","JSON","YAML","UUID","API",
          "SSOT","HFO","WASM","URL","TS","JS","SQL","FSM","BDD","DI","UI",
          "P0","P1","P2","P3","P4","P5","P6","P7","PKGS","GA","AI","PBFT",
          "JADC2","PDCA","DSE","AoA","MAP","MOO","REST","CRUD","BFT","MVP",
          "STEM","ORM","VC","UX","PREV","NOTE","TODO","DONE","PASS","FAIL"}
top = [(e, n) for e, n in Counter(all_caps).most_common(80) if e not in NOISE and len(e) >= 4]
for entity, count in top[:60]:
    print(f"  {count:4d}x  {entity}")

conn.close()
