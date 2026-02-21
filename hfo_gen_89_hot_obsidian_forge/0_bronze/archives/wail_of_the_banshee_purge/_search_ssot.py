import sqlite3
conn = sqlite3.connect('hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite')
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(stigmergy_events);")
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
for row in cursor.fetchall():
    print(row)
