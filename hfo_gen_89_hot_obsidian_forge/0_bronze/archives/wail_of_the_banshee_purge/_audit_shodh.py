import sqlite3
DB = r'C:\hfoDev\hfo_gen_89_hot_obsidian_forge\2_gold\resources\hfo_gen89_ssot.sqlite'
conn = sqlite3.connect(DB)

# Read Doc 43 — semantic manifold
row = conn.execute('SELECT title, bluf, content FROM documents WHERE id=43').fetchone()
print('=== Doc 43 ===')
print(f'BLUF: {row[1]}')
print(f'CONTENT (first 1200):\n{row[2][:1200]}')
print()

# Content search for manifold/higher-dimensional/Swarmlord
rows = conn.execute(
    "SELECT id, title FROM documents "
    "WHERE content LIKE '%higher dimensional%' OR content LIKE '%higher-dimensional%' "
    "OR content LIKE '%Swarmlord%' LIMIT 15"
).fetchall()
print('=== docs containing manifold/higher dimensional/Swarmlord ===')
for r in rows:
    print(f'  {r[0]}: {r[1]}')
print()

# Shodh schema
cols = conn.execute('PRAGMA table_info(shodh_associations)').fetchall()
print('=== shodh_associations schema ===')
for c in cols:
    print(f'  {c[1]} {c[2]}')
print()

# Check shodh_associations top weights
top = conn.execute('SELECT * FROM shodh_associations ORDER BY weight DESC LIMIT 5').fetchall()
print('=== shodh top weights (first 5) ===')
for t in top:
    print(f'  {t}')

conn.close()
