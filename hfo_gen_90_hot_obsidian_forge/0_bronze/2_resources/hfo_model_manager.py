"""
HFO Gen90 — Model Manager
==========================
Pull, list, and manage Ollama models.
Quick utility for loading popular models.

Pointer key: swarm.model_manager
Medallion: bronze
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hfo_swarm_config import (
    RECOMMENDED_MODELS,
    get_ollama_client,
    list_local_models,
    pull_model,
)


def show_status():
    """Show current model status."""
    print("=" * 60)
    print("  HFO Gen90 — Ollama Model Manager")
    print("=" * 60)

    # Local models
    local = list_local_models()
    local_names = {m["name"] for m in local}

    print(f"\n  Local models ({len(local)}):")
    if local:
        for m in local:
            print(f"    ✓ {m['name']:25s}  {m['size_gb']:6.1f} GB")
    else:
        print("    (none)")

    # Recommended models
    print(f"\n  Recommended models:")
    for name, info in RECOMMENDED_MODELS.items():
        installed = "✓" if name in local_names else " "
        print(f"    {installed} {name:25s}  {info['size_gb']:6.1f} GB  — {info['use']}")

    print()


def pull_popular(tier: str = "small"):
    """Pull popular models by tier.

    Tiers:
        small: Models under 5GB (good starting set)
        medium: Models under 10GB
        large: All recommended models
        coding: Coding-focused models
    """
    tiers = {
        "small": [k for k, v in RECOMMENDED_MODELS.items() if v["size_gb"] < 5],
        "medium": [k for k, v in RECOMMENDED_MODELS.items() if v["size_gb"] < 10],
        "large": list(RECOMMENDED_MODELS.keys()),
        "coding": [k for k in RECOMMENDED_MODELS if "coder" in k.lower()],
    }

    if tier not in tiers:
        print(f"Unknown tier: {tier}. Choose from: {list(tiers.keys())}")
        return

    models = tiers[tier]
    local = {m["name"] for m in list_local_models()}

    to_pull = [m for m in models if m not in local]
    total_gb = sum(RECOMMENDED_MODELS[m]["size_gb"] for m in to_pull)

    if not to_pull:
        print(f"All {tier} tier models already installed!")
        return

    print(f"\nPulling {len(to_pull)} models (~{total_gb:.1f} GB total):")
    for name in to_pull:
        print(f"  → {name} ({RECOMMENDED_MODELS[name]['size_gb']} GB)")

    print()
    for name in to_pull:
        try:
            pull_model(name)
        except Exception as e:
            print(f"  ✗ Failed to pull {name}: {e}")


def pull_single(model_name: str):
    """Pull a single model by name."""
    try:
        pull_model(model_name)
    except Exception as e:
        print(f"  ✗ Failed to pull {model_name}: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_status()
        print("Usage:")
        print("  python hfo_model_manager.py status              # Show model status")
        print("  python hfo_model_manager.py pull <model_name>   # Pull a specific model")
        print("  python hfo_model_manager.py tier small           # Pull all small models (<5GB)")
        print("  python hfo_model_manager.py tier medium          # Pull medium models (<10GB)")
        print("  python hfo_model_manager.py tier coding          # Pull coding models")
        print("  python hfo_model_manager.py tier large           # Pull ALL recommended models")
    elif sys.argv[1] == "status":
        show_status()
    elif sys.argv[1] == "pull" and len(sys.argv) > 2:
        pull_single(sys.argv[2])
    elif sys.argv[1] == "tier" and len(sys.argv) > 2:
        pull_popular(sys.argv[2])
    else:
        print(f"Unknown command: {' '.join(sys.argv[1:])}")
