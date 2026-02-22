import sqlite3
DB = 'hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite'
conn = sqlite3.connect(DB)

print('=== HFO_GRIMOIRE (4 rows) ===')
for r in conn.execute('SELECT id, spell_name, fca_archetype, hfo_mapping, medallion_layer FROM hfo_grimoire'):
    print(r)

print()
print('=== MISSION_STATE top 10 by priority ===')
for r in conn.execute('SELECT thread_key, status, priority, port, title FROM mission_state ORDER BY priority LIMIT 10'):
    print(r)

print()
print('=== STIGMERGY last 15 events ===')
for r in conn.execute('SELECT id, event_type, timestamp, subject FROM stigmergy_events ORDER BY id DESC LIMIT 15'):
    print(r)

print()
print('=== STIGMERGY top event types ===')
for r in conn.execute('SELECT event_type, COUNT(*) c FROM stigmergy_events GROUP BY event_type ORDER BY c DESC LIMIT 20'):
    print(r)

print()
print('=== COMPUTE_ROUTE (all 13) ===')
for r in conn.execute('SELECT port, daemon_name, task_type, model_id, provider FROM compute_route'):
    print(r)

conn.close()
print('DONE')
