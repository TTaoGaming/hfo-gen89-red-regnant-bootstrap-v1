import sqlite3
db = sqlite3.connect(r'hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite')
rows = db.execute(
    'SELECT event_type, timestamp, data_json FROM stigmergy_events ORDER BY rowid DESC LIMIT 5'
).fetchall()
print('=== last 5 stigmergy events ===')
for r in rows:
    print(f'  {r[0]}')
    print(f'  {r[1][:19]}')
    print(f'  {r[2][:200]}')
    print()

# Specifically check for hebbian events
rows2 = db.execute(
    "SELECT COUNT(*) FROM stigmergy_events WHERE event_type='hfo.gen89.shodh.hebbian.co_retrieval'"
).fetchone()
print(f'hebbian.co_retrieval events: {rows2[0]}')

# Verify doc 37 is NOT paired with anything new after the test
from datetime import datetime, timezone
new_pairs = db.execute(
    "SELECT doc_a, doc_b, weight FROM shodh_associations WHERE (doc_a=37 OR doc_b=37) AND last_activated > '2026-02-21'"
).fetchall()
print(f'new pairs involving hub doc 37 since today: {len(new_pairs)} (should be 0)')
db.close()
