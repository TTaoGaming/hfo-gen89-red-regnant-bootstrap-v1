import sqlite3
from pathlib import Path
db = str(Path(__file__).resolve().parent.parent.parent / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite")
conn = sqlite3.connect(db)
p = conn.execute("SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%perceive%'").fetchone()[0]
y = conn.execute("SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%yield%'").fetchone()[0]
print(f"Perceives: {p}, Yields: {y}, Ratio: {y/max(p,1)*100:.1f}%")
# Count gen88 vs gen89 perceives
g88 = conn.execute("SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%gen88%perceive%'").fetchone()[0]
g89 = conn.execute("SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%gen89%perceive%'").fetchone()[0]
g88y = conn.execute("SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%gen88%yield%'").fetchone()[0]
g89y = conn.execute("SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%gen89%yield%'").fetchone()[0]
prey8p = conn.execute("SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE 'hfo.prey8.perceive%'").fetchone()[0]
prey8y = conn.execute("SELECT COUNT(*) FROM stigmergy_events WHERE event_type LIKE 'hfo.prey8.yield%'").fetchone()[0]
print(f"Gen88 perceive: {g88}, Gen88 yield: {g88y}")
print(f"Gen89 perceive: {g89}, Gen89 yield: {g89y}")
print(f"Plain prey8 perceive: {prey8p}, yield: {prey8y}")
# Show event_type patterns
rows = conn.execute("SELECT event_type, COUNT(*) FROM stigmergy_events WHERE event_type LIKE '%perceive%' OR event_type LIKE '%yield%' GROUP BY event_type ORDER BY COUNT(*) DESC").fetchall()
for r in rows:
    print(f"  {r[0]}: {r[1]}")
conn.close()
