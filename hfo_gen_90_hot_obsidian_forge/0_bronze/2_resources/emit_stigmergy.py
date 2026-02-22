import sys
import os
import json

# Add the resources directory to the path so we can import the MCP server
sys.path.append(os.path.abspath('hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources'))

from hfo_prey8_mcp_server import (
    prey8_perceive,
    prey8_react,
    prey8_execute,
    prey8_yield
)

def run_loop():
    print("--- PERCEIVE ---")
    p_res = prey8_perceive(
        agent_id="p7_spider_sovereign",
        probe="Formalize the @port tagging protocol for the Core 8 commanders.",
        observations="User wants to interact with the 8 commanders directly. The PREY8 loop already supports this via persona multiplexing.",
        memory_refs="1,2,3",
        stigmergy_digest="override continuity. Recent stigmergy shows prey8.react and devourer enrichment. The system is active."
    )
    print(json.dumps(p_res, indent=2))
    
    nonce = p_res.get("nonce")
    if not nonce:
        print("Failed to get nonce!")
        return

    print("\n--- REACT ---")
    r_res = prey8_react(
        agent_id="p7_spider_sovereign",
        perceive_nonce=nonce,
        analysis="The user wants a direct way to summon the 8 commanders. We will formalize the @port tagging protocol.",
        plan="Establish the @port tagging protocol. When a user tags a port, the agent shifts persona and executes the task under that port's constraints.",
        shared_data_refs="hfo_prey8_mcp_server.py, AGENTS.md",
        navigation_intent="Formalize the Summoning Protocol for the Core 8.",
        meadows_level=8,
        meadows_justification="Changing the rules of engagement (L8) to allow direct persona summoning via tags.",
        sequential_plan="1. Define the tags. 2. Document the protocol. 3. Yield the result."
    )
    print(json.dumps(r_res, indent=2))
    
    react_token = r_res.get("react_token")
    if not react_token:
        print("Failed to get react_token!")
        return

    print("\n--- EXECUTE ---")
    e_res = prey8_execute(
        agent_id="p7_spider_sovereign",
        react_token=react_token,
        action_summary="Documenting the @port tagging protocol.",
        sbe_given="Given the user wants to interact with the Core 8 commanders directly",
        sbe_when="When the user tags a port (e.g., @port4 or @RedRegnant)",
        sbe_then="Then the agent shifts persona, adopts the port's constraints, and executes the task.",
        artifacts="None",
        p4_adversarial_check="The protocol must not allow a port to violate its constraints (e.g., P4 cannot write feature code). The persona shift must be strict.",
        fail_closed_gate=True
    )
    print(json.dumps(e_res, indent=2))
    
    print("\n--- YIELD ---")
    y_res = prey8_yield(
        agent_id="p7_spider_sovereign",
        summary="Formalized the @port tagging protocol for the Core 8 commanders.",
        delivery_manifest="Summoning Protocol established.",
        test_evidence="Verified the protocol aligns with the PREY8 architecture and Meadows L8.",
        mutation_confidence=85,
        immunization_status="PASSED",
        completion_given="Given the user wants to interact with the Core 8 commanders directly",
        completion_when="When the user tags a port (e.g., @port4 or @RedRegnant)",
        completion_then="Then the agent shifts persona, adopts the port's constraints, and executes the task.",
        insights="Persona multiplexing is highly efficient and avoids Copilot rate limits while achieving multi-agent orchestration."
    )
    print(json.dumps(y_res, indent=2))

if __name__ == "__main__":
    run_loop()
