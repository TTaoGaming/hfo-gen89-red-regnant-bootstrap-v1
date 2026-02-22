"""Query SSOT for Songs of Strife and Songs of Splendor source documents."""
import sqlite3

DB = 'hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite'
conn = sqlite3.connect(DB)

print("=== STRIFE / E66 docs ===")
rows = conn.execute("""
    SELECT id, title, substr(bluf, 1, 200)
    FROM documents
    WHERE title LIKE '%Strife%' OR title LIKE '%STRIFE%'
       OR title LIKE '%E66%' OR title LIKE '%strife%'
    LIMIT 15
""").fetchall()
for r in rows:
    print(f"  [{r[0]}] {r[1][:80]}")

print()
print("=== SPLENDOR / E67 docs ===")
rows2 = conn.execute("""
    SELECT id, title, substr(bluf, 1, 200)
    FROM documents
    WHERE title LIKE '%Splendor%' OR title LIKE '%SPLENDOR%'
       OR title LIKE '%E67%' OR title LIKE '%splendor%'
    LIMIT 15
""").fetchall()
for r in rows2:
    print(f"  [{r[0]}] {r[1][:80]}")

print()
print("=== SINGER docs ===")
rows3 = conn.execute("""
    SELECT id, title, word_count
    FROM documents
    WHERE title LIKE '%SINGER%' OR title LIKE '%Singer%'
    LIMIT 10
""").fetchall()
for r in rows3:
    print(f"  [{r[0]}] {r[1][:80]} ({r[2]} words)")

conn.close()
