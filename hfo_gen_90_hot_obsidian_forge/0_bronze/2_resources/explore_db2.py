import sqlite3
import json

conn = sqlite3.connect(r'c:\hfoDev\hfo_gen90_ssot.sqlite')
cursor = conn.cursor()

# 1. All meta keys
print("=" * 80)
print("META TABLE (all rows):")
print("=" * 80)
cursor.execute("SELECT key, value FROM meta ORDER BY key")
for row in cursor.fetchall():
    val = str(row[1])
    if len(val) > 200:
        val = val[:200] + "..."
    print(f"  {row[0]:40s} = {val}")

# 2. Document sources breakdown
print("\n" + "=" * 80)
print("DOCUMENTS BY SOURCE:")
print("=" * 80)
cursor.execute("SELECT source, COUNT(*), SUM(word_count) FROM documents GROUP BY source ORDER BY COUNT(*) DESC")
for row in cursor.fetchall():
    print(f"  {str(row[0]):35s}  {row[1]:6,} docs   {row[2] or 0:>10,} words")

# 3. Document types breakdown
print("\n" + "=" * 80)
print("DOCUMENTS BY DOC_TYPE:")
print("=" * 80)
cursor.execute("SELECT doc_type, COUNT(*) FROM documents GROUP BY doc_type ORDER BY COUNT(*) DESC")
for row in cursor.fetchall():
    print(f"  {str(row[0]):35s}  {row[1]:6,} docs")

# 4. Medallion breakdown
print("\n" + "=" * 80)
print("DOCUMENTS BY MEDALLION:")
print("=" * 80)
cursor.execute("SELECT medallion, COUNT(*) FROM documents GROUP BY medallion ORDER BY COUNT(*) DESC")
for row in cursor.fetchall():
    print(f"  {str(row[0]):35s}  {row[1]:6,} docs")

# 5. Port breakdown
print("\n" + "=" * 80)
print("DOCUMENTS BY PORT:")
print("=" * 80)
cursor.execute("SELECT port, COUNT(*) FROM documents GROUP BY port ORDER BY COUNT(*) DESC")
for row in cursor.fetchall():
    print(f"  {str(row[0]):35s}  {row[1]:6,} docs")

# 6. Stigmergy event types
print("\n" + "=" * 80)
print("STIGMERGY EVENTS BY TYPE:")
print("=" * 80)
cursor.execute("SELECT event_type, COUNT(*) FROM stigmergy_events GROUP BY event_type ORDER BY COUNT(*) DESC")
for row in cursor.fetchall():
    print(f"  {str(row[0]):50s}  {row[1]:6,}")

# 7. Timestamp range
print("\n" + "=" * 80)
print("TEMPORAL RANGE:")
print("=" * 80)
cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM stigmergy_events")
row = cursor.fetchone()
print(f"  Stigmergy first: {row[0]}")
print(f"  Stigmergy last:  {row[1]}")
cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM documents WHERE created_at IS NOT NULL")
row = cursor.fetchone()
print(f"  Docs created first: {row[0]}")
print(f"  Docs created last:  {row[1]}")

# 8. Total word count
print("\n" + "=" * 80)
print("AGGREGATE STATS:")
print("=" * 80)
cursor.execute("SELECT COUNT(*), SUM(word_count), AVG(word_count), MIN(word_count), MAX(word_count) FROM documents")
row = cursor.fetchone()
print(f"  Total documents:  {row[0]:,}")
print(f"  Total words:      {row[1]:,}")
print(f"  Avg words/doc:    {row[2]:,.0f}")
print(f"  Min words:        {row[3]:,}")
print(f"  Max words:        {row[4]:,}")

# 9. Tag frequency (top 30)
print("\n" + "=" * 80)
print("TOP 30 TAGS:")
print("=" * 80)
cursor.execute("SELECT tags FROM documents WHERE tags IS NOT NULL")
tag_counts = {}
for row in cursor.fetchall():
    for tag in row[0].split(','):
        tag = tag.strip()
        if tag:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
sorted_tags = sorted(tag_counts.items(), key=lambda x: -x[1])[:30]
for tag, count in sorted_tags:
    print(f"  {tag:45s}  {count:6,}")

# 10. Unique source_paths structure (first 20)
print("\n" + "=" * 80)
print("SOURCE PATH PREFIXES (top-level folders):")
print("=" * 80)
cursor.execute("SELECT source_path FROM documents WHERE source_path IS NOT NULL")
prefixes = {}
for row in cursor.fetchall():
    parts = row[0].split('/')
    if len(parts) >= 2:
        prefix = parts[0] + '/' + parts[1]
    else:
        prefix = parts[0]
    prefixes[prefix] = prefixes.get(prefix, 0) + 1
for prefix, count in sorted(prefixes.items(), key=lambda x: -x[1])[:25]:
    print(f"  {prefix:55s}  {count:6,}")

conn.close()
