import sqlite3
import hashlib
import json
from datetime import datetime, timezone

db_path = 'hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite'

content = '''# Port 6 Kraken Keeper - Draining & Chunking Spells Reference

## 1. Hunger of Hadar (3rd-Level Conjuration)
The Archetype (Black Box Digestion): The ultimate "digestion" of a legacy system. The acidic environment dissolves the connective tissue, while unseen tentacles rip the architecture into manageable chunks.

## 2. Disintegrate (6th-Level Transmutation)
The Archetype (Atomic Chunking): Stripping away complex, bloated energy bonds and forcing the monolithic architecture to shatter into its smallest, most fundamental, decoupled chunks (dust/microservices).

## 3. Soul Cage (6th-Level Necromancy)
The Archetype (Specification Mining / Devouring Dreams): Trapping the "soul" (core business logic) of a deprecated system. You chunk its remaining energy to power new architecture, and query its "dreams" to extract exact specifications.

## 4. Feeblemind (8th-Level Enchantment)
The Archetype (Abstraction Stripping): Stripping away complex, tangled abstractions and bloated UI. You chunk away the "intelligence" of the system until left with nothing but the raw, primitive state machine.

## 5. Enervation (5th-Level Necromancy)
The Archetype (The Kraken's Tether): Continuous data drain. Establishing a tether (strangler fig pattern) to siphon off logic turn by turn, digesting it into a cleanroom environment until the old system is an empty husk.

## 6. Vampiric Touch (3rd-Level Necromancy)
The Archetype (Iterative Extraction): Manual, chunk-by-chunk digestion. Diving into the codebase, grabbing a specific module, violently draining its core capability, and absorbing that logic.

## 7. Abi-Dalzims Horrid Wilting (8th-Level Necromancy)
The Archetype (Draining the Trigram Lake): Evaporating the bloat. Draining the "water" out of the system, stripping away the fluid, chaotic mess and leaving behind only the desiccated, hard, dry business rules.

## 8. Time Ravage (9th-Level Necromancy)
The Archetype (Deprecation Drain): Draining the lifecycle of the legacy system. Forcing a massive monolith into immediate end-of-life deprecation, stripping away its operational runway.

## 9. Ravenous Void (9th-Level Evocation)
The Archetype (The Abyssal Siphon): Massive environmental drain. Creating a black hole that violently sucks in all bloated code, dependencies, and data, crushing it down into a single, dense point of raw energy.

## 10. Magic Jar (6th-Level Necromancy)
The Archetype (The Strangler Fig / API Hijack): Hollowing out the entity. Trapping the legacy system's messy internal logic in a container, while new clean code pilots its external APIs and integrations.

## 11. Imprisonment: Minimus Containment (9th-Level Abjuration)
The Archetype (Absolute Containerization): Shrinking a monolithic entity and trapping it in a perfect, isolated container (Dockerized gem) to extract its logic at leisure.

## 12. Karsus's Avatar (12th-Level Lore Spell)
The Archetype (The Root Override): The ultimate divine-rank drain. Targeting the root dependency of the entire ecosystem, siphoning its core capabilities, and replacing it to become the new master node.
'''

content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

doc = {
    "title": "Port 6 Kraken Keeper - Draining & Chunking Spells Reference",
    "bluf": "A collection of RAW D&D 5e spells mapped to the Port 6 Kraken Keeper archetype of Architecture Recovery, Specification Mining, and legacy system digestion.",
    "source": "memory",
    "port": "P6",
    "medallion": "bronze",
    "doc_type": "reference",
    "content_hash": content_hash,
    "tags": "port6, kraken_keeper, spells, architecture_recovery, specification_mining, dnd",
    "metadata_json": json.dumps({"created_at": datetime.now(timezone.utc).isoformat()}),
    "content": content
}

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute('''
        INSERT INTO documents (title, bluf, source, port, medallion, doc_type, content_hash, tags, metadata_json, content)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (doc["title"], doc["bluf"], doc["source"], doc["port"], doc["medallion"], doc["doc_type"], doc["content_hash"], doc["tags"], doc["metadata_json"], doc["content"]))
    
    doc_id = cursor.lastrowid
    
    cursor.execute('''
        INSERT INTO documents_fts (rowid, title, bluf, content, tags)
        VALUES (?, ?, ?, ?, ?)
    ''', (doc_id, doc["title"], doc["bluf"], doc["content"], doc["tags"]))
    
    conn.commit()
    print(f"Successfully inserted document ID {doc_id} into SSOT.")
except sqlite3.IntegrityError:
    print("Document already exists (hash collision).")
finally:
    conn.close()
