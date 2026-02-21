import sys
import pathlib
sys.path.insert(0, "hfo_gen_89_hot_obsidian_forge/0_bronze/resources")
import hfo_prey8_mcp_server
hfo_prey8_mcp_server.DB_PATH = pathlib.Path("hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite")
res = hfo_prey8_mcp_server.prey8_react(
    agent_id="P4_Red_Regnant",
    perceive_nonce="F90CDE",
    analysis="The user wants to establish Gen 90 with a clean root and a single entryway. The PAL (Pointer Abstraction Layer) needs to be moved to the Gen 90 forge, and the Gen 89 PAL archived. hfo_pointers.py will remain in the root as the single entryway, but it needs to be updated to find the Gen 90 PAL.",
    plan="1. Move hfo_gen89_pointers_blessed.json to Gen 89 archives. 2. Create hfo_gen90_pointers_blessed.json in Gen 90 resources. 3. Move hfo_pointers.py to root and update it to read .env and find the PAL in the forge. 4. Update .env and AGENTS.md.",
    shared_data_refs="hfo_pointers.py, hfo_gen89_pointers_blessed.json, .env",
    navigation_intent="Establish Gen 90 PAL and clean up root directory.",
    meadows_level=8,
    meadows_justification="This is a rule change (L8) regarding how the system resolves paths and where the PAL is stored.",
    sequential_plan="1. Archive Gen 89 PAL. 2. Create Gen 90 PAL. 3. Move and update hfo_pointers.py. 4. Update .env and AGENTS.md."
)
print(res)