"""Ingest SONGS_OF_STRIFE catalog into SSOT and emit stigmergy event."""
import sqlite3
import hashlib
import json
from datetime import datetime
from pathlib import Path

DB = Path("hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite")
CATALOG = Path("hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/SONGS_OF_STRIFE_ANTIPATTERN_CATALOG.md")

content = CATALOG.read_text(encoding="utf-8")
h = hashlib.sha256(content.encode()).hexdigest()

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Check for duplicate
cur.execute("SELECT id FROM documents WHERE content_hash = ?", (h,))
row = cur.fetchone()
if row:
    print(f"Already ingested as doc {row['id']}. Skipping document insert.")
    doc_id = row["id"]
else:
    cur.execute("""
        INSERT INTO documents
          (source, source_path, content, content_hash, title, bluf, doc_type, port, medallion, tags, created_at, ingested_at, word_count)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        "p4_payload",
        str(CATALOG),
        content,
        h,
        "REFERENCE_P4_SONGS_OF_STRIFE_ANTIPATTERN_CATALOG_2026_02_21",
        "Formal machine-readable antipattern catalog: 30 STRIFE tokens across BREACH, Book-of-Blood GRUDGEs, SDD Stack GRUDGEs, and E50 Heuristics. Primary vector defense reference for P4 DISRUPT.",
        "reference",
        "P4",
        "bronze",
        "strife,grudge,book-of-blood,e50,heuristics,antipatterns,p4,breach,reward-hacking,test-theater",
        datetime.utcnow().isoformat() + "Z",
        datetime.utcnow().isoformat() + "Z",
        len(content.split()),
    ))
    doc_id = cur.lastrowid
    print(f"Ingested as doc {doc_id}")

# Emit stigmergy event
evt_data = json.dumps({
    "doc_id": doc_id,
    "catalog": "SONGS_OF_STRIFE_ANTIPATTERN_CATALOG",
    "tokens": 30,
    "registries": {
        "BREACH": 1,
        "book_of_blood_grudges": 8,
        "sdd_stack_grudges": 9,
        "e50_heuristics": 12,
    },
    "tests": "34/34 passing",
    "source_docs": [177, 120, 398, 687, 7673, 7855, 175],
    "schema_id": "hfo.gen90.songs_of_strife.v1",
})
evt_hash = hashlib.sha256(evt_data.encode()).hexdigest()

cur.execute("SELECT id FROM stigmergy_events WHERE content_hash = ?", (evt_hash,))
if cur.fetchone():
    print("Stigmergy event already logged.")
else:
    cur.execute("""
        INSERT INTO stigmergy_events (event_type, timestamp, source, subject, data_json, content_hash)
        VALUES (?,?,?,?,?,?)
    """, (
        "hfo.gen90.p4.songs_strife.catalog_created",
        datetime.utcnow().isoformat() + "Z",
        "p7_spider_sovereign",
        "SONGS_OF_STRIFE_ANTIPATTERN_CATALOG",
        evt_data,
        evt_hash,
    ))
    print(f"Stigmergy event logged (hash prefix: {evt_hash[:12]})")

conn.commit()
conn.close()
print("Done.")
