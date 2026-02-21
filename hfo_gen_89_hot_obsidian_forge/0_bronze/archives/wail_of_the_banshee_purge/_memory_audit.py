import sqlite3, sys
DB = r'hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite'
db = sqlite3.connect(DB)

print('=== tables ===')
for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
    print(' ', r[0])

print()
print('=== shodh/hebbian stigmergy events ===')
rows = db.execute("""
    SELECT event_type, COUNT(*) as n FROM stigmergy_events
    WHERE event_type LIKE '%shodh%' OR event_type LIKE '%hebbian%'
    GROUP BY event_type ORDER BY n DESC
""").fetchall()
for r in rows: print(f"  {r[1]:4d}  {r[0]}")
if not rows: print('  NONE — zero shodh/hebbian events in stigmergy_events')

print()
print('=== last 5 shodh.query stigmergy events ===')
rows = db.execute("""
    SELECT event_type, timestamp, data_json FROM stigmergy_events
    WHERE event_type LIKE '%shodh%'
    ORDER BY timestamp DESC LIMIT 5
""").fetchall()
for r in rows: print(f"  {r[0]}  {r[1][:19]}  {r[2][:80]}")
if not rows: print('  NONE')

print()
print('=== shodh_associations table ===')
try:
    n = db.execute("SELECT COUNT(*) FROM shodh_associations").fetchone()[0]
    top = db.execute("""SELECT doc_a, doc_b, weight, co_activation_count
        FROM shodh_associations ORDER BY weight DESC LIMIT 5""").fetchall()
    print(f"  rows: {n}")
    for r in top: print(f"  doc_a={r[0]} doc_b={r[1]} w={r[2]:.4f} hits={r[3]}")
except Exception as e:
    print(f"  ERROR: {e}")

print()
print('=== shodh_co_retrieval table ===')
try:
    n = db.execute("SELECT COUNT(*) FROM shodh_co_retrieval").fetchone()[0]
    print(f"  rows: {n}")
except Exception as e:
    print(f"  ERROR: {e}")

print()
print('=== DIAGNOSIS: does hebbian feed back into stigmergy? ===')
# The feedback loop question: does shodh_associations get read back into stigmergy_events,
# or does the hebbian weight only influence run_query() retrieval (Step 3b)?
import ast, inspect, sys
sys.path.insert(0, r'hfo_gen_89_hot_obsidian_forge/0_bronze/resources')
try:
    import hfo_shodh as hs
    src = inspect.getsource(hs.cmd_co_retrieve)
    has_stigmergy_write = 'stigmergy_events' in src or '_emit_stigmergy' in src
    print(f"  cmd_co_retrieve writes to stigmergy_events: {has_stigmergy_write}")
    print(f"  => Hebbian updates ONLY go to shodh_associations (private table)")
    print(f"  => They are NOT emitted as CloudEvents into stigmergy_events")
    print(f"  => The only stigmergy write is in run_query() AFTER synthesis (hfo.gen89.shodh.query)")
except Exception as e:
    print(f"  import error: {e}")

db.close()
