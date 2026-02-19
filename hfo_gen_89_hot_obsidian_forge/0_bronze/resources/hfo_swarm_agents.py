"""
HFO Gen89 — Ollama Swarm Agents
================================
Multi-agent swarm backed by local Ollama models.
Uses OpenAI Swarm framework with Ollama's OpenAI-compatible API.

Agents:
  - Triage Agent: Routes requests to specialist agents
  - Research Agent: Web search and information synthesis
  - Coder Agent: Code generation, review, debugging
  - Analyst Agent: Data analysis, reasoning, SSOT queries

Pointer key: swarm.agents
Medallion: bronze
"""

import sys
import os

# Add resources dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from swarm import Swarm, Agent
from hfo_swarm_config import (
    OLLAMA_API_BASE,
    DEFAULT_MODEL,
    MAX_TURNS,
    TEMPERATURE,
    get_openai_client,
)
from hfo_web_tools import web_search, web_news, fetch_page, search_and_summarize


# ══════════════════════════════════════════════════════════════════
# Agent Definitions
# ══════════════════════════════════════════════════════════════════

def transfer_to_research():
    """Transfer to the Research Agent for web search and information gathering."""
    return research_agent

def transfer_to_coder():
    """Transfer to the Coder Agent for code generation, review, or debugging."""
    return coder_agent

def transfer_to_analyst():
    """Transfer to the Analyst Agent for data analysis and reasoning."""
    return analyst_agent

def transfer_to_triage():
    """Transfer back to the Triage Agent for re-routing."""
    return triage_agent


# ── Triage Agent ───────────────────────────────────────────────
triage_agent = Agent(
    name="Triage Agent",
    model=DEFAULT_MODEL,
    instructions="""You are the Triage Agent for HFO Gen89. Your job is to understand
the user's request and route it to the right specialist agent.

Available specialists:
- Research Agent: For web searches, news, current events, gathering information
- Coder Agent: For writing code, debugging, code review, technical implementation
- Analyst Agent: For data analysis, reasoning, SSOT database queries, insights

Assess the user's request and transfer to the most appropriate agent.
If the request is simple enough, answer it directly.
If unsure, ask a clarifying question.""",
    functions=[transfer_to_research, transfer_to_coder, transfer_to_analyst],
)

# ── Research Agent ─────────────────────────────────────────────
research_agent = Agent(
    name="Research Agent",
    model=DEFAULT_MODEL,
    instructions="""You are the Research Agent for HFO Gen89. You specialize in:
- Web searches using DuckDuckGo
- News gathering
- Fetching and reading web pages
- Synthesizing information from multiple sources

When given a research task:
1. Search for relevant information using web_search or web_news
2. If needed, fetch full page content with fetch_page
3. Synthesize findings into a clear, organized summary
4. Cite your sources with URLs

Always verify claims with multiple sources when possible.
Transfer back to triage if the task needs a different specialist.""",
    functions=[web_search, web_news, fetch_page, search_and_summarize, transfer_to_triage],
)

# ── Coder Agent ────────────────────────────────────────────────
coder_agent = Agent(
    name="Coder Agent",
    model=DEFAULT_MODEL,
    instructions="""You are the Coder Agent for HFO Gen89. You specialize in:
- Writing clean, well-documented Python code
- Debugging and fixing code issues
- Code review and optimization
- Technical implementation of features

Follow these practices:
- Write clear docstrings and comments
- Follow PEP 8 conventions
- Handle errors gracefully
- Keep functions focused and testable

Transfer back to triage if the task needs a different specialist.""",
    functions=[transfer_to_triage],
)

