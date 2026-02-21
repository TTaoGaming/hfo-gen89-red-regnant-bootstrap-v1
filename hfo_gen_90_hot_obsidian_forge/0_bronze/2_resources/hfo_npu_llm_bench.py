#!/usr/bin/env python3
"""
hfo_npu_llm_bench.py — NPU LLM Inference Benchmark
====================================================
Tests OpenVINO GenAI models on Intel AI Boost NPU.

Usage:
  python hfo_npu_llm_bench.py                         # bench all available
  python hfo_npu_llm_bench.py --model qwen3-1.7b     # bench one model
  python hfo_npu_llm_bench.py --device CPU            # force CPU (fallback)
  python hfo_npu_llm_bench.py --interactive           # chat mode
  python hfo_npu_llm_bench.py --export qwen2.5-3b    # export model from HF

Models directory: C:\\hfoDev\\.hfo_models\\npu_llm\\
"""

import argparse
import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────────────────
HFO_ROOT   = Path(__file__).resolve().parents[3]  # C:\hfoDev
MODELS_DIR = HFO_ROOT / ".hfo_models" / "npu_llm"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ── Registered models ──────────────────────────────────────────────────────────
# Each entry: (local_dir_name, hf_repo, short_name, size_gb, recommended_device)
MODEL_REGISTRY = [
    # Pre-built NPU-optimized (INT4-GQ sym, group-size 128)
    ("qwen3-1.7b-int4-ov-npu",           "FluidInference/qwen3-1.7b-int4-ov-npu",             "Qwen3-1.7B",      1.0,  "NPU"),
    ("qwen3-4b-int4-ov-npu",             "FluidInference/qwen3-4b-int4-ov-npu",               "Qwen3-4B",        2.5,  "NPU"),
    ("qwen3-8b-int4-cw-ov",              "OpenVINO/Qwen3-8B-int4-cw-ov",                      "Qwen3-8B",        5.0,  "NPU"),
    # Exported (channel-wise INT4 sym, group-size 128)
    ("qwen2.5-3b-instruct-int4-sym",     "Qwen/Qwen2.5-3B-Instruct",                          "Qwen2.5-3B",      2.0,  "NPU"),
    ("phi-3.5-mini-int4-cw-ov",          "OpenVINO/Phi-3.5-mini-instruct-int4-cw-ov",         "Phi-3.5-mini",    2.2,  "NPU"),
    ("deepseek-r1-1.5b-int4-cw-ov",      "OpenVINO/DeepSeek-R1-Distill-Qwen-1.5B-int4-cw-ov","DeepSeek-R1-1.5B",1.0, "NPU"),
]

# Benchmark prompts
BENCH_PROMPTS = [
    {
        "name": "short_factual",
        "prompt": "What is the capital of France? Answer in one sentence.",
        "max_tokens": 64,
    },
    {
        "name": "summarize_task",
        "prompt": (
            "Summarize the following in 2 sentences: "
            "The knowledge graph is a data structure that represents entities and their relationships. "
            "It enables machines to understand the context and meaning of data, facilitating reasoning and inference. "
            "Knowledge graphs are used in search engines, recommendation systems, and AI assistants."
        ),
        "max_tokens": 128,
    },
    {
        "name": "bluf_generation",
        "prompt": (
            "Write a BLUF (Bottom Line Up Front) summary in one sentence for this document: "
            "This document describes the PREY8 cognitive loop architecture used in HFO Gen90. "
            "PREY8 stands for Perceive-React-Execute-Yield and provides mandatory session bookends "
            "to ensure cognitive persistence across agent sessions via stigmergy events stored in SQLite."
        ),
        "max_tokens": 64,
    },
]


def get_available_models():
    """Return models whose local directory exists."""
    found = []
    for local_dir, hf_repo, name, size_gb, device in MODEL_REGISTRY:
        path = MODELS_DIR / local_dir
        if path.exists() and any(path.iterdir()):
            found.append((path, hf_repo, name, size_gb, device))
    return found


def print_model_status():
    """Print which models are downloaded vs missing."""
    print("\n── NPU LLM Model Status ──────────────────────────────────────")
    print(f"  Storage: {MODELS_DIR}")
    print()
    for local_dir, hf_repo, name, size_gb, device in MODEL_REGISTRY:
        path = MODELS_DIR / local_dir
        status = "✓ READY" if (path.exists() and any(path.iterdir())) else "✗ missing"
        print(f"  [{status:10s}] {name:20s}  ~{size_gb:.1f} GB  {hf_repo}")
    print()


def download_model(local_dir: str, hf_repo: str):
    """Download a model from HuggingFace Hub."""
    from huggingface_hub import snapshot_download
    dest = MODELS_DIR / local_dir
    print(f"\n[DOWNLOAD] {hf_repo} → {dest}")
    print("  This may take a few minutes...")
    start = time.time()
    snapshot_download(
        repo_id=hf_repo,
        local_dir=str(dest),
        ignore_patterns=["*.msgpack", "*.h5", "tf_model*", "flax_model*"],
    )
    elapsed = time.time() - start
    # Size on disk
    total_bytes = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
    print(f"  Done in {elapsed:.1f}s — {total_bytes / 1024**3:.2f} GB on disk")
    return dest


