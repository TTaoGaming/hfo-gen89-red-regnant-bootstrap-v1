#!/usr/bin/env python3
"""Minimal Qwen3 NPU generate test — isolate crash."""
import sys, traceback, time, os

MODEL_PATH = r"C:\hfoDev\.hfo_models\npu_llm\qwen3-1.7b-int4-ov-npu"

try:
    import openvino_genai as ov_genai
    print(f"[OK] openvino_genai imported")
except ImportError as e:
    print(f"[FAIL] import: {e}")
    sys.exit(1)

# --- Test 1: Tiny prompt ---
print(f"\n[1] Loading pipeline (MAX_PROMPT_LEN=2048)...")
t0 = time.perf_counter()
try:
    pipe = ov_genai.LLMPipeline(MODEL_PATH, "NPU", MAX_PROMPT_LEN=2048)
    print(f"    Loaded in {(time.perf_counter()-t0)*1000:.0f}ms")
except Exception as e:
    traceback.print_exc()
    sys.exit(1)

# Test tiny prompt first
for label, prompt, max_tok in [
    ("TINY (20 chars)", "Hello, who are you?", 30),
    ("MEDIUM (100 chars)", "Answer in one sentence: What is the HFO swarm?", 60),
    ("PLAIN_RAG (400 chars)",
     "You are an assistant.\n---\nThe HFO swarm is controlled by "
     "the Spider Sovereign via a Galois lattice.\n---\nQuestion: Who controls HFO?\nAnswer:",
     80),
]:
    print(f"\n[2] Testing {label}...")
    print(f"    prompt len={len(prompt)} chars")
    try:
        t1 = time.perf_counter()
        output = pipe.generate(prompt, max_new_tokens=max_tok)
        gen_ms = (time.perf_counter()-t1)*1000
        print(f"    Generated in {gen_ms:.0f}ms")
        print(f"    output type: {type(output)}")
        # Try different extraction methods
        try:
            texts = output.texts
            print(f"    output.texts: {texts}")
        except AttributeError:
            pass
        try:
            text = str(output)
            print(f"    str(output) first 200: {repr(text[:200])}")
        except Exception as e2:
            print(f"    str(output) failed: {e2}")
    except Exception as e:
        print(f"    EXCEPTION during generate:")
        traceback.print_exc()

print("\n[DONE] All tests complete.")
