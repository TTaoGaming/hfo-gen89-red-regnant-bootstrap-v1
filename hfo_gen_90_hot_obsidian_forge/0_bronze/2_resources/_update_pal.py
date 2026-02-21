import json
import pathlib

p_in = pathlib.Path("hfo_gen_89_hot_obsidian_forge/0_bronze/demoted_hfo/archives/hfo_gen89_pointers_blessed.json")
data = json.loads(p_in.read_text(encoding="utf-8"))

data["$schema"] = "hfo.gen90.pointers.blessed.v1"
data["version"] = "gen90_v1"
data["built"] = "2026-02-21"
data["note"] = "Blessed pointer registry for Gen90. All paths relative to HFO_ROOT. Resolve via hfo_pointers.py."

# Update pointers
for key, entry in data["pointers"].items():
    if isinstance(entry, dict):
        path = entry["path"]
        path = path.replace("hfo_gen_89_hot_obsidian_forge", "hfo_gen_90_hot_obsidian_forge")
        path = path.replace("hfo_gen89_ssot.sqlite", "hfo_gen90_ssot.sqlite")
        path = path.replace("0_bronze/resources", "0_bronze/2_resources")
        path = path.replace("1_silver/resources", "1_silver/2_resources")
        path = path.replace("2_gold/resources", "2_gold/2_resources")
        path = path.replace("3_hyper_fractal_obsidian/resources", "3_hyper_fractal_obsidian/2_resources")
        if key == "root.pointers_blessed":
            path = "hfo_gen_90_hot_obsidian_forge/3_hyper_fractal_obsidian/2_resources/hfo_gen90_pointers_blessed.json"
        entry["path"] = path
    else:
        path = entry
        path = path.replace("hfo_gen_89_hot_obsidian_forge", "hfo_gen_90_hot_obsidian_forge")
        path = path.replace("hfo_gen89_ssot.sqlite", "hfo_gen90_ssot.sqlite")
        path = path.replace("0_bronze/resources", "0_bronze/2_resources")
        path = path.replace("1_silver/resources", "1_silver/2_resources")
        path = path.replace("2_gold/resources", "2_gold/2_resources")
        path = path.replace("3_hyper_fractal_obsidian/resources", "3_hyper_fractal_obsidian/2_resources")
        if key == "root.pointers_blessed":
            path = "hfo_gen_90_hot_obsidian_forge/3_hyper_fractal_obsidian/2_resources/hfo_gen90_pointers_blessed.json"
        data["pointers"][key] = path

p_out = pathlib.Path("hfo_gen_90_hot_obsidian_forge/3_hyper_fractal_obsidian/2_resources/hfo_gen90_pointers_blessed.json")
p_out.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("Updated PAL written to", p_out)