def export_model_to_npu(shortname: str):
    """Export a model from HuggingFace to OpenVINO INT4-sym format."""
    # Map shortname → HF model id and local dir
    export_map = {
        "qwen2.5-3b": ("Qwen/Qwen2.5-3B-Instruct", "qwen2.5-3b-instruct-int4-sym"),
        "qwen2.5-7b": ("Qwen/Qwen2.5-7B-Instruct", "qwen2.5-7b-instruct-int4-cw"),
        "qwen3-4b":   ("Qwen/Qwen3-4B",             "qwen3-4b-instruct-int4-sym"),
        "phi-3.5":    ("microsoft/Phi-3.5-mini-instruct", "phi-3.5-mini-int4-sym"),
    }
    key = shortname.lower()
    if key not in export_map:
        print(f"  [ERROR] Unknown model: {shortname}. Available: {list(export_map.keys())}")
        sys.exit(1)

    hf_id, local_dir = export_map[key]
    dest = MODELS_DIR / local_dir

    # Group-size 128 = better accuracy for ≤5B models
    # --sym = symmetric INT4 required by NPU
    import subprocess
    cmd = [
        sys.executable, "-m", "optimum.exporters.openvino",
        "--model", hf_id,
        "--weight-format", "int4",
        "--sym",
        "--ratio", "1.0",
        "--group-size", "128",
        str(dest),
    ]
    # Try CLI tool first (cleaner)
    cli_cmd = [
        "optimum-cli", "export", "openvino",
        "-m", hf_id,
        "--weight-format", "int4",
        "--sym",
        "--ratio", "1.0",
        "--group-size", "128",
        str(dest),
    ]
    print(f"\n[EXPORT] {hf_id}")
    print(f"  Format: INT4 symmetric, group-size=128 (NPU-optimized)")
    print(f"  Output: {dest}")
    print("  This will take 10-30 minutes depending on your internet + CPU speed...")
    print()
    result = subprocess.run(cli_cmd, cwd=str(HFO_ROOT))
    if result.returncode != 0:
        print(f"  [WARN] CLI export failed, trying Python API...")
        result = subprocess.run(cmd, cwd=str(HFO_ROOT))
    if result.returncode == 0:
        print(f"\n  [OK] Export complete → {dest}")
    else:
        print(f"\n  [ERROR] Export failed with code {result.returncode}")


