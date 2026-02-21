#!/usr/bin/env python3
"""
hfo_llm_router.py — HFO Gen89 Vendor-Agnostic LLM Router
==========================================================
Single entry-point for all LLM inference.  Handles:
  - Provider selection by role + strategy + live resources
  - Fallback chain:  NPU → Ollama → Gemini → OpenRouter
  - Resource pressure guards (RAM, VRAM)
  - Rolling NPU-utilisation tracking (20-sample window)
  - Stigmergy write on every inference + exhaustion event

Provider priority (default 'npu_first' strategy):
  NPU       — zero VRAM, local, sub-10ms for small models
  Ollama    — local GPU, only when VRAM budget allows
  Gemini    — cloud, rate-limited, no VRAM cost
  OpenRouter— paid cloud fallback, any model via API

Config (environment  / RouterConfig dataclass):
  LLM_ROUTER_STRATEGY     npu_first | ollama_first | gemini_first |
                          ollama_only | gemini_only   (default: npu_first)
  HFO_VRAM_BUDGET_GB      Total VRAM available for Ollama  (default: 10.0)
  HFO_VRAM_TARGET_PCT     Evict/skip Ollama above this %   (default: 80)
  HFO_RAM_TARGET_PCT      HOLD gate above this %           (default: 80)
  HFO_CPU_TARGET_PCT      CPU soft-ceiling                 (default: 80)
  HFO_NPU_MIN_RATE_PCT    Signal under-utilisation below   (default: 30)
  HFO_EVICT_IDLE_AFTER_S  Evict Ollama models idle this long (default: 300)
  GEMINI_API_KEY          Enable Gemini provider
  OPENROUTER_API_KEY      Enable OpenRouter provider
  P6_NPU_LLM_MODEL        Path to OpenVINO NPU model dir
  OLLAMA_BASE             Ollama base URL (default http://localhost:11434)
  HFO_SSOT_DB             Path to SSOT SQLite (optional observability)

Role → preferred provider (default):
  advisory, enricher   → NPU first
  analyst              → Ollama (gemma3:4b)
  researcher, planner,
  coder, validator     → Gemini (flash_25 / pro)

Medallion: bronze
Port: P2 SHAPE (creation) + P4 DISRUPT (adversarial)
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class RouterExhausted(Exception):
    """All providers in the fallback chain failed or were skipped."""


class ResourcePressureError(Exception):
    """RAM or VRAM pressure is too high to accept new inference requests."""


# ---------------------------------------------------------------------------
# Provider Enum  (superset of hfo_swarm_config.Provider)
# ---------------------------------------------------------------------------

class Provider(str, Enum):
    NPU        = "npu"
    OLLAMA     = "ollama"
    GEMINI     = "gemini"
    OPENROUTER = "openrouter"


# ---------------------------------------------------------------------------
# Role → (preferred_provider, preferred_model) map
# ---------------------------------------------------------------------------

ROLE_MAP: Dict[str, Dict[str, str]] = {
    "advisory":   {"provider": Provider.NPU.value,    "model": ""},
    "enricher":   {"provider": Provider.NPU.value,    "model": ""},
    "analyst":    {"provider": Provider.OLLAMA.value, "model": "qwen3:8b"},        # upgraded: 8B > 4B, fits in 16GB VRAM
    "researcher": {"provider": Provider.GEMINI.value, "model": "flash_25"},
    "planner":    {"provider": Provider.GEMINI.value, "model": "pro"},
    "coder":      {"provider": Provider.OLLAMA.value, "model": "qwen2.5-coder:7b"}, # local dedicated coder, saves Gemini tokens
    "validator":  {"provider": Provider.GEMINI.value, "model": "pro"},
    "triage":     {"provider": Provider.OLLAMA.value, "model": "qwen2.5:3b"},
    "router":     {"provider": Provider.OLLAMA.value, "model": "qwen2.5:3b"},
}

# Strategy → ordered provider chain
STRATEGY_CHAINS: Dict[str, List[str]] = {
    "npu_first":    [Provider.NPU, Provider.OLLAMA, Provider.GEMINI, Provider.OPENROUTER],
    "ollama_first": [Provider.OLLAMA, Provider.NPU, Provider.GEMINI, Provider.OPENROUTER],
    "gemini_first": [Provider.GEMINI, Provider.NPU, Provider.OLLAMA, Provider.OPENROUTER],
    "ollama_only":  [Provider.OLLAMA],
    "gemini_only":  [Provider.GEMINI],
}


# ---------------------------------------------------------------------------
# RouterConfig
# ---------------------------------------------------------------------------

@dataclass
class RouterConfig:
    """Immutable router configuration.  Build via from_env() or pass directly."""

    strategy: str = "npu_first"

    # NPU
    npu_model_path: Optional[str] = None

    # Resource budgets
    vram_budget_gb: float = 10.0
    vram_target_pct: float = 80.0   # evict/skip Ollama above this
    ram_target_pct: float = 80.0    # emit HOLD above this
    cpu_target_pct: float = 60.0    # matches HFO_GOV_CPU_OVER_PCT / orchestrator target
    npu_min_rate_pct: float = 30.0  # underutilisation signal threshold
    evict_idle_after_s: float = 300.0

    # Credentials
    gemini_api_key: str = ""
    openrouter_api_key: str = ""

    # Observability
    db_path: Optional[Path] = None

    # Test injection overrides (set > 0 to bypass live psutil reads)
    vram_used_gb: float = 0.0    # 0.0 = read live
    ram_pct: float = 0.0         # 0.0 = read live

    @classmethod
    def from_env(cls, db_path: Optional[Path] = None) -> "RouterConfig":
        """Build config from environment variables, with .env auto-load."""
        _load_dotenv_once()
        return cls(
            strategy=os.getenv("LLM_ROUTER_STRATEGY", "npu_first"),
            npu_model_path=os.getenv("P6_NPU_LLM_MODEL") or None,
            vram_budget_gb=float(os.getenv("HFO_VRAM_BUDGET_GB", "10.0")),
            vram_target_pct=float(os.getenv("HFO_VRAM_TARGET_PCT", "80")),
            ram_target_pct=float(os.getenv("HFO_RAM_TARGET_PCT", "80")),
            cpu_target_pct=float(os.getenv("HFO_CPU_TARGET_PCT", "80")),
            npu_min_rate_pct=float(os.getenv("HFO_NPU_MIN_RATE_PCT", "30")),
            evict_idle_after_s=float(os.getenv("HFO_EVICT_IDLE_AFTER_S", "300")),
            gemini_api_key=os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", "")),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
            db_path=db_path or _default_db_path(),
        )

    @property
    def vram_target_gb(self) -> float:
        return self.vram_budget_gb * self.vram_target_pct / 100.0


# ---------------------------------------------------------------------------
# LLMRouter
# ---------------------------------------------------------------------------

RAM_BLOCK_THRESHOLD_PCT: float = 95.0   # hard block — too dangerous to proceed


class LLMRouter:
    """
    Vendor-agnostic LLM router.

    Usage:
        router = LLMRouter(RouterConfig.from_env(db_path=...))
        result = router.generate("Assess this event", role="advisory")
        # → {"response": "...", "provider": "npu", "model": "...", "latency_ms": 42.3, ...}
    """

    def __init__(self, config: RouterConfig) -> None:
        self.config = config
        self._window: Deque[str] = deque(maxlen=20)   # provider names, last 20 calls
        self.last_attempt_chain: List[str] = []
        self._npu_pipeline: Optional[Any] = None      # lazy-init OpenVINO pipeline
        self._npu_init_attempted: bool = False

    # ── Public API ──────────────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        role: str = "advisory",
        system: Optional[str] = None,
        max_tokens: int = 200,
        # test injection hooks
        _mock_ollama_error: bool = False,
        _mock_gemini_status: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Route a prompt to the best available provider.

        Returns dict with keys:
          response, provider, model, latency_ms, tokens,
          fallback_used, reason, [skip_reason]
        """
        # ── Resource pressure guard (hard block) ────────────────────────────
        live_ram = self._live_ram_pct()
        if live_ram >= RAM_BLOCK_THRESHOLD_PCT:
            self._write_stigmergy("hfo.gen89.llm_router.ram_blocked", {
                "role": role,
                "ram_pct": live_ram,
            })
            raise ResourcePressureError(
                f"RAM at {live_ram:.1f}% — above hard block threshold {RAM_BLOCK_THRESHOLD_PCT}%"
            )

        chain = self._build_chain(role)
        self.last_attempt_chain = []
        # Maps provider name → reason string (skip or exception message)
        # Ordered dict so we can reconstruct the causal chain in order.
        errors: Dict[str, str] = {}
        providers_tried: int = 0   # skipped + failed providers before current

        for provider in chain:
            pname = provider.value if isinstance(provider, Provider) else str(provider)
            self.last_attempt_chain.append(pname)

            # Skip checks per provider
            skip_reason = self._should_skip(provider, live_ram)
            if skip_reason:
                errors[pname] = f"skipped:{skip_reason}"
                providers_tried += 1
                continue

            t0 = time.perf_counter()
            try:
                response_text, model_name = self._dispatch(
                    provider=provider,
                    prompt=prompt,
                    system=system,
                    max_tokens=max_tokens,
                    role=role,
                    _mock_ollama_error=_mock_ollama_error,
                    _mock_gemini_status=_mock_gemini_status,
                )
                latency_ms = (time.perf_counter() - t0) * 1000
                tokens = len(response_text.split())
                fallback_used = providers_tried > 0

                # Determine the reason we ended up here — scan errors LIFO
                # (most-recent failure wins, e.g. 429 beats vram_pressure)
                reason = "primary"
                if fallback_used:
                    reason = "fallback"
                    # Walk in reverse order; first match wins
                    for prev_err in reversed(list(errors.values())):
                        if "429" in prev_err or "rate_limited" in prev_err:
                            reason = "gemini_rate_limited"
                            break
                        if "vram_pressure" in prev_err:
                            reason = "vram_pressure"
                            break

                result = {
                    "response": response_text,
                    "provider": pname,
                    "model": model_name,
                    "latency_ms": round(latency_ms, 2),
                    "tokens": tokens,
                    "fallback_used": fallback_used,
                    "reason": reason,
                    "port": self._role_to_port(role),
                }
                self._record_inference(pname, model_name, latency_ms, tokens)
                self._write_stigmergy("hfo.gen89.llm_router.inference", {
                    **result, "prompt_len": len(prompt),
                })
                return result

            except Exception as exc:
                latency_ms = (time.perf_counter() - t0) * 1000
                errors[pname] = str(exc)
                providers_tried += 1
                continue

        # All providers exhausted
        self._write_stigmergy("hfo.gen89.llm_router.exhausted", {
            "role": role,
            "chain": self.last_attempt_chain,
            "errors": errors,
        })
        raise RouterExhausted(
            f"All providers exhausted for role={role!r}. "
            f"Chain: {self.last_attempt_chain}. Errors: {errors}"
        )

    def select_for_role(self, role: str) -> Dict[str, str]:
        """Return the preferred {provider, model} for a role, no inference."""
        entry = ROLE_MAP.get(role) or ROLE_MAP.get("advisory")
        assert entry is not None
        # If preferred is NPU but NPU is unavailable, fall back
        if entry["provider"] == Provider.NPU.value and not self._npu_available():
            ollama_entry = ROLE_MAP.get("analyst", {})
            return {
                "provider": Provider.OLLAMA.value,
                "model": ollama_entry.get("model", "qwen2.5:3b"),
            }
        return {"provider": entry["provider"], "model": entry["model"]}

    def npu_utilisation_rate(self) -> float:
        """Fraction of last 20 inferences that used NPU.  0.0–1.0."""
        if not self._window:
            return 0.0
        return sum(1 for p in self._window if p == Provider.NPU.value) / len(self._window)

    def _record_inference(self, provider: str, model: str,
                          latency_ms: float, tokens: int) -> None:
        """Update the rolling utilisation window."""
        self._window.append(provider)

    # ── Chain building ───────────────────────────────────────────────────────

    def _build_chain(self, role: str) -> List[Provider]:
        """Return ordered provider chain for this strategy, role-hinted."""
        strategy = self.config.strategy
        base_chain: List[Provider] = list(STRATEGY_CHAINS.get(strategy, STRATEGY_CHAINS["npu_first"]))

        # If the role has a strong preference and strategy is npu_first, honour it
        if strategy == "npu_first":
            entry = ROLE_MAP.get(role)
            if entry:
                preferred = entry["provider"]
                # Promote preferred to front if not already there
                preferred_enum = Provider(preferred)
                if preferred_enum in base_chain and base_chain[0] != preferred_enum:
                    base_chain.remove(preferred_enum)
                    base_chain.insert(0, preferred_enum)

        return base_chain

    def _should_skip(self, provider: Provider, live_ram: float) -> Optional[str]:
        """Return a skip reason string if provider should be bypassed, else None."""
        cfg = self.config

        if provider == Provider.NPU:
            if not self._npu_available():
                return "npu_unavailable"
            return None

        if provider == Provider.OLLAMA:
            vram_used = self._live_vram_used_gb()
            if vram_used >= cfg.vram_target_gb:
                return f"vram_pressure:{vram_used:.1f}gb>={cfg.vram_target_gb:.1f}gb"
            return None

        if provider == Provider.GEMINI:
            if not cfg.gemini_api_key:
                return "no_gemini_key"
            return None

        if provider == Provider.OPENROUTER:
            if not cfg.openrouter_api_key:
                return "no_openrouter_key"
            return None

        return None

    # ── Provider Dispatch ────────────────────────────────────────────────────

    def _dispatch(
        self,
        provider: Provider,
        prompt: str,
        system: Optional[str],
        max_tokens: int,
        role: str,
        _mock_ollama_error: bool,
        _mock_gemini_status: Optional[int],
    ) -> tuple[str, str]:
        """Call the provider.  Returns (response_text, model_name)."""
        if provider == Provider.NPU:
            text = self._call_npu(prompt=prompt, system=system, max_tokens=max_tokens)
            return text, str(self.config.npu_model_path or "npu-local")

        if provider == Provider.OLLAMA:
            model = ROLE_MAP.get(role, {}).get("model") or "qwen2.5:3b"
            if _mock_ollama_error:
                raise ConnectionError("mock_ollama_error")
            text = self._call_ollama(
                prompt=prompt, system=system, model=model, max_tokens=max_tokens
            )
            return text, model

        if provider == Provider.GEMINI:
            if _mock_gemini_status == 429:
                raise Exception("429 rate limit exceeded")
            model = ROLE_MAP.get(role, {}).get("model") or "flash_25"
            text = self._call_gemini(
                prompt=prompt, system=system, tier=model, max_tokens=max_tokens
            )
            return text, f"gemini:{model}"

        if provider == Provider.OPENROUTER:
            model = "google/gemini-flash-1.5"   # sensible default
            text = self._call_openrouter(
                prompt=prompt, system=system, model=model, max_tokens=max_tokens
            )
            return text, f"openrouter:{model}"

        raise ValueError(f"Unknown provider: {provider}")

    # ── Provider Implementations ─────────────────────────────────────────────

    def _call_npu(self, prompt: str, system: Optional[str] = None,
                  max_tokens: int = 200) -> str:
        """Run inference on Intel NPU via OpenVINO GenAI."""
        pipeline = self._get_npu_pipeline()
        if pipeline is None:
            raise RuntimeError("NPU pipeline is not available")
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        result = pipeline.generate(full_prompt, max_new_tokens=max_tokens)
        # OpenVINO GenAI returns a string directly
        return str(result).strip() if result else ""

    def _call_ollama(self, prompt: str, model: str = "qwen2.5:3b",
                     system: Optional[str] = None, max_tokens: int = 200) -> str:
        """POST to local Ollama /api/generate."""
        base = os.getenv("OLLAMA_BASE", "http://localhost:11434")
        url = f"{base}/api/generate"
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.3},
        }
        if system:
            payload["system"] = system
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode())
        return data.get("response", "").strip()

    def _call_gemini(self, prompt: str, tier: str = "flash_25",
                     system: Optional[str] = None, max_tokens: int = 200) -> str:
        """Call Gemini via google-generativeai (or google-genai) SDK."""
        api_key = self.config.gemini_api_key
        if not api_key:
            raise RuntimeError("No GEMINI_API_KEY configured")

        # Try google-generativeai (older SDK, widely installed)
        try:
            import google.generativeai as genai  # type: ignore
            genai.configure(api_key=api_key)
            model_id = _gemini_tier_to_model_id(tier)
            model = genai.GenerativeModel(
                model_id,
                system_instruction=system or "",
                generation_config={"max_output_tokens": max_tokens},
            )
            resp = model.generate_content(prompt)
            return resp.text.strip() if hasattr(resp, "text") else ""
        except ImportError:
            pass

        # Try google-genai (newer SDK)
        try:
            from google import genai as genai2  # type: ignore
            client = genai2.Client(api_key=api_key)
            model_id = _gemini_tier_to_model_id(tier)
            resp = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config={"max_output_tokens": max_tokens,
                        "system_instruction": system or ""},
            )
            return resp.text.strip() if hasattr(resp, "text") else ""
        except ImportError:
            raise RuntimeError("Neither google-generativeai nor google-genai is installed")

    def _call_openrouter(self, prompt: str, model: str = "google/gemini-flash-1.5",
                         system: Optional[str] = None, max_tokens: int = 200) -> str:
        """POST to OpenRouter chat completions API."""
        api_key = self.config.openrouter_api_key
        if not api_key:
            raise RuntimeError("No OPENROUTER_API_KEY configured")
        url = "https://openrouter.ai/api/v1/chat/completions"
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": model, "messages": messages,
                   "max_tokens": max_tokens, "temperature": 0.3}
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {api_key}",
                     "HTTP-Referer": "https://github.com/hfo",
                     "X-Title": "HFO Gen89"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"].strip()

    # ── NPU Lazy Init ─────────────────────────────────────────────────────────

    def _npu_available(self) -> bool:
        """True if NPU model directory exists and openvino_genai importable."""
        model_path = self.config.npu_model_path
        if not model_path:
            return False
        if not Path(model_path).exists():
            return False
        try:
            import openvino_genai  # type: ignore  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_npu_pipeline(self) -> Optional[Any]:
        """Lazy-init the OpenVINO GenAI pipeline.  None if unavailable."""
        if self._npu_init_attempted:
            return self._npu_pipeline
        self._npu_init_attempted = True
        model_path = self.config.npu_model_path
        if not model_path or not Path(model_path).exists():
            return None
        try:
            import openvino_genai as ov_genai  # type: ignore
            self._npu_pipeline = ov_genai.LLMPipeline(str(model_path), "NPU")
            return self._npu_pipeline
        except Exception:
            return None

    # ── Live Resource Reads ──────────────────────────────────────────────────

    def _live_ram_pct(self) -> float:
        """RAM usage %.  Returns config override if set (> 0), else psutil."""
        if self.config.ram_pct > 0:
            return self.config.ram_pct
        try:
            import psutil  # type: ignore
            return psutil.virtual_memory().percent
        except Exception:
            return 0.0

    def _live_vram_used_gb(self) -> float:
        """VRAM used GB.  Returns config override if set (> 0), else Ollama /api/ps."""
        if self.config.vram_used_gb > 0:
            return self.config.vram_used_gb
        try:
            base = os.getenv("OLLAMA_BASE", "http://localhost:11434")
            with urllib.request.urlopen(f"{base}/api/ps", timeout=3) as resp:
                data = json.loads(resp.read().decode())
            total = sum(m.get("size_vram", 0) for m in data.get("models", []))
            return total / (1024 ** 3)
        except Exception:
            return 0.0

    # ── Stigmergy ────────────────────────────────────────────────────────────

    def _write_stigmergy(self, event_type: str, data: Dict[str, Any]) -> None:
        """Write a CloudEvent-structured row to stigmergy_events."""
        db_path = self.config.db_path
        if not db_path or not Path(db_path).exists():
            return
        ts = datetime.now(timezone.utc).isoformat()
        data_json = json.dumps(data, default=str)
        content_hash = hashlib.sha256(
            f"{event_type}:{ts}:{data_json}".encode()
        ).hexdigest()
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                """INSERT OR IGNORE INTO stigmergy_events
                   (event_type, timestamp, subject, data_json, content_hash)
                   VALUES (?, ?, ?, ?, ?)""",
                (event_type, ts, "llm_router", data_json, content_hash),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _role_to_port(role: str) -> str:
        _map = {
            "advisory": "P0", "enricher": "P6", "analyst": "P2",
            "researcher": "P2", "planner": "P7", "coder": "P2",
            "validator": "P5", "triage": "P7", "router": "P7",
        }
        return _map.get(role, "P2")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gemini_tier_to_model_id(tier: str) -> str:
    """Map tier alias → actual Gemini model ID."""
    _MAP = {
        "nano":         "gemini-2.5-flash-lite",
        "flash":        "gemini-2.5-flash",
        "flash_25":     "gemini-2.5-flash",
        "lite_25":      "gemini-2.5-flash-lite",
        "pro":          "gemini-2.5-pro",
        "experimental": "gemini-2.5-pro",
    }
    return _MAP.get(tier, tier)  # pass through if already a model ID


