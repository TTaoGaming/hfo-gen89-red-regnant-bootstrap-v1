"""
Step definitions for gpu_utilization.feature and ollama_fleet.feature.

Real integration tests — hit Ollama API, check env, run vulkaninfo.
"""

import json
import os
import subprocess

from behave import given, when, then


# ═══════════════════════════════════════════════════════════════════
#  SHARED / BACKGROUND
# ═══════════════════════════════════════════════════════════════════

@given('Ollama API is reachable at the configured host')
def step_ollama_reachable(context):
    r = context.http.get(f"{context.ollama_base}/api/version")
    assert r.status_code == 200, f"Ollama not reachable: {r.status_code}"
    context.ollama_version = r.json().get("version", "unknown")


# ═══════════════════════════════════════════════════════════════════
#  GPU UTILIZATION
# ═══════════════════════════════════════════════════════════════════

@then('the environment variable "{name}" is "{value}"')
def step_env_var(context, name, value):
    actual = os.environ.get(name, "")
    assert actual == value, f"Expected {name}={value}, got '{actual}'"


@when('I query Ollama for available GPUs')
def step_query_gpus(context):
    # Generate 1 token so a model is loaded, then check /api/ps
    body = {"model": "qwen2.5:3b", "prompt": "hi", "stream": False,
            "options": {"num_predict": 1}}
    r = context.http.post(f"{context.ollama_base}/api/generate", json=body,
                          timeout=120)
    assert r.status_code == 200, f"Generate failed: {r.status_code}"
    ps = context.http.get(f"{context.ollama_base}/api/ps").json()
    context.loaded_models = ps.get("models", [])


@then('at least {n:d} GPU is reported')
def step_gpu_count(context, n):
    has_gpu = any(m.get("size_vram", 0) > 0 for m in context.loaded_models)
    assert has_gpu, "No models using VRAM — GPU not active"


@then('the GPU name contains "{fragment}"')
def step_gpu_name(context, fragment):
    vulkaninfo = r"C:\Windows\System32\vulkaninfo.exe"
    if not os.path.exists(vulkaninfo):
        vulkaninfo = "vulkaninfo"
    r = subprocess.run([vulkaninfo, "--summary"],
                       capture_output=True, text=True, timeout=15)
    combined = r.stdout + r.stderr
    assert fragment.lower() in combined.lower(), \
        f"GPU name does not contain '{fragment}'. Output snippet: {combined[:400]}"


@given('model "{name}" is available')
def step_model_available(context, name):
    r = context.http.get(f"{context.ollama_base}/api/tags")
    models = [m["name"] for m in r.json().get("models", [])]
    matched = any(name in m for m in models)
    assert matched, f"Model {name} not in fleet: {models}"


@given('model "{name}" is loaded in VRAM')
def step_model_loaded(context, name):
    body = {"model": name, "prompt": "hi", "stream": False,
            "options": {"num_predict": 1}}
    context.http.post(f"{context.ollama_base}/api/generate", json=body,
                      timeout=120)
    ps = context.http.get(f"{context.ollama_base}/api/ps").json()
    loaded = [m["name"] for m in ps.get("models", [])]
    assert any(name in m for m in loaded), \
        f"Model {name} not loaded. Loaded: {loaded}"


@when('I generate {n:d} tokens with model "{name}"')
def step_generate(context, n, name):
    body = {"model": name,
            "prompt": "Explain quantum computing briefly.",
            "stream": False,
            "options": {"num_predict": n}}
    r = context.http.post(f"{context.ollama_base}/api/generate", json=body,
                          timeout=120)
    assert r.status_code == 200, f"Generate failed: {r.status_code}"
    data = r.json()
    context.last_gen = data

    eval_dur = data.get("eval_duration", 1) / 1e9
    eval_count = data.get("eval_count", 0)
    prompt_dur = data.get("prompt_eval_duration", 1) / 1e9
    prompt_count = data.get("prompt_eval_count", 0)

    context.gen_tps = eval_count / max(eval_dur, 0.001)
    context.prompt_tps = prompt_count / max(prompt_dur, 0.001)


@then('the model "{name}" is loaded')
def step_model_is_loaded(context, name):
    ps = context.http.get(f"{context.ollama_base}/api/ps").json()
    loaded = [m["name"] for m in ps.get("models", [])]
    assert any(name in m for m in loaded), \
        f"{name} not loaded. Loaded: {loaded}"


@then('VRAM usage for "{name}" is greater than 0 bytes')
def step_vram_nonzero(context, name):
    ps = context.http.get(f"{context.ollama_base}/api/ps").json()
    for m in ps.get("models", []):
        if name in m["name"]:
            vram = m.get("size_vram", 0)
            assert vram > 0, f"VRAM for {name} is {vram} (expected > 0)"
            return
    assert False, f"Model {name} not found in /api/ps"


@then('generation throughput is at least the configured minimum tok/s')
def step_gen_throughput(context):
    thr = context.thresholds["min_gen_tps"]
    assert context.gen_tps >= thr, \
        f"Gen throughput {context.gen_tps:.1f} tok/s < threshold {thr}"


@then('prompt throughput is at least the configured minimum tok/s')
def step_prompt_throughput(context):
    thr = context.thresholds["min_prompt_tps"]
    assert context.prompt_tps >= thr, \
        f"Prompt throughput {context.prompt_tps:.1f} tok/s < threshold {thr}"


# ═══════════════════════════════════════════════════════════════════
#  OLLAMA FLEET
# ═══════════════════════════════════════════════════════════════════

@when('I query Ollama version')
def step_query_version(context):
    r = context.http.get(f"{context.ollama_base}/api/version")
    context.ollama_version = r.json().get("version", "0.0.0")


@then('the version is at least "{min_ver}"')
def step_version_check(context, min_ver):
    def _parse(v):
        return tuple(int(x) for x in v.split(".")[:3])
    try:
        assert _parse(context.ollama_version) >= _parse(min_ver), \
            f"Version {context.ollama_version} < {min_ver}"
    except ValueError:
        assert context.ollama_version >= min_ver


@when('I list available Ollama models')
def step_list_models(context):
    r = context.http.get(f"{context.ollama_base}/api/tags")
    context.available_models = r.json().get("models", [])


@then('at least the configured minimum number of models are available')
def step_min_models(context):
    n = context.thresholds["min_models_available"]
    actual = len(context.available_models)
    assert actual >= n, f"Only {actual} models, need {n}"


@then('there is at least {n:d} model under {gb:d} GB')
def step_model_under_size(context, n, gb):
    small = [m for m in context.available_models
             if m.get("size", 0) / (1024**3) < gb]
    assert len(small) >= n, \
        f"Only {len(small)} models under {gb}GB (need {n})"


@then('there is at least {n:d} model between {lo:d} GB and {hi:d} GB')
def step_model_between_size(context, n, lo, hi):
    mid = [m for m in context.available_models
           if lo <= m.get("size", 0) / (1024**3) < hi]
    assert len(mid) >= n, \
        f"Only {len(mid)} models between {lo}-{hi}GB (need {n})"


@when('I check loaded models')
def step_check_loaded(context):
    ps = context.http.get(f"{context.ollama_base}/api/ps").json()
    context.loaded_models = ps.get("models", [])


@then('at most {n:d} models are loaded in memory')
def step_max_loaded(context, n):
    actual = len(context.loaded_models)
    assert actual <= n, f"{actual} models loaded, max allowed is {n}"
