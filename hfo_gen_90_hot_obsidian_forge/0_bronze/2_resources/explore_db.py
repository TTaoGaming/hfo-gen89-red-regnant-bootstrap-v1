import sqlite3
import json

conn = sqlite3.connect(r'c:\hfoDev\hfo_gen90_ssot.sqlite')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 1. List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cursor.fetchall()]
print("=" * 80)
print(f"TABLES ({len(tables)}):")
print("=" * 80)
for t in tables:
    cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
    count = cursor.fetchone()[0]
    print(f"  {t:50s}  ({count:,} rows)")

# 2. Schema for each table
print("\n" + "=" * 80)
print("SCHEMAS:")
print("=" * 80)
for t in tables:
    print(f"\n--- {t} ---")
    cursor.execute(f"PRAGMA table_info([{t}])")
    cols = cursor.fetchall()
    for col in cols:
        pk = " [PK]" if col[5] else ""
        nn = " NOT NULL" if col[3] else ""
        default = f" DEFAULT {col[4]}" if col[4] is not None else ""
        print(f"  {col[1]:40s} {col[2]:15s}{pk}{nn}{default}")

# 3. Indexes
print("\n" + "=" * 80)
print("INDEXES:")
print("=" * 80)
cursor.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY tbl_name, name")
for idx in cursor.fetchall():
    print(f"  {idx[0]:50s} on {idx[1]}")
    if idx[2]:
        print(f"    {idx[2]}")

# 4. Views
cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='view' ORDER BY name")
views = cursor.fetchall()
if views:
    print("\n" + "=" * 80)
    print(f"VIEWS ({len(views)}):")
    print("=" * 80)
    for v in views:
        print(f"\n--- {v[0]} ---")
        print(f"  {v[1]}")

# 5. Triggers
cursor.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='trigger' ORDER BY name")
triggers = cursor.fetchall()
if triggers:
    print("\n" + "=" * 80)
    print(f"TRIGGERS ({len(triggers)}):")
    print("=" * 80)
    for tr in triggers:
        print(f"\n--- {tr[0]} (on {tr[1]}) ---")
        print(f"  {tr[2]}")

# 6. Sample rows from each table (first 3 rows)
print("\n" + "=" * 80)
print("SAMPLE DATA (first 3 rows per table):")
print("=" * 80)
for t in tables:
    print(f"\n--- {t} ---")
    cursor.execute(f"SELECT * FROM [{t}] LIMIT 3")
    rows = cursor.fetchall()
    if rows:
        col_names = [description[0] for description in cursor.description]
        for i, row in enumerate(rows):
            print(f"  Row {i+1}:")
            for cn, val in zip(col_names, row):
                val_str = str(val)
                if len(val_str) > 200:
                    val_str = val_str[:200] + "..."
                print(f"    {cn}: {val_str}")
    else:
        print("  (empty)")

# 7. Database size info
cursor.execute("PRAGMA page_count")
page_count = cursor.fetchone()[0]
cursor.execute("PRAGMA page_size")
page_size = cursor.fetchone()[0]
print(f"\n{'=' * 80}")
print(f"DB SIZE: {page_count * page_size / 1024 / 1024:.1f} MB ({page_count} pages x {page_size} bytes)")

conn.close()
