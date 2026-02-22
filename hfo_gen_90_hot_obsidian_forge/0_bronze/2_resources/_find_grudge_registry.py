"""Find the Book of Blood registry and all GRUDGE-numbered docs."""
import sqlite3
conn = sqlite3.connect('hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite')

# Find the Book of Blood source doc
results = conn.execute(
    "SELECT id, title, word_count FROM documents WHERE id IN "
    "(SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?) ORDER BY word_count DESC LIMIT 15",
    ('"Book of Blood" grudge',)
).fetchall()
print("=== Book of Blood sources ===")
for r in results:
    print(f"  [{r[0]:4d}] {r[2]:6d}w  {r[1][:70]}")

# Find docs with high GRUDGE numbers
results2 = conn.execute(
    "SELECT id, title, word_count FROM documents WHERE id IN "
    "(SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?) ORDER BY word_count DESC LIMIT 10",
    ('GRUDGE_014 OR GRUDGE_020 OR GRUDGE_033 OR "grudge registry"',)
).fetchall()
print("\n=== Extended GRUDGE numbers ===")
for r in results2:
    print(f"  [{r[0]:4d}] {r[2]:6d}w  {r[1][:70]}")

# Check what's in doc 120 about GRUDGE specifically
row = conn.execute("SELECT substr(content,1,6000) FROM documents WHERE id=120").fetchone()
if row:
    # Print lines containing GRUDGE
    for line in row[0].split('\n'):
        if 'GRUDGE' in line or 'BREACH' in line or 'Anti-Pattern' in line.replace('-',''):
            print(f"  DOC120: {line[:100]}")

conn.close()
