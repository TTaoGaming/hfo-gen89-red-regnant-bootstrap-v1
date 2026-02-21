import sqlite3
from pathlib import Path
db = Path(__file__).resolve().parent.parent.parent / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite"
print(f"DB: {db}")
print(f"Exists: {db.exists()}")
conn = sqlite3.connect(str(db))
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print(f"Tables: {tables}")
conn.close()
