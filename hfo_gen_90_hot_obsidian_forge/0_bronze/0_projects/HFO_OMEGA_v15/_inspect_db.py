import sqlite3, pathlib

db = pathlib.Path("C:/hfoDev/hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite")
conn = sqlite3.connect(db)
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print("TABLES:", tables)

for t in tables:
    if any(k in t.lower() for k in ["braid", "mission", "thread", "braided"]):
        cur.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,))
        print(f"\nSCHEMA [{t}]:", cur.fetchone())
        cur.execute(f"SELECT * FROM [{t}] LIMIT 5")
        rows = cur.fetchall()
        desc = [d[0] for d in cur.description]
        print(f"COLS: {desc}")
        for row in rows:
            print("  ROW:", row)

conn.close()
