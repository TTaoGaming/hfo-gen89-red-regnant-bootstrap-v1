import sqlite3
import json

conn = sqlite3.connect('hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite')
cursor = conn.cursor()

query = """
SELECT id, title, bluf 
FROM documents 
WHERE id IN (
    SELECT rowid 
    FROM documents_fts 
    WHERE documents_fts MATCH 'title:grimoire OR title:chimera OR title:"galois lattice" OR title:spells OR title:quine OR title:"braided mission thread"'
)
LIMIT 20;
"""

cursor.execute(query)
results = cursor.fetchall()

for row in results:
    print(f"ID: {row[0]}")
    print(f"Title: {row[1]}")
    print(f"BLUF: {row[2]}")
    print("-" * 40)
