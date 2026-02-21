import sqlite3
from pathlib import Path

def demo_readonly_attach():
    root_dir = Path("C:/hfoDev")
    gen90_db_path = root_dir / "hfo_gen_90_hot_obsidian_forge" / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite"
    gen90_db_path = root_dir / "hfo_gen_90_hot_obsidian_forge" / "0_bronze" / "3_archives" / "gen90_legacy" / "hfo_gen90_ssot.sqlite"
    
    print(f"Connecting to Gen 90 SSOT: {gen90_db_path}")
    # Connect to Gen 90 database
    conn = sqlite3.connect(str(gen90_db_path))
    cursor = conn.cursor()
    
    print(f"Attaching Gen 89 SSOT as read-only: {gen90_db_path}")
    # Attach Gen 89 database in read-only mode using URI filename
    # The ?mode=ro ensures that even if the file permissions allow writing, SQLite will treat it as read-only
    attach_query = f"ATTACH DATABASE 'file:{gen90_db_path.as_posix()}?mode=ro' AS gen90;"
    
    # We need to enable URI filenames for the connection to use ?mode=ro
    # In Python's sqlite3, we can just pass uri=True to connect, but for ATTACH, 
    # SQLite handles the URI if it's formatted correctly and URI support is enabled.
    # Actually, it's safer to just connect with uri=True and then attach.
    conn.close()
    
    # Reconnect with URI support enabled
    conn = sqlite3.connect(f"file:{gen90_db_path.as_posix()}", uri=True)
    cursor = conn.cursor()
    
    cursor.execute(attach_query)
    print("Successfully attached Gen 89 database as 'gen90'.")
    
    # Demonstrate querying from both databases
    print("\n--- Querying Gen 90 ---")
    cursor.execute("SELECT key, value FROM meta WHERE key = 'generation'")
    print("Gen 90 meta generation:", cursor.fetchone())
    
    print("\n--- Querying Gen 89 (Read-Only) ---")
    cursor.execute("SELECT COUNT(*) FROM gen90.documents")
    print("Gen 89 document count:", cursor.fetchone()[0])
    
    print("\n--- Attempting to write to Gen 89 (Should Fail) ---")
    try:
        cursor.execute("INSERT INTO gen90.meta (key, value) VALUES ('test_write', 'should_fail')")
    except sqlite3.OperationalError as e:
        print(f"Write failed as expected: {e}")
        
    conn.close()

if __name__ == "__main__":
    demo_readonly_attach()
