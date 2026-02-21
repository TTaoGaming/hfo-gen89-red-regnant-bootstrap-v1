import pathlib
import sys
import json

p = pathlib.Path("hfo_pointers.py")
text = p.read_text(encoding="utf-8")

old_str = """def load_pointers(root: Path) -> dict:
    \"\"\"Load the blessed pointer registry.\"\"\"
    # Try well-known names
    for name in ["hfo_gen90_pointers_blessed.json", "hfo_pointers_blessed.json"]:
        fp = root / name
        if fp.exists():
            data = json.loads(fp.read_text(encoding="utf-8"))
            return data.get("pointers", data)

    print("ERROR: No blessed pointer file found in root", file=sys.stderr)
    sys.exit(1)"""

new_str = """def load_pointers(root: Path) -> dict:
    \"\"\"Load the blessed pointer registry.\"\"\"
    env = load_env(root)
    forge_dir = env.get("HFO_FORGE", "hfo_gen_90_hot_obsidian_forge")
    gen = env.get("HFO_GENERATION", "90")
    
    # Try well-known names in the forge
    for name in [f"hfo_gen{gen}_pointers_blessed.json", "hfo_pointers_blessed.json"]:
        fp = root / forge_dir / "3_hyper_fractal_obsidian" / "2_resources" / name
        if fp.exists():
            data = json.loads(fp.read_text(encoding="utf-8"))
            return data.get("pointers", data)

    print(f"ERROR: No blessed pointer file found in {forge_dir}/3_hyper_fractal_obsidian/2_resources/", file=sys.stderr)
    sys.exit(1)"""

text = text.replace(old_str, new_str)
p.write_text(text, encoding="utf-8")
print("Updated hfo_pointers.py")