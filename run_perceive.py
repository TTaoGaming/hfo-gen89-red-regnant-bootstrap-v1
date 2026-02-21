import sys
import pathlib
sys.path.insert(0, "hfo_gen_89_hot_obsidian_forge/0_bronze/resources")
import hfo_prey8_mcp_server
hfo_prey8_mcp_server.DB_PATH = pathlib.Path("hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite")
res = hfo_prey8_mcp_server.prey8_perceive(
    agent_id="P4_Red_Regnant",
    probe="Planar Binding Gen 90 PAL",
    observations="Gen 90 forge is created. Gen 89 PAL is in root. User wants to move PAL to forge and have a single entryway in root.",
    memory_refs="129,317,12,4",
    stigmergy_digest="Last yield was nonce BFF9C2 about fixing PARA structure in Gen 90. No memory losses detected."
)
print(res)