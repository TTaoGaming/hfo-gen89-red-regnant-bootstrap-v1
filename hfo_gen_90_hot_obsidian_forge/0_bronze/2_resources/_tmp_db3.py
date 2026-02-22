import sqlite3, json
DB = 'hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite'
conn = sqlite3.connect(DB)

# Read last yield event data
print('=== LAST YIELD (ID 17877) ===')
row = conn.execute("SELECT id, event_type, timestamp, subject, data_json FROM stigmergy_events WHERE id = 17877").fetchone()
if row:
    print(f"ID: {row[0]}, type: {row[1]}, ts: {row[2]}, subject: {row[3]}")
    try:
        d = json.loads(row[4])
        for k, v in d.items():
            print(f"  {k}: {str(v)[:200]}")
    except:
        print(f"  raw: {row[4][:500]}")

print()
print('=== LAST REACT (ID 17878) ===')
row = conn.execute("SELECT id, event_type, timestamp, subject, data_json FROM stigmergy_events WHERE id = 17878").fetchone()
if row:
    print(f"ID: {row[0]}, type: {row[1]}, ts: {row[2]}, subject: {row[3]}")
    try:
        d = json.loads(row[4])
        for k, v in d.items():
            print(f"  {k}: {str(v)[:200]}")
    except:
        print(f"  raw: {row[4][:500]}")

print()
print('=== LAST 5 YIELDS ===')
for row in conn.execute("SELECT id, timestamp, subject, data_json FROM stigmergy_events WHERE event_type LIKE '%yield%' ORDER BY id DESC LIMIT 5"):
    print(f"ID: {row[0]}, ts: {row[1]}, subject: {row[2]}")
    try:
        d = json.loads(row[3])
        summary = d.get('summary', d.get('data', {}).get('summary', ''))
        print(f"  summary: {str(summary)[:300]}")
    except:
        print(f"  raw: {str(row[3])[:200]}")

conn.close()
