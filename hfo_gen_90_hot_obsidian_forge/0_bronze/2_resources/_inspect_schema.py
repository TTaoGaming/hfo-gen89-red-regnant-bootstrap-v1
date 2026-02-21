"""Quick schema inspector for SSOT database."""
import sqlite3

DB = r"c:\hfoDev\hfo_gen_90_hot_obsidian_forge\2_gold\resources\hfo_gen90_ssot.sqlite"
conn = sqlite3.connect(DB)
c = conn.cursor()

print("=== TABLES ===")
c.execute("SELECT sql FROM sqlite_master WHERE type='table'")
for row in c.fetchall():
    print(row[0])
    print("---")

print("\n=== META KEYS ===")
c.execute("SELECT key, substr(value, 1, 300) FROM meta")
for row in c.fetchall():
    print(f"{row[0]}: {row[1]}")
    print()

print("\n=== STIGMERGY EVENT TYPES (top 20) ===")
c.execute("SELECT event_type, COUNT(*) as cnt FROM stigmergy_events GROUP BY event_type ORDER BY cnt DESC LIMIT 20")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\n=== LINEAGE TABLE ===")
c.execute("SELECT COUNT(*) FROM lineage")
print(f"  Rows: {c.fetchone()[0]}")

print("\n=== INDEXES ===")
c.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]}")

conn.close()
