import sqlite3
from pathlib import Path
db = str(Path(__file__).resolve().parent.parent.parent / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite")
conn = sqlite3.connect(db)
# Find good promotion candidates — gold_report or silver source docs
rows = conn.execute("""
    SELECT id, title, source, medallion 
    FROM documents 
    WHERE source IN ('gold_report','silver','config')
    LIMIT 15
""").fetchall()
for r in rows:
    print(f"{r[0]}: [{r[2]}] medallion={r[3]} — {r[1][:80]}")
conn.close()
