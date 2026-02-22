import sqlite3
conn = sqlite3.connect("hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite")
for row in conn.execute("SELECT id, title, medallion, port, word_count FROM documents WHERE id IN (9871,9872) ORDER BY id"):
    print(f"Doc {row[0]}: {row[1][:60]}")
    print(f"  medallion={row[2]}  port={row[3]}  words={row[4]}")
conn.close()
