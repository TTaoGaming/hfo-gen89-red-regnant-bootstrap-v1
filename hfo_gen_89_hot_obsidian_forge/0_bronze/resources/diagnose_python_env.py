#!/usr/bin/env python3
"""diagnose_python_env.py

Run a Python-level diagnostic to report installed packages and environment variables
relevant to Ollama, OpenVINO/oneAPI, and common inference runtimes.

Usage:
  python diagnose_python_env.py --json
"""

import json
import os
import subprocess
from importlib import util

PKGS = [
    "ollama",
    "openvino",
    "intel_extension_for_pytorch",
    "transformers",
    "accelerate",
    "torch",
]


def check_imports():
    out = {}
    for p in PKGS:
        spec = util.find_spec(p)
        if spec is None:
            out[p] = None
            continue
        try:
            mod = __import__(p)
            ver = getattr(mod, "__version__", None)
            out[p] = ver or str(mod)
        except Exception as e:
            out[p] = f"import_error: {e}"
    return out


def check_ollama_cli():
    try:
        res = subprocess.run(["ollama", "--version"], capture_output=True, text=True, timeout=5)
        return res.stdout.strip() or res.stderr.strip()
    except Exception as e:
        return f"ollama_cli_missing_or_error: {e}"


def main():
    report = {}
    report["env_vars"] = {k: os.environ.get(k) for k in ["OLLAMA_HOST", "OLLAMA_MODEL", "HFO_FORGE"]}
    report["python_packages"] = check_imports()
    report["ollama_cli"] = check_ollama_cli()

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
