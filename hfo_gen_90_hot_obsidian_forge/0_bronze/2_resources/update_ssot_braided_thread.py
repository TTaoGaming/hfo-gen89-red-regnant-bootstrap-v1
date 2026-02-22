import sqlite3
import json
import os
import sys
import datetime
import hashlib

def resolve_pointer(key):
    # Simple resolution for now, assuming standard path
    if key == 'ssot.db':
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '../../2_gold/2_resources/hfo_gen90_ssot.sqlite'))
    return None

db_path = resolve_pointer('ssot.db')
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    sys.exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# We need to add a document or stigmergy event for the braided mission thread notes.
# Let's add a document.
title = "Braided Mission Thread Notes: Exocortical Bootloader"
bluf = "Notes on the Exocortical Bootloader and its integration into the braided mission thread."
content = """
# Braided Mission Thread Notes: Exocortical Bootloader

The Exocortical Bootloader is a critical component of the braided mission thread, specifically designed to align the Alpha (infrastructure/governance) and Omega (gesture control plane) threads.

## Key Integration Points:
1. **Temporal Foresight Rollout**: Ensures that Omega phase developments do not fall into local minima (Green Lies) by enforcing a temporal rollout evaluation.
2. **Meadows Sphere Ascension**: Forces the AI agent to pop up and out of parameter tuning to evaluate structural rules and system paradigms, aligning with the Alpha thread's governance.
3. **Semantic Hash Anchors**: Locks the latent space to prevent conversational entropy, ensuring the agent remains focused on the braided mission thread's core concepts (e.g., Second-Order Cybernetics, Social Spider Swarm).

This bootloader acts as the state transfer payload between stateless LLM sessions, preserving the thermodynamic integrity of the architecture.
"""

source = "memory"
port = "P6"
medallion = "bronze"
doc_type = "explanation"
tags = "braided_mission_thread, exocortical_bootloader, omega, alpha, handoff"

# Generate content hash
content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

metadata = {
    "medallion_layer": medallion,
    "mutation_score": 0,
    "hive": "V",
    "hfo_header_v3": "compact",
    "schema_id": "hfo.mosaic_microkernel_header.v3",
    "mnemonic": "O·B·S·I·D·I·A·N = 8 ports = 1 octree",
    "bluf": bluf,
    "primary_port": port,
    "role": "P6 ASSIMILATE — knowledge/documentation",
    "tags": [t.strip() for t in tags.split(',')]
}

try:
    cursor.execute('''
        INSERT INTO documents (title, bluf, source, port, medallion, doc_type, content, content_hash, tags, metadata_json, ingested_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (title, bluf, source, port, medallion, doc_type, content, content_hash, tags, json.dumps(metadata), datetime.datetime.now(datetime.timezone.utc).isoformat()))
    
    doc_id = cursor.lastrowid
    
    # Also insert into FTS
    cursor.execute('''
        INSERT INTO documents_fts (rowid, title, bluf, content, tags)
        VALUES (?, ?, ?, ?, ?)
    ''', (doc_id, title, bluf, content, tags))
    
    conn.commit()
    print(f"Successfully inserted document with ID {doc_id}")
except sqlite3.IntegrityError as e:
    print(f"Integrity error (possibly duplicate content hash): {e}")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
