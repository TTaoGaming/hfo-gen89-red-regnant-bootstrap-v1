import sqlite3, pathlib

db = pathlib.Path("C:/hfoDev/hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite")
conn = sqlite3.connect(db)
cur = conn.cursor()

# Triggers on stigmergy_events
cur.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger' AND tbl_name='stigmergy_events'")
for row in cur.fetchall():
    print(f"TRIGGER: {row[0]}")
    print(row[1])
    print("---")

conn.close()
