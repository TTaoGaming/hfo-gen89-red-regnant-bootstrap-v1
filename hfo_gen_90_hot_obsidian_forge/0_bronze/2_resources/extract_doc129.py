import sqlite3

conn = sqlite3.connect('hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite')
cursor = conn.cursor()

cursor.execute('SELECT content FROM documents WHERE id = 129')
content = cursor.fetchone()[0]
with open('doc_129.md', 'w', encoding='utf-8') as f:
    f.write(content)
