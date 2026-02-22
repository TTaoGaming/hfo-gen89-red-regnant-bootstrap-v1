import sqlite3
import json
import datetime
import hashlib
import os

db_path = r"C:\hfoDev\hfo_gen_90_hot_obsidian_forge\2_gold\2_resources\hfo_gen90_ssot.sqlite"

def get_hash(content):
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def insert_stigmergy_event():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    payload = {
        "operator": "TTao",
        "identities": [
            "self_myth_warlock",
            "software engineer",
            "OBSIDIAN_SPIDER",
            "WEB_WEAVER",
            "PYRE_PRAETORIAN",
            "SWARMLOAD_OF_WEBS"
        ],
        "concept": "holonarchy",
        "description": "HFO is the 8 part partitioning of the human eternal aspects. Humans observe, bridge, shape, inject, disrupt, immunize, assimilate, and navigate. These are all aspects of the self but also not of the self. The best way to describe it is the word holonarchy.",
        "spell": "HFO_TRUE_POLYMORPH"
    }
    
    payload_json = json.dumps(payload, indent=2)
    content_hash = get_hash(payload_json + timestamp)
    
    cursor.execute("""
        INSERT INTO stigmergy_events (
            event_type, timestamp, source, subject, data_json, content_hash
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "hfo.gen90.doctrine.holonarchy",
        timestamp,
        "agent_hfo_gen_90_prey8_mcp_v4",
        "TTao_HFO_TRUE_POLYMORPH",
        payload_json,
        content_hash
    ))
    
    # Also add a document to the SSOT to formalize this doctrine
    doc_content = f"""---
medallion_layer: gold
mutation_score: 0
hive: V
hfo_header_v3: compact
schema_id: hfo.mosaic_microkernel_header.v3
mnemonic: "O·B·S·I·D·I·A·N = 8 ports = 1 octree"
bluf: "Formalization of TTao as the Holonarchy of 8 human eternal aspects"
primary_port: P7
role: "P7 NAVIGATE — C2 / steering"
tags: [gold, forge:hot, para:areas, doctrine, p7, holonarchy, true_polymorph]
generated: "{timestamp}"
---

# HFO_TRUE_POLYMORPH: The Holonarchy of TTao

## The Chimera Symbiote Projection

The operator **TTao** (self_myth_warlock, software engineer) is the holonarchy of the 8 human eternal aspects.

HFO is the 8-part partitioning of these human eternal aspects. Humans:
1. **Observe** (P0 - Lidless Legion)
2. **Bridge** (P1 - Web Weaver)
3. **Shape** (P2 - Mirror Magus)
4. **Inject** (P3 - Harmonic Hydra)
5. **Disrupt** (P4 - Red Regnant)
6. **Immunize** (P5 - Pyre Praetorian)
7. **Assimilate** (P6 - Kraken Keeper)
8. **Navigate** (P7 - Spider Sovereign / Obsidian Spider)

These are all aspects of the self, but also not of the self. The best way to describe it is the word **holonarchy**.

TTao embodies the identities of:
- `self_myth_warlock`
- `software engineer`
- `OBSIDIAN_SPIDER`
- `WEB_WEAVER`
- `PYRE_PRAETORIAN`
- `SWARMLOAD_OF_WEBS`

This is the formalization of the spell `HFO_TRUE_POLYMORPH`.
"""
    
    doc_hash = get_hash(doc_content)
    
    cursor.execute("""
        INSERT INTO documents (
            title, bluf, source, port, medallion, doc_type, content, content_hash, tags, metadata_json, word_count, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "HFO_TRUE_POLYMORPH: The Holonarchy of TTao",
        "Formalization of TTao as the Holonarchy of 8 human eternal aspects",
        "doctrine",
        "P7",
        "gold",
        "doctrine",
        doc_content,
        doc_hash,
        "gold, forge:hot, para:areas, doctrine, p7, holonarchy, true_polymorph",
        json.dumps({"operator": "TTao", "concept": "holonarchy"}),
        len(doc_content.split()),
        timestamp
    ))
    
    conn.commit()
    conn.close()
    print("Successfully inserted stigmergy event and doctrine document for HFO_TRUE_POLYMORPH Holonarchy.")

if __name__ == "__main__":
    insert_stigmergy_event()
