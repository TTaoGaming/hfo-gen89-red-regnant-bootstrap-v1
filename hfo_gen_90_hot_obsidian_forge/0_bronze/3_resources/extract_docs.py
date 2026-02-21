import sqlite3

conn = sqlite3.connect('hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite')
cursor = conn.cursor()

docs = [101, 170, 471, 620, 53]
for doc_id in docs:
    cursor.execute('SELECT content FROM documents WHERE id = ?', (doc_id,))
    content = cursor.fetchone()[0]
    with open(f'doc_{doc_id}.md', 'w', encoding='utf-8') as f:
        f.write(content)
