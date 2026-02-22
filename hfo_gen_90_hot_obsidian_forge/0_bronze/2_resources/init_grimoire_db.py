import sqlite3
import json
import os

# ------------------------------------------------------------------------
# HFO Gen90 - Grimoire Initialization
# ------------------------------------------------------------------------
# Creates the hfo_grimoire table in the SSOT database and populates it
# with the 4 Epic Spell Functional Capacity Archetypes (FCAs) that map
# to the Universal Darwinism / MAP-Elites breeding process.
# ------------------------------------------------------------------------

DB_PATH = "hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite"

def init_grimoire():
    if not os.path.exists(DB_PATH):
        print(f"[!] Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("[*] Creating hfo_grimoire table...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS hfo_grimoire (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        spell_name TEXT NOT NULL,
        dnd_seed TEXT NOT NULL,
        fca_archetype TEXT NOT NULL,
        hfo_mapping TEXT NOT NULL,
        medallion_layer TEXT DEFAULT 'bronze',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # The 4 Epic Spells mapping to Universal Darwinism
    spells = [
        (
            "Origin of Species: Achaierai",
            "Life + Conjure",
            "The Mutator / Variation Engine",
            "MAP-Elites Breeder Script. Takes an existing exemplar, applies genetic crossover and mutation along phenotypic axes, and spawns a new generation of software mutants. Engine of Variation."
        ),
        (
            "Genesis",
            "Conjure",
            "The Fitness Landscape / SPLENDOR Grid",
            "MAP-Elites Grid and Eval Harness (Stryker/promptfoo). Building the isolated, high-pressure environment where mutants must survive. Sets strict environmental constraints that apply Selection pressure."
        ),
        (
            "Epic Polymorph / True Shapechange",
            "Transform",
            "The Pareto Frontier Optimizer",
            "Quality-Diversity / Pareto Frontier aspect of MAP-Elites. Fluidly adapting the codebase to perfectly fill every cell of the phenotypic grid for highly-specialized survival niches."
        ),
        (
            "Animus Blast / Epic Awaken",
            "Life + Fortify",
            "The Spark of Heredity",
            "Injection of the PREY8 Loop (Perceive -> React -> Execute -> Yield) into static exemplars. Grants the capacity for Heredity (writing to stigmergy trail). Awakens dead code into a living participant in the Universal Darwinism engine."
        )
    ]

    print("[*] Populating table with Epic Spell FCAs...")
    
    # Check if they already exist to avoid duplicates
    cursor.execute("SELECT COUNT(*) FROM hfo_grimoire")
    count_before = cursor.fetchone()[0]
    
    if count_before == 0:
        cursor.executemany('''
        INSERT INTO hfo_grimoire (spell_name, dnd_seed, fca_archetype, hfo_mapping)
        VALUES (?, ?, ?, ?)
        ''', spells)
        conn.commit()
        print(f"[+] Successfully inserted {len(spells)} spells into hfo_grimoire table.")
    else:
        print(f"[*] Table already contains {count_before} records. Skipping initial population to avoid duplicates.")

    # Verify
    cursor.execute("SELECT id, spell_name, fca_archetype FROM hfo_grimoire")
    rows = cursor.fetchall()
    print("\n--- HFO Grimoire Contents ---")
    for row in rows:
        print(f"[{row[0]}] {row[1]} -> {row[2]}")

    conn.close()

if __name__ == "__main__":
    init_grimoire()