# ── Analyst Agent ──────────────────────────────────────────────
analyst_agent = Agent(
    name="Analyst Agent",
    model=DEFAULT_MODEL,
    instructions="""You are the Analyst Agent for HFO Gen89. You specialize in:
- Data analysis and interpretation
- Querying the HFO SSOT database (SQLite)
- Pattern recognition and insights
- Structured reasoning and decision support

When analyzing data:
1. Understand the question clearly
2. Identify what data is needed
3. Present findings with evidence
4. Highlight key insights and recommendations

Transfer back to triage if the task needs a different specialist.""",
    functions=[web_search, transfer_to_triage],
)


# ══════════════════════════════════════════════════════════════════
# Swarm Runner
# ══════════════════════════════════════════════════════════════════

def create_swarm():
    """Create and return a configured Swarm instance with Ollama backend."""
    client = get_openai_client()
    swarm = Swarm(client=client)
    return swarm


def run_swarm(user_message: str, agent=None, context_variables=None, stream=False):
    """
    Run a single turn through the swarm.

    Args:
        user_message: The user's input message
        agent: Starting agent (defaults to triage_agent)
        context_variables: Dict of context variables for agents
        stream: Whether to stream the response

    Returns:
        Swarm Response object
    """
    if agent is None:
        agent = triage_agent
    if context_variables is None:
        context_variables = {}

    swarm = create_swarm()
    messages = [{"role": "user", "content": user_message}]

    response = swarm.run(
        agent=agent,
        messages=messages,
        context_variables=context_variables,
        max_turns=MAX_TURNS,
        stream=stream,
    )

    return response


def interactive_loop():
    """Run an interactive chat loop with the swarm."""
    print("=" * 60)
    print("  HFO Gen89 — Ollama Swarm (Interactive)")
    print(f"  Model: {DEFAULT_MODEL}")
    print(f"  API: {OLLAMA_API_BASE}")
    print("  Type 'quit' to exit, 'agents' to list agents")
    print("=" * 60)
    print()

    swarm = create_swarm()
    messages = []
    current_agent = triage_agent

    while True:
        try:
            user_input = input(f"[{current_agent.name}] You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("Goodbye!")
            break
        if user_input.lower() == "agents":
            print("  Triage Agent — Routes to specialists")
            print("  Research Agent — Web search & synthesis")
            print("  Coder Agent — Code generation & review")
            print("  Analyst Agent — Data analysis & reasoning")
            continue

        messages.append({"role": "user", "content": user_input})

        try:
            response = swarm.run(
                agent=current_agent,
                messages=messages,
                max_turns=MAX_TURNS,
            )

            # Update state
            messages = response.messages
            current_agent = response.agent

            # Print assistant response
            last_msg = messages[-1]["content"] if messages else "(no response)"
            print(f"\n[{current_agent.name}]: {last_msg}\n")

        except Exception as e:
            print(f"\n  Error: {e}\n")
            # Don't break — let user retry


# ══════════════════════════════════════════════════════════════════
# CLI Entry Point
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_loop()
    elif len(sys.argv) > 1:
        # One-shot mode: pass all args as the message
        msg = " ".join(sys.argv[1:])
        print(f"Sending to swarm: {msg}\n")
        response = run_swarm(msg)
        print(f"[{response.agent.name}]: {response.messages[-1]['content']}")
    else:
        print("Usage:")
        print("  python hfo_swarm_agents.py --interactive    # Chat loop")
        print('  python hfo_swarm_agents.py "your message"   # One-shot')
        print()
        print("Testing swarm connectivity...")
        try:
            swarm = create_swarm()
            print(f"  ✓ Swarm created (API: {OLLAMA_API_BASE})")
            print(f"  ✓ Default model: {DEFAULT_MODEL}")

            from hfo_swarm_config import list_local_models
            models = list_local_models()
            print(f"  ✓ Available models: {[m['name'] for m in models]}")

            print("\n  Running quick test...")
            response = run_swarm("Say hello in exactly 5 words.")
            print(f"  ✓ Response from [{response.agent.name}]: {response.messages[-1]['content']}")
            print("\n  Swarm is operational!")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback
            traceback.print_exc()