def _default_db_path() -> Optional[Path]:
    """Walk up from this file to find the SSOT database."""
    try:
        candidate = (
            Path(__file__).resolve().parents[3]
            / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
        )
        return candidate if candidate.exists() else None
    except Exception:
        return None


def _load_dotenv_once() -> None:
    """Load .env from HFO_ROOT if python-dotenv is available."""
    try:
        from dotenv import load_dotenv  # type: ignore
        for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
            for candidate in [anchor, *anchor.parents]:
                env_path = candidate / ".env"
                if env_path.exists() and (candidate / "AGENTS.md").exists():
                    load_dotenv(env_path, override=False)
                    return
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HFO LLM Router smoke-test")
    parser.add_argument("--prompt", default="Briefly describe the HFO octree.")
    parser.add_argument("--role", default="advisory")
    parser.add_argument("--strategy", default=None)
    args = parser.parse_args()

    cfg = RouterConfig.from_env()
    if args.strategy:
        cfg = RouterConfig(**{**cfg.__dict__, "strategy": args.strategy})

    router = LLMRouter(cfg)
    print(f"Strategy : {cfg.strategy}")
    print(f"NPU path : {cfg.npu_model_path}")
    print(f"Gemini   : {'YES' if cfg.gemini_api_key else 'NO'}")
    print(f"OR key   : {'YES' if cfg.openrouter_api_key else 'NO'}")
    print(f"VRAM used: {router._live_vram_used_gb():.2f} GB / {cfg.vram_budget_gb} GB")
    print(f"RAM pct  : {router._live_ram_pct():.1f}%")
    print()

    try:
        result = router.generate(args.prompt, role=args.role)
        print(f"Provider   : {result['provider']} ({result['model']})")
        print(f"Latency    : {result['latency_ms']:.0f} ms")
        print(f"Fallback   : {result['fallback_used']} (reason={result['reason']})")
        print(f"Response   : {result['response'][:200]}")
    except RouterExhausted as e:
        print(f"EXHAUSTED  : {e}")
    except ResourcePressureError as e:
        print(f"RAM BLOCK  : {e}")
