import sqlite3, json, sys

DB = 'hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite'
conn = sqlite3.connect(DB)

print('=== ALL TABLES ===')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
for t in tables:
    name = t[0]
    count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
    cols = [c[1] for c in conn.execute(f'PRAGMA table_info("{name}")').fetchall()]
    print(f'  {name}: rows={count} | cols={cols}')

print()
print('=== GRIMOIRE TABLE (if exists) ===')
try:
    rows = conn.execute('SELECT * FROM hfo_grimoire LIMIT 10').fetchall()
    cols = [c[1] for c in conn.execute('PRAGMA table_info(hfo_grimoire)').fetchall()]
    print('COLS:', cols)
    for r in rows:
        print(dict(zip(cols, r)))
except Exception as e:
    print('hfo_grimoire not found:', e)

print()
print('=== BLACKBOARD TABLE (if exists) ===')
for bname in ['obsidian_blackboard', 'blackboard', 'hfo_blackboard']:
    try:
        cols = [c[1] for c in conn.execute(f'PRAGMA table_info({bname})').fetchall()]
        count = conn.execute(f'SELECT COUNT(*) FROM {bname}').fetchone()[0]
        print(f'{bname}: cols={cols} rows={count}')
    except Exception as e:
        print(f'{bname}: not found')

print()
print('=== SPELLS TABLE (if exists) ===')
for sname in ['spells', 'hfo_spells', 'grimoire_spells']:
    try:
        cols = [c[1] for c in conn.execute(f'PRAGMA table_info({sname})').fetchall()]
        count = conn.execute(f'SELECT COUNT(*) FROM {sname}').fetchone()[0]
        print(f'{sname}: cols={cols} rows={count}')
        rows = conn.execute(f'SELECT * FROM {sname} LIMIT 5').fetchall()
        for r in rows:
            print(' ', dict(zip(cols, r)))
    except Exception as e:
        print(f'{sname}: not found')

print()
print('=== RECENT STIGMERGY EVENTS (last 15) ===')
rows = conn.execute('''
    SELECT id, event_type, timestamp, subject
    FROM stigmergy_events
    ORDER BY id DESC LIMIT 15
''').fetchall()
for r in rows:
    print(f'  [{r[0]}] {r[1]} | {r[2][:19]} | {r[3]}')

print()
print('=== UNIQUE EVENT TYPES ===')
rows = conn.execute('''
    SELECT event_type, COUNT(*) as cnt
    FROM stigmergy_events
    GROUP BY event_type
    ORDER BY cnt DESC
    LIMIT 30
''').fetchall()
for r in rows:
    print(f'  {r[1]:6} {r[0]}')

conn.close()
