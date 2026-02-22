import sqlite3, pathlib

db = pathlib.Path("C:/hfoDev/hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite")
conn = sqlite3.connect(db)
cur = conn.cursor()

# Get triggers on mission_state
cur.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger' AND tbl_name='mission_state'")
for row in cur.fetchall():
    print(f"TRIGGER: {row[0]}")
    print(row[1][:2000])
    print("---")

# Also check what columns mission_state has that relate to signal_metadata
cur.execute("PRAGMA table_info(mission_state)")
cols = cur.fetchall()
print("\nCOLUMNS:", [c[1] for c in cols])

conn.close()
