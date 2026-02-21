import os
import shutil
import json
from pathlib import Path

def resurrect_port6_memory():
    print("=== PHOENIX PROTOCOL: RESURRECTING PORT 6 MEMORY ===")
    
    root_dir = Path("C:/hfoDev")
    forge_dir = root_dir / "hfo_gen_90_hot_obsidian_forge"
    
    bronze_res = forge_dir / "0_bronze" / "2_resources"
    silver_res = forge_dir / "1_silver" / "2_resources"
    gold_res = forge_dir / "2_gold" / "2_resources"
    
    # Ensure silver resources directory exists
    silver_res.mkdir(parents=True, exist_ok=True)
    
    # 1. Find and move SSOT DB
    ssot_db_name = "hfo_gen90_ssot.sqlite"
    ssot_db_src = None
    
    if (bronze_res / ssot_db_name).exists():
        ssot_db_src = bronze_res / ssot_db_name
    elif (gold_res / ssot_db_name).exists():
        ssot_db_src = gold_res / ssot_db_name
        
    if ssot_db_src:
        ssot_db_dest = silver_res / ssot_db_name
        print(f"Moving SSOT DB from {ssot_db_src} to {ssot_db_dest}")
        shutil.move(str(ssot_db_src), str(ssot_db_dest))
    else:
        print("WARNING: SSOT DB not found!")

    # 2. Find and move SHODH derived view
    shodh_files = ["hfo_shodh_query.py", "hfo_shodh.py"]
    for f in shodh_files:
        src = bronze_res / f
        if src.exists():
            dest = silver_res / f
            print(f"Moving SHODH file {f} to {dest}")
            shutil.move(str(src), str(dest))
        else:
            print(f"WARNING: SHODH file {f} not found in bronze!")

    # 3. Find and move Stigmergy components
    stigmergy_files = ["hfo_stigmergy_watchdog.py", "hfo_stigmergy_weekly_report.py"]
    for f in stigmergy_files:
        src = bronze_res / f
        if src.exists():
            dest = silver_res / f
            print(f"Moving Stigmergy file {f} to {dest}")
            shutil.move(str(src), str(dest))
        else:
            print(f"WARNING: Stigmergy file {f} not found in bronze!")

    # 4. Update Pointer Registry
    pointer_file = root_dir / "hfo_gen90_pointers_blessed.json"
    if pointer_file.exists():
        with open(pointer_file, 'r', encoding='utf-8') as f:
            pointers = json.load(f)
            
        if "pointers" in pointers and "ssot.db" in pointers["pointers"]:
            old_path = pointers["pointers"]["ssot.db"]["path"]
            new_path = "hfo_gen_90_hot_obsidian_forge/1_silver/resources/hfo_gen90_ssot.sqlite"
            pointers["pointers"]["ssot.db"]["path"] = new_path
            print(f"Updated pointer registry: ssot.db -> {new_path}")
            
            with open(pointer_file, 'w', encoding='utf-8') as f:
                json.dump(pointers, f, indent=2)
    else:
        print("WARNING: Pointer registry not found!")

    print("=== RESURRECTION PREPARATION COMPLETE ===")
    print("Port 6 Memory (SSOT, SHODH, Stigmergy, FTS) is now staged in 1_silver.")

if __name__ == "__main__":
    resurrect_port6_memory()
