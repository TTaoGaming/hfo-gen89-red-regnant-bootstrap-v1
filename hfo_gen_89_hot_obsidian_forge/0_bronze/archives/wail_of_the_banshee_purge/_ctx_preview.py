import sqlite3, re

DB = r'C:\hfoDev\hfo_gen_89_hot_obsidian_forge\2_gold\resources\hfo_gen89_ssot.sqlite'
conn = sqlite3.connect(DB)
FRONT = re.compile(r'^---.*?---\s*', re.DOTALL)

results = [
    {'doc_id': 190, 'title': 'Eightfold OBSIDIAN_SPIDER', 'port': None, 'score': 0.5},
    {'doc_id': 276, 'title': 'P7 OBSIDIAN_SPIDER SECRETS', 'port': 'P7', 'score': 0.5},
]

parts = []
for r in results:
    raw = conn.execute('SELECT content FROM documents WHERE id=?', (r['doc_id'],)).fetchone()[0] or ''
    content = FRONT.sub('', raw.strip()).strip()[:1500]
    chunk = f"[Doc {r['doc_id']} | {r['title']} | port={r['port']} | score={r['score']}]\n{content}\n"
    parts.append(chunk)

ctx = '\n---\n'.join(parts)
print(f'Total ctx len: {len(ctx)}')
print()
print('=== First 1000 chars ===')
print(ctx[:1000])
conn.close()
