"""Extract heuristics from doc 177 and full GRUDGE table from doc 120."""
import sqlite3

conn = sqlite3.connect('hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite')
out = open('hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/_heuristics.txt', 'w', encoding='utf-8')

def w(s):
    out.write(s + '\n')

# Doc 177 - Claude heuristics
row = conn.execute("SELECT title, content FROM documents WHERE id=177").fetchone()
if row:
    w("=" * 80)
    w(f"DOC 177: {row[0]}")
    w("=" * 80)
    w(row[1])

w("\n\n")

# Doc 120 - Red Regnant full GRUDGE table
row = conn.execute("SELECT title, content FROM documents WHERE id=120").fetchone()
if row:
    w("=" * 80)
    w(f"DOC 120: {row[0]}")
    w("=" * 80)
    w(row[1])

w("\n\n")

# Doc 175 - reward hacking
row = conn.execute("SELECT title, content FROM documents WHERE id=175").fetchone()
if row:
    w("=" * 80)
    w(f"DOC 175: {row[0]}")
    w("=" * 80)
    w(row[1])

out.close()
conn.close()

import os
print(f"Written: {os.path.getsize('hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/_heuristics.txt'):,} bytes")
