"""
SW-5 Promotion Gate: Bronze → Hyper Fractal Obsidian (Layer 3)

Promotes SONGS_OF_SPLENDOR and SONGS_OF_STRIFE catalogs to the meta-architectural
layer. These are the highest-level abstractions of the entire HFO system —
the YIN/YANG ledger of patterns — and belong in 3_hyper_fractal_obsidian.

Promotion criteria met:
  - SONGS_OF_SPLENDOR: 85 tokens, 35/35 tests passing, source-doc-traced
  - SONGS_OF_STRIFE:   30 tokens, 34/34 tests passing, SSOT ingested as doc 9870
  - Both: human operator explicitly requested promotion gate
"""

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("c:/hfoDev")
DB = ROOT / "hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite"
DEST_DIR = ROOT / "hfo_gen_90_hot_obsidian_forge/3_hyper_fractal_obsidian/2_resources"
DEST_DIR.mkdir(parents=True, exist_ok=True)

NOW = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

CATALOG_DEFS = [
    {
        "bronze_path": ROOT / "hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/SONGS_OF_STRIFE_ANTIPATTERN_CATALOG.md",
        "hfo_filename": "SONGS_OF_STRIFE_ANTIPATTERN_CATALOG.hfo_meta.md",
        "new_schema_id": "hfo.gen90.songs_of_strife.hfo_meta.v1",
        "title_key": "REFERENCE_P4_SONGS_OF_STRIFE_ANTIPATTERN_CATALOG_HFO_META",
        "bluf": "SONGS OF STRIFE — HFO meta-layer antipattern catalog. 30 named STRIFE tokens (BREACH, Book-of-Blood GRUDGEs, SDD Stack GRUDGEs, E50 Heuristics). Primary vector defense reference. Promoted to Hyper Fractal Obsidian as a foundational system abstraction.",
        "tests": "34/34",
        "tokens": 30,
        "port": "P4",
    },
    {
        "bronze_path": ROOT / "hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/SONGS_OF_SPLENDOR_EXEMPLAR_CATALOG.md",
        "hfo_filename": "SONGS_OF_SPLENDOR_EXEMPLAR_CATALOG.hfo_meta.md",
        "new_schema_id": "hfo.gen90.songs_of_splendor.hfo_meta.v1",
        "title_key": "REFERENCE_P4_SONGS_OF_SPLENDOR_EXEMPLAR_CATALOG_HFO_META",
        "bluf": "SONGS OF SPLENDOR — HFO meta-layer exemplar catalog. 85 named SPLENDOR tokens (S001-S085) across 9 tiers — proven patterns that survived 14 months of solo HFO development. Promoted to Hyper Fractal Obsidian as a foundational system abstraction.",
        "tests": "35/35",
        "tokens": 85,
        "port": "P4",
    },
]

PROMOTION_BLOCK = (
    "promoted_to: hyper_fractal_obsidian\n"
    f"promoted_at: \"{NOW}\"\n"
    "promotion_gate: \"SW-5 explicit operator request — foundational system abstraction\"\n"
    "promotion_evidence: \"All tests passing, source-doc-traced, 14 months production survival\"\n"
    "bronze_origin: true\n"
)


def update_frontmatter(content: str, new_schema_id: str) -> str:
    """Replace medallion_layer and schema_id in YAML frontmatter, then inject promotion block."""
    content = re.sub(
        r"(medallion_layer:\s*)bronze",
        r"\1hyper_fractal_obsidian",
        content,
        count=1,
    )
    content = re.sub(
        r"(schema_id:\s*)\S+",
        rf"\g<1>{new_schema_id}",
        content,
        count=1,
    )
    # Inject promotion block before the closing ---
    content = re.sub(
        r"^(---\s*\n)(# )",
        rf"\g<1>{PROMOTION_BLOCK}---\n\n\g<2>",
        content,
        count=1,
        flags=re.MULTILINE,
    )
    return content


results = []
conn = sqlite3.connect(DB)
cur = conn.cursor()

for defn in CATALOG_DEFS:
    src = defn["bronze_path"]
    dst = DEST_DIR / defn["hfo_filename"]

    print(f"\n── Promoting {src.name} → {dst.relative_to(ROOT)}")

    raw = src.read_text(encoding="utf-8")
    promoted = update_frontmatter(raw, defn["new_schema_id"])

    # Write promoted copy
    dst.write_text(promoted, encoding="utf-8")
    print(f"   Written: {dst}")

    # Hash
    content_hash = hashlib.sha256(promoted.encode()).hexdigest()

    # Ingest into SSOT (skip if already present)
    cur.execute("SELECT id FROM documents WHERE content_hash = ?", (content_hash,))
    row = cur.fetchone()
    if row:
        print(f"   Already in SSOT as doc {row[0]}")
        doc_id = row[0]
    else:
        cur.execute(
            """
            INSERT INTO documents
              (source, source_path, content, content_hash, title, bluf, doc_type,
               port, medallion, tags, created_at, ingested_at, word_count)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "config",
                str(dst.relative_to(ROOT)).replace("\\", "/"),
                promoted,
                content_hash,
                defn["title_key"],
                defn["bluf"],
                "reference",
                defn["port"],
                "hyper_fractal_obsidian",
                f"hfo_meta,songs,{defn['port'].lower()},exemplar,promoted",
                NOW,
                NOW,
                len(promoted.split()),
            ),
        )
        doc_id = cur.lastrowid
        print(f"   Ingested as doc {doc_id}")

    # Stigmergy event
    evt_data = json.dumps({
        "doc_id": doc_id,
        "catalog": defn["title_key"],
        "tokens": defn["tokens"],
        "tests": defn["tests"],
        "schema_id": defn["new_schema_id"],
        "promoted_from": "bronze",
        "promoted_to": "hyper_fractal_obsidian",
        "promotion_gate": "SW-5",
        "bronze_origin": str(src.relative_to(ROOT)).replace("\\", "/"),
    })
    evt_hash = hashlib.sha256(evt_data.encode()).hexdigest()
    cur.execute("SELECT id FROM stigmergy_events WHERE content_hash = ?", (evt_hash,))
    if cur.fetchone():
        print("   Stigmergy already logged.")
    else:
        cur.execute(
            """
            INSERT INTO stigmergy_events
              (event_type, timestamp, source, subject, data_json, content_hash)
            VALUES (?,?,?,?,?,?)
            """,
            (
                "hfo.gen90.p7.songs.promotion.hfo_meta",
                NOW,
                "p7_spider_sovereign",
                defn["title_key"],
                evt_data,
                evt_hash,
            ),
        )
        print(f"   Stigmergy logged ({evt_hash[:12]})")

    results.append({"catalog": defn["hfo_filename"], "doc_id": doc_id, "hash": content_hash[:12]})

conn.commit()
conn.close()

print("\n══ PROMOTION COMPLETE ══")
for r in results:
    print(f"  {r['catalog']} → SSOT doc {r['doc_id']} (hash {r['hash']})")
print(f"\nDestination: {DEST_DIR.relative_to(ROOT)}")
print("Medallion:   hyper_fractal_obsidian")
print("Gate:        SW-5 explicit operator request")
