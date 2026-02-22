"""Extract the Book of Blood comprehensive report and full GRUDGE names from braided thread."""
import sqlite3, re

conn = sqlite3.connect('hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite')

# 1. Find the comprehensive Book of Blood report
results = conn.execute(
    "SELECT id, title, word_count, source_path FROM documents WHERE source_path LIKE '%book_of_blood%' OR title LIKE '%book_of_blood%' OR title LIKE '%GRUDGE%' ORDER BY word_count DESC LIMIT 20"
).fetchall()
print("=== Book of Blood path search ===")
for r in results:
    print(f"  [{r[0]:4d}] {r[2]:6d}w  path:{str(r[3])[:80]}  title:{str(r[1])[:50]}")

# 2. Get GRUDGE names from braided thread - read full content
row = conn.execute("SELECT content FROM documents WHERE id=7855").fetchone()
if row:
    content = row[0]
    # Find the GRUDGE definitions section - look for name/description patterns
    # Look for patterns like: id: "GRUDGE_001" ... name: "..." ... description: "..."
    chunks = re.split(r'(?=id:\s+"GRUDGE_)', content)
    print(f"\n=== Braided thread: {len(chunks)-1} GRUDGE chunks found ===")
    for chunk in chunks[1:25]:  # first 24 chunks (GRUDGE_001 to GRUDGE_025)
        lines = chunk.split('\n')[:12]  # first 12 lines of each chunk
        snippet = '\n'.join(l for l in lines if l.strip())[:300]
        print(f"\n--- {snippet[:300]}")

conn.close()
