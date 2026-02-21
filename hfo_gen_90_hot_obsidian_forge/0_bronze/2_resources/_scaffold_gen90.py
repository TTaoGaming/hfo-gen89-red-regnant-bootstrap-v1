import os
import shutil
import sqlite3
from pathlib import Path

def scaffold_gen90():
    print("=== SCAFFOLDING HFO GEN 90 ===")
    
    root_dir = Path("C:/hfoDev")
    gen90_dir = root_dir / "hfo_gen_90_hot_obsidian_forge"
    
    medallions = ["0_bronze", "1_silver", "2_gold", "3_hyper_fractal_obsidian"]
    para_dirs = ["0_archives", "1_areas", "2_projects", "3_resources"]
    
    # 1. Scaffold Gen90 structure
    for medallion in medallions:
        for para in para_dirs:
            dir_path = gen90_dir / medallion / para
            dir_path.mkdir(parents=True, exist_ok=True)
            # Create a .gitkeep to ensure empty directories are tracked
            (dir_path / ".gitkeep").touch()
            print(f"Created: {dir_path}")

    print("=== GEN 90 SCAFFOLDING COMPLETE ===")

def port_gen89_to_gen90_bronze():
    print("=== PORTING GEN 89 SSOT TO GEN 90 BRONZE ===")
    
    root_dir = Path("C:/hfoDev")
    gen89_ssot_path = root_dir / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
    gen90_bronze_dir = root_dir / "hfo_gen_90_hot_obsidian_forge" / "0_bronze"
    
    if not gen89_ssot_path.exists():
        print(f"WARNING: Gen89 SSOT not found at {gen89_ssot_path}")
        return

    dest_archive = gen90_bronze_dir / "0_archives" / "gen89_legacy"
    dest_archive.mkdir(parents=True, exist_ok=True)
    
    dest_file = dest_archive / "hfo_gen89_ssot.sqlite"
    
    print(f"Copying {gen89_ssot_path} to {dest_file}...")
    
    try:
        shutil.copy2(str(gen89_ssot_path), str(dest_file))
        # Freeze the file (make it read-only)
        os.chmod(str(dest_file), 0o444)
        print("Porting and freezing complete.")
    except Exception as e:
        print(f"Error during porting: {e}")

def init_gen90_ssot():
    print("=== INITIALIZING GEN 90 SSOT ===")
    
    root_dir = Path("C:/hfoDev")
    gen90_gold_res = root_dir / "hfo_gen_90_hot_obsidian_forge" / "2_gold" / "3_resources"
    gen90_gold_res.mkdir(parents=True, exist_ok=True)
    
    db_path = gen90_gold_res / "hfo_gen90_ssot.sqlite"
    
    if db_path.exists():
        print(f"SSOT already exists at {db_path}")
        return
        
    print(f"Creating new SSOT at {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Basic schema for the new SSOT
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            bluf TEXT,
            source TEXT,
            port TEXT,
            doc_type TEXT,
            medallion TEXT,
            tags TEXT,
            word_count INTEGER,
            content_hash TEXT UNIQUE,
            source_path TEXT,
            content TEXT,
            metadata_json TEXT
        );
        
        CREATE TABLE IF NOT EXISTS stigmergy_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            source TEXT,
            subject TEXT,
            data_json TEXT,
            content_hash TEXT NOT NULL UNIQUE
        );
        
        -- FTS5 Virtual Table
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
            title, bluf, content, tags,
            content='documents', content_rowid='id'
        );
        
        -- Triggers to keep FTS updated
        CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
            INSERT INTO documents_fts(rowid, title, bluf, content, tags)
            VALUES (new.id, new.title, new.bluf, new.content, new.tags);
        END;
        
        CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, bluf, content, tags)
            VALUES('delete', old.id, old.title, old.bluf, old.content, old.tags);
        END;
        
        CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, title, bluf, content, tags)
            VALUES('delete', old.id, old.title, old.bluf, old.content, old.tags);
            INSERT INTO documents_fts(rowid, title, bluf, content, tags)
            VALUES (new.id, new.title, new.bluf, new.content, new.tags);
        END;
    ''')
    
    # Insert initial meta data
    cursor.execute("INSERT INTO meta (key, value) VALUES (?, ?)", 
                   ("generation", "90"))
    cursor.execute("INSERT INTO meta (key, value) VALUES (?, ?)", 
                   ("created_at", "2026-02-20"))
    
    conn.commit()
    conn.close()
    print("Gen 90 SSOT initialized.")

if __name__ == "__main__":
    scaffold_gen90()
    port_gen89_to_gen90_bronze()
    init_gen90_ssot()
