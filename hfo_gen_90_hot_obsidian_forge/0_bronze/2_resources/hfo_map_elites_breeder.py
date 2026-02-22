import os
import sys
import json
import time
import subprocess
import sqlite3
from typing import Dict, Any, List, Tuple
import urllib.request
import urllib.error

# ------------------------------------------------------------------------
# HFO Gen90 - MAP-Elites Breeder (P4 Red Regnant)
# ------------------------------------------------------------------------
# This script mutates a base TypeScript file (Genome) along two phenotypic
# dimensions to populate a MAP-Elites grid (SPLENDOR).
# 
# Dimensions:
# X: Aggressiveness (0-10) - How aggressively it optimizes/prunes
# Y: Precision (0-10) - How strictly it adheres to type safety/invariants
# ------------------------------------------------------------------------

# Configuration
BASE_DIR = "hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15"
TARGET_FILE = "behavioral_predictive_layer.ts"
TEST_CMD = "npx jest behavioral_predictive_layer.spec.ts"
GRID_FILE = "hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/map_elites_grid.json"
MODEL_NAME = "gemini-2.5-flash"

def call_gemini(prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={api_key}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7}
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result['candidates'][0]['content']['parts'][0]['text']
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_time = 2 ** attempt
                print(f"     [!] 429 Too Many Requests. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"Gemini API Error: {e}")
                return ""
        except Exception as e:
            print(f"Gemini API Error: {e}")
            return ""
            
    print("     [!] Max retries reached for Gemini API.")
    return ""

def load_grid() -> Dict[str, Any]:
    if os.path.exists(GRID_FILE):
        with open(GRID_FILE, "r") as f:
            return json.load(f)
    return {}

def save_grid(grid: Dict[str, Any]):
    with open(GRID_FILE, "w") as f:
        json.dump(grid, f, indent=2)

def get_cell_key(x: int, y: int) -> str:
    return f"{x},{y}"

def mutate_genome(base_code: str, x_agg: int, y_prec: int) -> str:
    """Mutate the base code using Gemini based on phenotypic dimensions."""
    prompt = f"""
    You are P4 Red Regnant, an evolutionary mutation engine.
    Your task is to mutate the following TypeScript code.
    
    Phenotypic Dimensions:
    - Aggressiveness (0-10): {x_agg} (Higher = more aggressive optimization, pruning, risk-taking)
    - Precision (0-10): {y_prec} (Higher = stricter type safety, invariant checking, defensive coding)
    
    Base Code:
    ```typescript
    {base_code}
    ```
    
    Return ONLY the mutated TypeScript code. Do not include markdown formatting or explanations.
    """
    response_text = call_gemini(prompt)
    if not response_text:
        raise ValueError("Empty response from Gemini")
        
    mutated_code = response_text.strip()
    if mutated_code.startswith("```typescript"):
        mutated_code = mutated_code[13:]
    elif mutated_code.startswith("```ts"):
        mutated_code = mutated_code[5:]
    if mutated_code.endswith("```"):
        mutated_code = mutated_code[:-3]
    return mutated_code.strip()

def evaluate_mutant(mutated_code: str) -> Tuple[bool, float]:
    """Run the test suite against the mutated code and return (passed, score)."""
    target_path = os.path.join(BASE_DIR, TARGET_FILE)
    
    # Backup original
    with open(target_path, "r") as f:
        original_code = f.read()
        
    try:
        # Write mutant
        with open(target_path, "w") as f:
            f.write(mutated_code)
            
        # Run tests
        start_time = time.time()
        result = subprocess.run(TEST_CMD, shell=True, cwd=BASE_DIR, capture_output=True, text=True)
        duration = time.time() - start_time
        
        passed = result.returncode == 0
        
        # Calculate a simple fitness score (e.g., based on test pass and execution speed)
        # In a real scenario, this would parse test coverage or specific assertions.
        score = 100.0 if passed else 0.0
        if passed:
            score += max(0, 10.0 - duration) # Bonus for speed
            
        return passed, score
        
    finally:
        # Restore original
        with open(target_path, "w") as f:
            f.write(original_code)

def breed_generation(num_mutants: int = 5):
    print(f"[*] Starting MAP-Elites Breeding Generation ({num_mutants} mutants)")
    grid = load_grid()
    
    target_path = os.path.join(BASE_DIR, TARGET_FILE)
    if not os.path.exists(target_path):
        print(f"[!] Target file not found: {target_path}")
        return
        
    with open(target_path, "r") as f:
        base_code = f.read()
        
    import random
    
    for i in range(num_mutants):
        # Randomly select phenotypic traits
        x_agg = random.randint(0, 10)
        y_prec = random.randint(0, 10)
        
        print(f"  -> Mutating [Aggressiveness: {x_agg}, Precision: {y_prec}]...")
        
        try:
            mutated_code = mutate_genome(base_code, x_agg, y_prec)
            passed, score = evaluate_mutant(mutated_code)
            
            print(f"     Result: {'PASS' if passed else 'FAIL'} | Score: {score:.2f}")
            
            if passed:
                cell_key = get_cell_key(x_agg, y_prec)
                existing_elite = grid.get(cell_key)
                
                if not existing_elite or score > existing_elite["score"]:
                    print(f"     *** NEW ELITE DISCOVERED for cell {cell_key} ***")
                    grid[cell_key] = {
                        "score": score,
                        "code": mutated_code,
                        "timestamp": time.time()
                    }
                    save_grid(grid)
                    
        except Exception as e:
            print(f"     [!] Mutation failed: {e}")

if __name__ == "__main__":
    breed_generation(5)
