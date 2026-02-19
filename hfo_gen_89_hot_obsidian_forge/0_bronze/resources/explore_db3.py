import sqlite3, json

conn = sqlite3.connect(r'c:\hfoDev\hfo_gen89_ssot.sqlite')
cursor = conn.cursor()

# 1. Get the quine instructions and schema doc from meta
print("=" * 80)
print("QUINE INSTRUCTIONS:")
print("=" * 80)
cursor.execute("SELECT value FROM meta WHERE key='quine_instructions'")
row = cursor.fetchone()
if row: print(row[0])

print("\n" + "=" * 80)
print("SCHEMA DOC:")
print("=" * 80)
cursor.execute("SELECT value FROM meta WHERE key='schema_doc'")
row = cursor.fetchone()
if row: print(row[0])

print("\n" + "=" * 80)
print("SOURCE MANIFEST:")
print("=" * 80)
cursor.execute("SELECT value FROM meta WHERE key='source_manifest'")
row = cursor.fetchone()
if row: print(row[0])

# 2. Check if AGENTS.md or CLAUDE.md or llms.txt exist in docs
print("\n" + "=" * 80)
print("ROOT-LEVEL DOCS (source_path matches root files):")
print("=" * 80)
cursor.execute("""SELECT id, title, source_path, doc_type, word_count, bluf 
FROM documents 
WHERE source_path IN ('AGENTS.md', 'CLAUDE.md', 'llms.txt') 
   OR source_path LIKE 'contracts/%'
   OR source_path LIKE 'artifacts/%'
   OR source_path LIKE 'braided%'
   OR source_path LIKE 'hfo_pointers%'
ORDER BY source_path""")
for row in cursor.fetchall():
    print(f"\n  [{row[0]}] {row[2]}")
    print(f"    title: {row[1]}")
    print(f"    type: {row[3]}, words: {row[4]}")
    bluf = str(row[5])[:200] if row[5] else "None"
    print(f"    bluf: {bluf}")

# 3. Get content of AGENTS.md and CLAUDE.md from the database
print("\n" + "=" * 80)
print("AGENTS.MD CONTENT (from DB):")
print("=" * 80)
cursor.execute("SELECT content FROM documents WHERE source_path = 'AGENTS.md'")
row = cursor.fetchone()
if row: print(row[0][:3000])

print("\n" + "=" * 80)
print("CLAUDE.MD CONTENT (from DB):")
print("=" * 80)
cursor.execute("SELECT content FROM documents WHERE source_path = 'CLAUDE.md'")
row = cursor.fetchone()
if row: print(row[0][:3000])

print("\n" + "=" * 80)
print("LLMS.TXT CONTENT (from DB):")
print("=" * 80)
cursor.execute("SELECT content FROM documents WHERE source_path = 'llms.txt'")
row = cursor.fetchone()
if row: print(row[0][:3000])

# 4. P4 port docs about the octree/port structure
print("\n" + "=" * 80)
print("KEY DOCS ABOUT PORTS/OCTREE:")
print("=" * 80)
cursor.execute("""SELECT id, title, bluf, source_path FROM documents 
WHERE (title LIKE '%octree%' OR title LIKE '%port%' OR title LIKE '%OBSIDIAN%')
AND doc_type IN ('reference','explanation','doctrine')
LIMIT 10""")
for row in cursor.fetchall():
    print(f"\n  [{row[0]}] {row[1]}")
    bluf = str(row[2])[:150] if row[2] else "None"
    print(f"    bluf: {bluf}")

conn.close()
