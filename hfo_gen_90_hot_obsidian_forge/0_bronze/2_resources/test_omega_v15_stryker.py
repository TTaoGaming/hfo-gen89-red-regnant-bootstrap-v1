import subprocess
import sys

def test_stryker_score():
    result = subprocess.run(
        ["npx", "-y", "tsx", "test_plugin_supervisor.ts"],
        cwd="hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15",
        capture_output=True,
        text=True,
        shell=True
    )
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)
    print("Tests passed.")

if __name__ == "__main__":
    test_stryker_score()