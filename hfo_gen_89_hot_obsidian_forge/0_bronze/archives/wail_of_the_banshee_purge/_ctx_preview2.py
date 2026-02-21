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

# Apply exact same sanitization as synthesize_with_npu
def sanitize(text):
    text = re.sub(r'^---.*?---\s*', '', text, flags=re.DOTALL)
    text = re.sub(r'<\|[^|>]{1,30}\|>', '', text)
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'</?think>', '', text)
    text = text.encode('ascii', errors='ignore').decode('ascii')
    text = re.sub(r'\n{4,}', '\n\n', text)
    text = re.sub(r'[ \t]{3,}', ' ', text)
    return text.strip()

ctx_clean = sanitize(ctx)
ctx_800 = ctx_clean[:800]

print(f'Cleaned len: {len(ctx_clean)}, trimmed to: {len(ctx_800)}')
print()
print('=== EXACTLY what Qwen3 sees (800 chars) ===')
print(ctx_800)
print()
print('=== Chars 800-1000 (just outside budget) ===')
print(ctx_clean[800:1000])
conn.close()
