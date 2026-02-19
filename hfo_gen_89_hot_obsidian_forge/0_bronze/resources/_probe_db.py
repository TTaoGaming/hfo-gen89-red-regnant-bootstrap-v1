import sqlite3
conn = sqlite3.connect(r'c:\hfoDev\hfo_gen_89_hot_obsidian_forge\2_gold\resources\hfo_gen89_ssot.sqlite')
c = conn.cursor()

print("=== TABLES ===")
for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    print(row[0])

print("\n=== META KEYS ===")
for row in c.execute("SELECT key, substr(value, 1, 120) FROM meta"):
    print(f"{row[0]}: {row[1]}")

print("\n=== DOC SOURCES ===")
for row in c.execute("SELECT source, COUNT(*), SUM(word_count) FROM documents GROUP BY source ORDER BY COUNT(*) DESC"):
    print(f"  {row[0]}: {row[1]} docs, {row[2]} words")

print("\n=== STIGMERGY TOP 10 ===")
for row in c.execute("SELECT event_type, COUNT(*) FROM stigmergy_events GROUP BY event_type ORDER BY COUNT(*) DESC LIMIT 10"):
    print(f"  {row[0]}: {row[1]}")

print("\n=== DB FILE SIZE ===")
import os
sz = os.path.getsize(r'c:\hfoDev\hfo_gen_89_hot_obsidian_forge\2_gold\resources\hfo_gen89_ssot.sqlite')
print(f"  {sz / (1024*1024):.1f} MB")

conn.close()
