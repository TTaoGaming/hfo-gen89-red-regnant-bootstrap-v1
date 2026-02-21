#!/usr/bin/env python3
"""
hfo_eval_orchestrator.py — Perceive → Eval Harness → Yield orchestrator

Lightweight runner that performs a PREY8 perceive, runs the `prey8_eval_harness.py`
against a chosen model, saves run artifacts, and calls the PREY8 yield bookend.

Usage examples:
  python hfo_eval_orchestrator.py --model qwen2.5:7b --limit 5 --once
  python hfo_eval_orchestrator.py --model qwen2.5:7b --limit 10 --interval 3600

Designed to be run as a single long-lived runner (serialize Ollama calls),
and to be wrapped by a Windows service or Task Scheduler.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = (HERE / "../../..").resolve()
OUTDIR = HERE / "orchestrator_outputs"
OUTDIR.mkdir(parents=True, exist_ok=True)


def run_perceive(probe: str):
    cmd = [sys.executable, str(HERE / "hfo_perceive.py"), "--probe", probe, "--json"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Perceive failed: {p.stderr.strip()}")
    try:
        ctx = json.loads(p.stdout)
    except Exception:
        # fall back to best-effort parse
        raise RuntimeError("Perceive returned non-JSON output")
    return ctx


def run_eval(model: str, limit: int):
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_log = OUTDIR / f"eval_{model.replace(':','_')}_{ts}.log"
    cmd = [sys.executable, str(HERE / "prey8_eval_harness.py"), "--model", model, "--mode", "both", "--limit", str(limit)]
    with open(out_log, "w", encoding="utf-8") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, text=True)
    return proc.returncode, str(out_log)


def run_yield(summary: str, probe: str, artifacts: list):
    args = [sys.executable, str(HERE / "hfo_yield.py"), "--summary", summary, "--probe", probe, "--artifacts-created", ",".join(artifacts), "--json"]
    p = subprocess.run(args, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Yield failed: {p.stderr.strip()}")
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"note": "yield returned non-json"}


def orchestrate(model: str, limit: int, probe: str):
    # 1) Perceive
    ctx = run_perceive(probe)
    perceive_nonce = ctx.get("nonce")

    # 2) Eval
    rc, logpath = run_eval(model, limit)

    # 3) Yield
    short_sum = f"Automated eval run: model={model}, limit={limit}, rc={rc}"
    y = run_yield(summary=short_sum, probe=probe, artifacts=[logpath])

    # 4) Record an orchestrator summary
    recap = {
        "timestamp": datetime.utcnow().isoformat(),
        "model": model,
        "limit": limit,
        "perceive_nonce": perceive_nonce,
        "eval_returncode": rc,
        "log": logpath,
        "yield_receipt": y,
    }
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    recap_path = OUTDIR / f"forchestrator_recap_{model.replace(':','_')}_{ts}.json"
    recap_path.write_text(json.dumps(recap, indent=2), encoding="utf-8")
    print(f"Orchestrator run complete. Recap: {recap_path}")
    return recap


def main():
    p = argparse.ArgumentParser(description="PREY8 Eval Orchestrator — Perceive → Eval → Yield")
    p.add_argument("--model", required=True, help="Model name for the eval harness (e.g. qwen2.5:7b)")
    p.add_argument("--limit", type=int, default=5, help="Number of eval problems to run per invocation")
    p.add_argument("--probe", default=None, help="Probe text for Perceive (defaults to automated message)")
    p.add_argument("--interval", type=int, default=0, help="If >0 run as loop sleep seconds between runs")
    p.add_argument("--once", action="store_true", help="Run once and exit")
    args = p.parse_args()

    probe = args.probe or f"Automated eval run for model {args.model}"

    if args.once or args.interval == 0:
        orchestrate(args.model, args.limit, probe)
        return

    try:
        while True:
            orchestrate(args.model, args.limit, probe)
            print(f"Sleeping {args.interval} seconds...")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Orchestrator interrupted, exiting.")


if __name__ == "__main__":
    main()
