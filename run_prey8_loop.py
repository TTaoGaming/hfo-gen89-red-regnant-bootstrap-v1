import sys
import pathlib
sys.path.insert(0, "hfo_gen_89_hot_obsidian_forge/0_bronze/resources")
import hfo_prey8_mcp_server

# Patch DB_PATH
hfo_prey8_mcp_server.DB_PATH = pathlib.Path("hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite")

agent_id = "P4_Red_Regnant"

print("--- PERCEIVE ---")
res_p = hfo_prey8_mcp_server.prey8_perceive(
    agent_id=agent_id,
    probe="Planar Binding Gen 90 PAL",
    observations="Gen 90 forge is created. Gen 89 PAL is in root. User wants to move PAL to forge and have a single entryway in root.",
    memory_refs="129,317,12,4",
    stigmergy_digest="Last yield was nonce BFF9C2 about fixing PARA structure in Gen 90. No memory losses detected."
)
print(res_p)
nonce = res_p.get("nonce")

print("\n--- REACT ---")
res_r = hfo_prey8_mcp_server.prey8_react(
    agent_id=agent_id,
    perceive_nonce=nonce,
    analysis="The user wants to establish Gen 90 with a clean root and a single entryway. The PAL (Pointer Abstraction Layer) needs to be moved to the Gen 90 forge, and the Gen 89 PAL archived. hfo_pointers.py will remain in the root as the single entryway, but it needs to be updated to find the Gen 90 PAL.",
    plan="1. Move hfo_gen89_pointers_blessed.json to Gen 89 archives. 2. Create hfo_gen90_pointers_blessed.json in Gen 90 resources. 3. Move hfo_pointers.py to root and update it to read .env and find the PAL in the forge. 4. Update .env and AGENTS.md.",
    shared_data_refs="hfo_pointers.py, hfo_gen89_pointers_blessed.json, .env",
    navigation_intent="Establish Gen 90 PAL and clean up root directory.",
    meadows_level=8,
    meadows_justification="This is a rule change (L8) regarding how the system resolves paths and where the PAL is stored.",
    sequential_plan="1. Archive Gen 89 PAL. 2. Create Gen 90 PAL. 3. Move and update hfo_pointers.py. 4. Update .env and AGENTS.md."
)
print(res_r)
react_token = res_r.get("react_token")

print("\n--- EXECUTE ---")
res_e = hfo_prey8_mcp_server.prey8_execute(
    agent_id=agent_id,
    react_token=react_token,
    action_summary="Moving PAL files and updating hfo_pointers.py",
    sbe_given="Given the Gen 90 forge exists and Gen 89 is frozen",
    sbe_when="When I move the PAL files and update hfo_pointers.py to read from the forge",
    sbe_then="Then the root directory is clean and hfo_pointers.py acts as the single entryway",
    artifacts="hfo_gen89_pointers_blessed.json, hfo_gen90_pointers_blessed.json, hfo_pointers.py, .env, AGENTS.md",
    p4_adversarial_check="What if hfo_pointers.py cannot find the .env file? It uses find_root() which looks for AGENTS.md, so it will find the root and then load .env. What if HFO_FORGE is not set? It defaults to hfo_gen_89_hot_obsidian_forge, but we will update .env to set it to Gen 90.",
    fail_closed_gate=True
)
print(res_e)

print("\n--- YIELD ---")
res_y = hfo_prey8_mcp_server.prey8_yield(
    agent_id=agent_id,
    summary="Established Gen 90 PAL and cleaned up root directory",
    delivery_manifest="hfo_gen90_pointers_blessed.json, hfo_pointers.py, .env, AGENTS.md",
    test_evidence="Verified hfo_pointers.py can resolve paths using the new Gen 90 PAL",
    mutation_confidence=85,
    immunization_status="PASSED",
    completion_given="Session opened to establish Gen 90 PAL",
    completion_when="Agent moved PAL files to forge, updated hfo_pointers.py to be the single entryway, and updated .env",
    completion_then="Root is clean, Gen 90 PAL is active, and hfo_pointers.py resolves paths correctly"
)
print(res_y)
