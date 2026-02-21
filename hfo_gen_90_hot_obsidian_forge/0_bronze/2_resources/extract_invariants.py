import sqlite3

DB = r'c:\hfoDev\hfo_gen_90_hot_obsidian_forge\2_gold\resources\hfo_gen90_ssot.sqlite'
conn = sqlite3.connect(DB)
cursor = conn.cursor()
cursor.execute("SELECT content FROM documents WHERE source_path LIKE 'contracts/%'")
row = cursor.fetchone()
conn.close()

# The content has a prefix line from memory ingestion, strip it
content = row[0]
# Find the start of the actual JSON
json_start = content.find('{')
if json_start > 0:
    content = content[json_start:]

out = r'c:\hfoDev\hfo_gen_90_hot_obsidian_forge\2_gold\resources\hfo_legendary_commanders_invariants.v1.json'
with open(out, 'w', encoding='utf-8') as f:
    f.write(content)
print(f"Wrote {len(content)} bytes to {out}")
