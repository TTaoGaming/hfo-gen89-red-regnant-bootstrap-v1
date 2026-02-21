"""Insert the 8^N Octree Revenue Architecture document into SSOT.
One-shot script — run once, then delete.
"""
import sqlite3, hashlib, json, os
from datetime import datetime, timezone

FORGE = "hfo_gen_90_hot_obsidian_forge"
DB = os.path.join(FORGE, "2_gold", "resources", "hfo_gen90_ssot.sqlite")
DOC_FILE = os.path.join(FORGE, "0_bronze", "resources",
    "2026-02-19_REFERENCE_8N_OCTREE_REVENUE_ARCHITECTURE_V1.md")

with open(DOC_FILE, "r", encoding="utf-8") as f:
    content = f.read()

content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
word_count = len(content.split())
now = datetime.now(timezone.utc).isoformat()

metadata = {
    "schema_id": "hfo.diataxis.reference.v1",
    "medallion_layer": "bronze",
    "hive": "V",
    "primary_port": "P3",
    "secondary_ports": ["P0","P1","P2","P4","P5","P6","P7"],
    "author": "Red Regnant P4 (session 5a382eb2ff684c20 + 98341ffce3abe8e9)",
    "date": "2026-02-19",
    "status": "LIVING",
    "prey8_session": "98341ffce3abe8e9",
    "extends": "Doc 7855 braided_mission_thread monetization.streams 6→8",
    "cross_references": [
        "Doc 7855: braided_mission_thread_alpha_omega_hfo_gen89v8",
        "Doc 56: REFERENCE_FREEMIUM_MONETIZATION_IMPLEMENTATION_SPEC",
        "Doc 44: Clone/Fork/Evolve App Catalog",
        "Doc 112: Omega Launch Thread GTM FSM",
        "Doc 253: Omega Gen8 GTM Analysis",
        "Doc 205: Mission Thread Omega",
        "Doc 317: EXPLANATION_WHAT_HFO_ACTUALLY_IS",
        "Doc 129: Octree port-pair mapping"
    ]
}

conn = sqlite3.connect(DB)
cur = conn.cursor()

# Check for duplicate content hash
cur.execute("SELECT id FROM documents WHERE content_hash = ?", (content_hash,))
existing = cur.fetchone()
if existing:
    print(f"DUPLICATE: content_hash already exists as doc {existing[0]}. Skipping INSERT.")
    conn.close()
    exit(0)

cur.execute("""
    INSERT INTO documents (
        source, source_path, content, content_hash, title, bluf, doc_type,
        port, medallion, tags, created_at, ingested_at, word_count, metadata_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    "diataxis",
    "hfo_gen_90_hot_obsidian_forge/0_bronze/resources/2026-02-19_REFERENCE_8N_OCTREE_REVENUE_ARCHITECTURE_V1.md",
    content,
    content_hash,
    "8^N Octree Revenue Architecture — O·B·S·I·D·I·A·N Revenue Topology",
    "8^N Octree Revenue Architecture mapping each HFO port to a passive monetization stream. "
    "The octree IS the business model — 8 ports × 8 variants × 8 tactics = 512+ revenue paths. "
    "Extends braided mission thread (Doc 7855) monetization.streams from 6→8. "
    "Core mechanisms: P3 viral watermark always-on, P5 gamified challenge dismissal, "
    "P6 battle pass → loot pool, P1 Patreon/Kickstarter patronage bridge. "
    "Never pay-gate features. The architecture markets itself.",
    "reference",
    "P3",
    "bronze",
    "bronze,monetization,8^N,octree,revenue,passive,watermark,battle-pass,loot-pool,"
    "patreon,kickstarter,ko-fi,consultation,cosmetics,gamification,challenge,freemium,"
    "braided-thread-extension",
    "2026-02-19",
    now,
    word_count,
    json.dumps(metadata)
))

new_id = cur.lastrowid
conn.commit()
conn.close()

print(f"SUCCESS: Inserted as document ID {new_id}")
print(f"  title: 8^N Octree Revenue Architecture — O·B·S·I·D·I·A·N Revenue Topology")
print(f"  content_hash: {content_hash}")
print(f"  word_count: {word_count}")
print(f"  medallion: bronze")
print(f"  port: P3")
print(f"  source: diataxis")
print(f"  doc_type: reference")
