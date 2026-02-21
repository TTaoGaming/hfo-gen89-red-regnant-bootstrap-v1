import os
import shutil
import json
import re

def demote_forge():
    base_dir = "hfo_gen_89_hot_obsidian_forge"
    bronze_dir = os.path.join(base_dir, "0_bronze")
    
    demoted_silver = os.path.join(bronze_dir, "demoted_silver")
    demoted_gold = os.path.join(bronze_dir, "demoted_gold")
    demoted_hfo = os.path.join(bronze_dir, "demoted_hfo")
    
    os.makedirs(demoted_silver, exist_ok=True)
    os.makedirs(demoted_gold, exist_ok=True)
    os.makedirs(demoted_hfo, exist_ok=True)
    
    # Move contents of 1_silver
    silver_dir = os.path.join(base_dir, "1_silver")
    if os.path.exists(silver_dir):
        for item in os.listdir(silver_dir):
            src = os.path.join(silver_dir, item)
            dst = os.path.join(demoted_silver, item)
            shutil.move(src, dst)
            
    # Move contents of 2_gold
    gold_dir = os.path.join(base_dir, "2_gold")
    if os.path.exists(gold_dir):
        for item in os.listdir(gold_dir):
            src = os.path.join(gold_dir, item)
            dst = os.path.join(demoted_gold, item)
            shutil.move(src, dst)
            
    # Move contents of 3_hyper_fractal_obsidian
    hfo_dir = os.path.join(base_dir, "3_hyper_fractal_obsidian")
    if os.path.exists(hfo_dir):
        for item in os.listdir(hfo_dir):
            src = os.path.join(hfo_dir, item)
            dst = os.path.join(demoted_hfo, item)
            shutil.move(src, dst)
            
    # Update pointers
    pointers_file = "hfo_gen89_pointers_blessed.json"
    with open(pointers_file, "r", encoding="utf-8") as f:
        pointers_data = json.load(f)
        
    for key, value in pointers_data.get("pointers", {}).items():
        path = value.get("path", "")
        if "1_silver" in path:
            value["path"] = path.replace("1_silver", "0_bronze/demoted_silver")
        elif "2_gold" in path:
            value["path"] = path.replace("2_gold", "0_bronze/demoted_gold")
        elif "3_hyper_fractal_obsidian" in path:
            value["path"] = path.replace("3_hyper_fractal_obsidian", "0_bronze/demoted_hfo")
            
    with open(pointers_file, "w", encoding="utf-8") as f:
        json.dump(pointers_data, f, indent=2)
        
    # Update .env
    env_file = ".env"
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            env_content = f.read()
            
        env_content = env_content.replace("1_silver", "0_bronze/demoted_silver")
        env_content = env_content.replace("2_gold", "0_bronze/demoted_gold")
        env_content = env_content.replace("3_hyper_fractal_obsidian", "0_bronze/demoted_hfo")
        
        with open(env_file, "w", encoding="utf-8") as f:
            f.write(env_content)
            
    print("Demotion complete. Pointers and .env updated.")

if __name__ == "__main__":
    demote_forge()