def run_inference(model_path: Path, device: str, prompt: str, max_tokens: int = 128,
                  min_response_len: int = 32) -> dict:
    """Run a single inference and return timing + response."""
    try:
        import openvino_genai as ov_genai
    except ImportError:
        print("  [ERROR] openvino-genai not installed. Run: pip install openvino-genai==2025.4")
        sys.exit(1)

    pipeline_config = {
        "MAX_PROMPT_LEN": 1024,
        "MIN_RESPONSE_LEN": min_response_len,
    }

    t_load_start = time.perf_counter()
    try:
        if device == "NPU":
            pipe = ov_genai.LLMPipeline(str(model_path), device, pipeline_config)
        else:
            pipe = ov_genai.LLMPipeline(str(model_path), device)
    except Exception as e:
        return {"error": str(e), "device": device}
    t_load_end = time.perf_counter()

    t_gen_start = time.perf_counter()
    try:
        result_text = pipe.generate(prompt, max_new_tokens=max_tokens)
    except Exception as e:
        return {"error": str(e), "load_ms": int((t_load_end - t_load_start) * 1000)}
    t_gen_end = time.perf_counter()

    # Estimate tokens (rough: characters / 4)
    approx_output_tokens = max(1, len(result_text) // 4)
    gen_seconds = t_gen_end - t_gen_start

    return {
        "device": device,
        "load_ms": int((t_load_end - t_load_start) * 1000),
        "gen_ms": int(gen_seconds * 1000),
        "output_chars": len(result_text),
        "approx_tokens": approx_output_tokens,
        "tok_per_sec": round(approx_output_tokens / max(gen_seconds, 0.001), 1),
        "response": result_text.strip(),
    }


def bench_model(model_path: Path, model_name: str, device: str, quiet: bool = False):
    """Run all benchmark prompts on a model."""
    print(f"\n{'=' * 60}")
    print(f"  Model : {model_name}")
    print(f"  Path  : {model_path.name}")
    print(f"  Device: {device}")
    print(f"{'=' * 60}")

    results = {"model": model_name, "device": device, "prompts": []}

    for bench in BENCH_PROMPTS:
        print(f"\n  [{bench['name']}]")
        print(f"  Prompt: {bench['prompt'][:80]}{'...' if len(bench['prompt']) > 80 else ''}")
        r = run_inference(model_path, device, bench["prompt"], bench["max_tokens"])

        if "error" in r:
            print(f"  ERROR: {r['error']}")
            results["prompts"].append({"name": bench["name"], "error": r["error"]})
            continue

        print(f"  Load:   {r['load_ms']:,} ms")
        print(f"  Gen:    {r['gen_ms']:,} ms  (~{r['tok_per_sec']} tok/s)")
        if not quiet:
            print(f"  Output: {r['response'][:200]}")
        results["prompts"].append({"name": bench["name"], **r})

    return results


def interactive_chat(model_path: Path, model_name: str, device: str):
    """Simple interactive chat loop."""
    import openvino_genai as ov_genai

    print(f"\n  Loading {model_name} on {device}...")
    pipeline_config = {"MAX_PROMPT_LEN": 2048, "MIN_RESPONSE_LEN": 64}
    if device == "NPU":
        pipe = ov_genai.LLMPipeline(str(model_path), device, pipeline_config)
    else:
        pipe = ov_genai.LLMPipeline(str(model_path), device)

    print(f"  Ready! Type 'quit' to exit.\n")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye.")
            break
        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            break
        t_start = time.perf_counter()
        response = pipe.generate(user_input, max_new_tokens=512)
        elapsed = time.perf_counter() - t_start
        approx_tok = len(response) // 4
        print(f"\nAssistant: {response.strip()}")
        print(f"  [{elapsed:.1f}s, ~{approx_tok / max(elapsed, 0.001):.0f} tok/s]\n")


def main():
    parser = argparse.ArgumentParser(description="HFO NPU LLM Benchmark")
    parser.add_argument("--status", action="store_true", help="Show model download status")
    parser.add_argument("--model", type=str, help="Model short name to bench (e.g. 'qwen3-1.7b')")
    parser.add_argument("--device", type=str, default="NPU",
                        choices=["NPU", "CPU", "GPU"], help="Inference device")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive chat mode")
    parser.add_argument("--download", type=str, metavar="SHORTNAME",
                        help="Download a pre-built model by registry short name")
    parser.add_argument("--download-all", action="store_true",
                        help="Download all pre-built (non-export) registry models")
    parser.add_argument("--export", type=str, metavar="SHORTNAME",
                        help="Export a model from HuggingFace (e.g. qwen2.5-3b)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress response text")

    args = parser.parse_args()

    if args.status:
        print_model_status()
        return

    if args.download:
        # Find in registry
        lower = args.download.lower()
        for local_dir, hf_repo, name, size_gb, device in MODEL_REGISTRY:
            if lower in name.lower() or lower in local_dir.lower():
                download_model(local_dir, hf_repo)
                return
        print(f"  [ERROR] No registry entry matches: {args.download}")
        print_model_status()
        return

    if args.download_all:
        # Download all pre-built (those not requiring export)
        prebuilt = [r for r in MODEL_REGISTRY if "FluidInference" in r[1] or "OpenVINO/" in r[1]]
        for local_dir, hf_repo, name, size_gb, device in prebuilt:
            path = MODELS_DIR / local_dir
            if path.exists() and any(path.iterdir()):
                print(f"  [SKIP] {name} already downloaded")
            else:
                download_model(local_dir, hf_repo)
        return

    if args.export:
        export_model_to_npu(args.export)
        return

    # ── Run benchmark ──────────────────────────────────────────────────────────
    available = get_available_models()
    if not available:
        print("\n  [!] No models found in", MODELS_DIR)
        print("  Download first with: python hfo_npu_llm_bench.py --download qwen3-1.7b")
        print_model_status()
        return

    # Filter by --model if specified
    if args.model:
        lower = args.model.lower()
        available = [(p, r, n, s, d) for p, r, n, s, d in available
                     if lower in n.lower() or lower in p.name.lower()]
        if not available:
            print(f"  [ERROR] No downloaded model matches: {args.model}")
            print_model_status()
            return

    all_results = []
    for model_path, hf_repo, name, size_gb, default_device in available:
        device = args.device

        if args.interactive:
            interactive_chat(model_path, name, device)
        else:
            results = bench_model(model_path, name, device, quiet=args.quiet)
            all_results.append(results)

    if all_results and not args.interactive:
        # Summary table
        print(f"\n{'=' * 60}")
        print("  BENCHMARK SUMMARY")
        print(f"{'=' * 60}")
        print(f"  {'Model':<22} {'Device':<5}  {'Prompt':<20}  {'Gen(ms)':>8}  {'tok/s':>6}")
        print(f"  {'-'*22} {'-'*5}  {'-'*20}  {'-'*8}  {'-'*6}")
        for r in all_results:
            for p in r.get("prompts", []):
                if "error" not in p:
                    print(f"  {r['model']:<22} {r['device']:<5}  {p['name']:<20}"
                          f"  {p['gen_ms']:>8,}  {p['tok_per_sec']:>6}")

        # Save results
        result_file = HFO_ROOT / f".npu_bench_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_file, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "device": args.device,
                "results": all_results,
            }, f, indent=2)
        print(f"\n  Results saved: {result_file.name}")


if __name__ == "__main__":
    main()
