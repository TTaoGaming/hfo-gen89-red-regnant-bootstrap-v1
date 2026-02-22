import subprocess
import sys
import os

def test_red_state():
    # Ensure the test file exists
    assert os.path.exists("c:/hfoDev/hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/tests/kernel/event_bus.spec.ts"), "Jest test file missing"
    
    # Run jest
    result = subprocess.run(
        ["npx", "jest", "tests/kernel/event_bus.spec.ts", "--testMatch=**/*.spec.ts", "--testPathIgnorePatterns=[]"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
        cwd="c:/hfoDev/hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15"
    )
    
    # Save output
    with open("c:/hfoDev/hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/jest_output.log", "w", encoding="utf-8") as f:
        f.write("STDOUT:\n" + str(result.stdout) + "\nSTDERR:\n" + str(result.stderr))
        
    # Assert it failed (RED state)
    assert result.returncode != 0, "Test passed unexpectedly! It should be RED."

if __name__ == "__main__":
    test_red_state()
