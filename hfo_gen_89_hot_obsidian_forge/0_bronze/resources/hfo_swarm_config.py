"""
HFO Gen89 — Ollama Swarm Configuration
=======================================
Central config for the local Ollama-backed swarm.
All agents share this config to connect to the local Ollama instance
via its OpenAI-compatible API.

Pointer key: swarm.config
Medallion: bronze
"""

import os

# ── Ollama Server ──────────────────────────────────────────────
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_API_BASE = f"{OLLAMA_HOST}/v1"

# ── Default Model ──────────────────────────────────────────────
# Override via OLLAMA_MODEL env var or per-agent
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

# ── Recommended Models (pull these for full swarm capability) ──
RECOMMENDED_MODELS = {
    # Small & fast — good for routing, triage, tool-calling
    "qwen2.5:3b":       {"size_gb": 1.8,  "use": "routing, triage, fast tasks"},
    # Medium — good balance of quality and speed
    "qwen2.5:7b":       {"size_gb": 4.4,  "use": "general purpose, coding"},
    "llama3.1:8b":      {"size_gb": 4.7,  "use": "general purpose, reasoning"},
    "gemma3:12b":       {"size_gb": 7.6,  "use": "general purpose, multilingual"},
    "mistral:7b":       {"size_gb": 4.1,  "use": "general purpose, fast"},
    # Large — best quality, needs more RAM
    "qwen2.5:14b":      {"size_gb": 9.0,  "use": "complex reasoning, coding"},
    "deepseek-r1:14b":  {"size_gb": 9.0,  "use": "deep reasoning, chain-of-thought"},
    "llama3.1:70b":     {"size_gb": 40.0, "use": "best quality (needs 48GB+ RAM)"},
    # Coding specialists
    "qwen2.5-coder:7b": {"size_gb": 4.4,  "use": "code generation, review"},
    # Vision
    "llava:7b":         {"size_gb": 4.5,  "use": "multimodal, image understanding"},
}

# ── Swarm Settings ─────────────────────────────────────────────
MAX_TURNS = int(os.getenv("SWARM_MAX_TURNS", "30"))
TEMPERATURE = float(os.getenv("SWARM_TEMPERATURE", "0.7"))
STREAM = os.getenv("SWARM_STREAM", "true").lower() == "true"

# ── Web Research Settings ──────────────────────────────────────
WEB_SEARCH_MAX_RESULTS = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "10"))
WEB_SEARCH_REGION = os.getenv("WEB_SEARCH_REGION", "wt-wt")  # worldwide
WEB_SEARCH_SAFESEARCH = os.getenv("WEB_SEARCH_SAFESEARCH", "moderate")


def get_openai_client():
    """Return an OpenAI client pointed at the local Ollama instance."""
    from openai import OpenAI
    return OpenAI(
        base_url=OLLAMA_API_BASE,
        api_key="ollama",  # Ollama doesn't need a real key
    )


def get_ollama_client():
    """Return the native Ollama Python client."""
    import ollama
    return ollama.Client(host=OLLAMA_HOST)


def list_local_models():
    """List models currently available in the local Ollama instance."""
    client = get_ollama_client()
    response = client.list()
    models = response.models if hasattr(response, 'models') else []
    return [
        {
            "name": getattr(m, 'model', getattr(m, 'name', str(m))),
            "size_gb": round(getattr(m, 'size', 0) / (1024**3), 2),
            "modified": str(getattr(m, 'modified_at', '')),
        }
        for m in models
    ]


def pull_model(name: str):
    """Pull a model from the Ollama registry."""
    client = get_ollama_client()
    print(f"Pulling {name}... (this may take a while)")
    for progress in client.pull(name, stream=True):
        status = getattr(progress, 'status', str(progress))
        total = getattr(progress, 'total', 0) or 0
        completed = getattr(progress, 'completed', 0) or 0
        if total > 0:
            pct = round(completed / total * 100, 1)
            print(f"\r  {status}: {pct}%", end="", flush=True)
        else:
            print(f"\r  {status}", end="", flush=True)
    print(f"\n  ✓ {name} ready")
