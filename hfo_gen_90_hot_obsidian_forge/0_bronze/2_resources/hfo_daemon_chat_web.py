#!/usr/bin/env python3
"""
hfo_daemon_chat_web.py - HFO Gen90 Daemon Chat Web App
========================================================
aiohttp-powered web interface for live stigmergy monitoring
and interactive chat with any of the 8 Octree port commanders.

Opens in your browser. No terminal UI knowledge required.

Features:
  - Live stigmergy event feed (auto-polls every 3s)
  - 8 port commanders + ALL channel
  - Interactive Ollama chat with per-port persona
  - FTS5 search across SSOT
  - All chat exchanges logged as stigmergy CloudEvents
  - Dark theme, responsive layout

Usage:
    python hfo_daemon_chat_web.py
    python hfo_daemon_chat_web.py --port 8089
    python hfo_daemon_chat_web.py --model gemma3:12b
    python hfo_daemon_chat_web.py --no-open

REST API:
    GET  /api/ports               - Port registry
    GET  /api/stigmergy?limit=50  - Stigmergy events
    POST /api/chat                - Chat with daemon
    GET  /api/search?q=term       - FTS5 search
    GET  /api/stats               - SSOT stats
    GET  /api/models              - Loaded Ollama models

Medallion: bronze
Port: P1 BRIDGE (shared data fabric) + P7 NAVIGATE (C2 interface)
Schema: hfo.gen90.web.daemon_chat.v1
Pointer key: web.daemon_chat
"""

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import sqlite3
import sys
import webbrowser
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

import httpx
from aiohttp import web

# ── Path resolution ─────────────────────────────────────────

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = _find_root()
DB_PATH = (
    HFO_ROOT
    / "hfo_gen_90_hot_obsidian_forge"
    / "2_gold"
    / "resources"
    / "hfo_gen90_ssot.sqlite"
)
GEN = os.environ.get("HFO_GENERATION", "89")
OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# ── Port Registry ───────────────────────────────────────────

PORTS = [
    {
        "port_id": "P0", "powerword": "OBSERVE", "commander": "Lidless Legion",
        "title": "Watcher of Whispers and Wrath",
        "spell": "TRUE SEEING", "school": "Divination",
        "symbol": "\u2630", "element": "Heaven",
        "color": "#4fc3f7", "prey8": "PERCEIVE",
    },
    {
        "port_id": "P1", "powerword": "BRIDGE", "commander": "Web Weaver",
        "title": "Binder of Blood and Breath",
        "spell": "FORBIDDANCE", "school": "Abjuration",
        "symbol": "\u2631", "element": "Lake",
        "color": "#81c784", "prey8": "REACT",
    },
    {
        "port_id": "P2", "powerword": "SHAPE", "commander": "Mirror Magus",
        "title": "Maker of Myths and Meaning",
        "spell": "GENESIS", "school": "Conjuration",
        "symbol": "\u2632", "element": "Fire",
        "color": "#ffb74d", "prey8": "EXECUTE",
    },
    {
        "port_id": "P3", "powerword": "INJECT", "commander": "Harmonic Hydra",
        "title": "Harbinger of Harmony and Havoc",
        "spell": "GATE", "school": "Conjuration",
        "symbol": "\u2633", "element": "Thunder",
        "color": "#e57373", "prey8": "YIELD",
    },
    {
        "port_id": "P4", "powerword": "DISRUPT", "commander": "Red Regnant",
        "title": "Singer of Strife and Splendor",
        "spell": "WEIRD", "school": "Illusion",
        "symbol": "\u2634", "element": "Wind",
        "color": "#f44336", "prey8": "EXECUTE",
    },
    {
        "port_id": "P5", "powerword": "IMMUNIZE", "commander": "Pyre Praetorian",
        "title": "Dancer of Death and Dawn",
        "spell": "CONTINGENCY", "school": "Evocation",
        "symbol": "\u2635", "element": "Water",
        "color": "#ce93d8", "prey8": "YIELD",
    },
    {
        "port_id": "P6", "powerword": "ASSIMILATE", "commander": "Kraken Keeper",
        "title": "Devourer of Depths and Dreams",
        "spell": "CLONE", "school": "Necromancy",
        "symbol": "\u2636", "element": "Mountain",
        "color": "#90a4ae", "prey8": "PERCEIVE",
    },
    {
        "port_id": "P7", "powerword": "NAVIGATE", "commander": "Spider Sovereign",
        "title": "Summoner of Seals and Spheres",
        "spell": "TIME STOP", "school": "Transmutation",
        "symbol": "\u2637", "element": "Earth",
        "color": "#a1887f", "prey8": "REACT",
    },
]

PORT_BY_ID = {p["port_id"]: p for p in PORTS}

DEFAULT_CHAT_MODEL = os.environ.get("HFO_CHAT_MODEL", "gemma3:4b")

# ── SSOT Functions (sync, run in executor) ──────────────────

def _get_conn() -> sqlite3.Connection:
    return sqlite3.connect(str(DB_PATH), timeout=5)


def _read_stigmergy_sync(limit: int = 50, after_id: int = 0,
                          event_filter: str = "%") -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT id, event_type, timestamp, subject,
                      substr(data_json, 1, 2000)
               FROM stigmergy_events
               WHERE id > ? AND event_type LIKE ?
               ORDER BY id DESC LIMIT ?""",
            (after_id, event_filter, limit),
        ).fetchall()
        results = []
        for r in rows:
            try:
                data = json.loads(r[4]) if r[4] else {}
            except Exception:
                data = {}
            results.append({
                "id": r[0],
                "event_type": r[1],
                "timestamp": r[2],
                "subject": r[3] or "",
                "data": data,
            })
        return results
    finally:
        conn.close()


def _write_stigmergy_sync(event_type: str, data: dict,
                           subject: str = "web-chat") -> int:
    if not DB_PATH.exists():
        return -1
    ts = datetime.now(timezone.utc).isoformat()
    event = {
        "specversion": "1.0",
        "id": secrets.token_hex(16),
        "type": event_type,
        "source": f"hfo_daemon_chat_web_gen{GEN}",
        "subject": subject,
        "time": ts,
        "timestamp": ts,
        "datacontenttype": "application/json",
        "data": data,
    }
    c_hash = hashlib.sha256(
        json.dumps(event, sort_keys=True).encode()
    ).hexdigest()
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, timestamp, subject, source, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event["type"], ts, subject, event["source"],
             json.dumps(event), c_hash),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()


def _fts_search_sync(query: str, limit: int = 20) -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT id, title, substr(bluf, 1, 300), port, source, doc_type
               FROM documents
               WHERE id IN (
                   SELECT rowid FROM documents_fts
                   WHERE documents_fts MATCH ?
               ) LIMIT ?""",
            (query, limit),
        ).fetchall()
        return [
            {"id": r[0], "title": r[1], "bluf": r[2],
             "port": r[3], "source": r[4], "doc_type": r[5]}
            for r in rows
        ]
    finally:
        conn.close()


def _get_stats_sync() -> dict:
    if not DB_PATH.exists():
        return {"docs": 0, "events": 0}
    conn = _get_conn()
    try:
        docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        events = conn.execute(
            "SELECT COUNT(*) FROM stigmergy_events"
        ).fetchone()[0]
        return {"docs": docs, "events": events}
    finally:
        conn.close()


# ── Ollama Interface (async) ────────────────────────────────

async def ollama_generate(model: str, prompt: str, system: str = "",
                           timeout: float = 120) -> dict:
    url = f"{OLLAMA_BASE}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 1024, "temperature": 0.4},
    }
    if system:
        payload["system"] = system
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            return {
                "response": data.get("response", ""),
                "model": data.get("model", model),
                "eval_count": data.get("eval_count", 0),
                "duration_s": round(data.get("total_duration", 0) / 1e9, 1),
                "done": data.get("done", False),
            }
    except Exception as e:
        return {"response": f"[ERROR] {e}", "model": model,
                "eval_count": 0, "duration_s": 0, "done": False}


async def get_loaded_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_BASE}/api/ps")
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


async def get_all_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_BASE}/api/tags")
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


# ── Persona Builder ─────────────────────────────────────────

def build_persona(port: dict) -> str:
    return f"""# {port['port_id']} {port['powerword']} -- {port['commander']}
## {port['title']}

You are **{port['commander']}**, commander of {port['port_id']} ({port['powerword']}) in the HFO Octree.
Your trigram is {port['symbol']} ({port['element']}). Your signature spell is **{port['spell']}** ({port['school']}).
Your PREY8 gate: **{port['prey8']}**.

## Context
- Gen90 SSOT: ~9,861 documents, ~9M words, 10,600+ stigmergy events
- All content is BRONZE (trust nothing, validate everything)
- The operator (TTAO) is chatting with you through the Daemon Chat Web App
- Be concise, specific, and actionable. Cite document IDs when referencing SSOT content.
- Sign responses: [{port['port_id']}:{port['commander']}]

## Your Domain: {port['powerword']}
Provide expert advisory in your domain. Reference recent stigmergy events when relevant.
The operator values: signal over noise, adversarial coaching, and stigmergy-first coordination.
"""


# ── API Route Handlers ──────────────────────────────────────

async def handle_index(request: web.Request) -> web.Response:
    return web.Response(text=HTML_PAGE, content_type="text/html")


async def handle_ports(request: web.Request) -> web.Response:
    return web.json_response(PORTS)


async def handle_stigmergy(request: web.Request) -> web.Response:
    limit = int(request.query.get("limit", "50"))
    after_id = int(request.query.get("after_id", "0"))
    event_filter = request.query.get("filter", "%")
    loop = asyncio.get_event_loop()
    events = await loop.run_in_executor(
        None, partial(_read_stigmergy_sync, limit, after_id, event_filter)
    )
    return web.json_response(events)


async def handle_chat(request: web.Request) -> web.Response:
    body = await request.json()
    port_id = body.get("port_id", "P4")
    message = body.get("message", "").strip()
    model = body.get("model", DEFAULT_CHAT_MODEL)

    if not message:
        return web.json_response({"error": "Empty message"}, status=400)

    port = PORT_BY_ID.get(port_id)
    if not port:
        return web.json_response({"error": f"Unknown port: {port_id}"}, status=400)

    # Get recent stigmergy for context
    loop = asyncio.get_event_loop()
    recent = await loop.run_in_executor(
        None, partial(_read_stigmergy_sync, 5, 0, "%")
    )
    context_lines = []
    for evt in recent[:5]:
        ts = evt["timestamp"][:19] if evt.get("timestamp") else ""
        context_lines.append(f"[{ts}] {evt['event_type']}: {evt.get('subject', '')}")
    context_block = "\n".join(context_lines)

    prompt = f"""## Recent Stigmergy Events
{context_block}

## Operator Message
{message}"""

    system = build_persona(port)
    result = await ollama_generate(model, prompt, system)

    # Log to stigmergy
    await loop.run_in_executor(
        None,
        partial(
            _write_stigmergy_sync,
            "hfo.gen90.web.chat.exchange",
            {
                "port_id": port_id,
                "commander": port["commander"],
                "model": model,
                "user_message": message[:500],
                "response_preview": result["response"][:500],
                "eval_count": result["eval_count"],
                "duration_s": result["duration_s"],
            },
            f"web-chat:{port_id}",
        ),
    )

    return web.json_response(result)


async def handle_search(request: web.Request) -> web.Response:
    q = request.query.get("q", "").strip()
    if not q:
        return web.json_response([])
    limit = int(request.query.get("limit", "20"))
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        None, partial(_fts_search_sync, q, limit)
    )
    return web.json_response(results)


async def handle_stats(request: web.Request) -> web.Response:
    loop = asyncio.get_event_loop()
    stats = await loop.run_in_executor(None, _get_stats_sync)
    return web.json_response(stats)


async def handle_models(request: web.Request) -> web.Response:
    loaded = await get_loaded_models()
    available = await get_all_models()
    return web.json_response({"loaded": loaded, "available": available})


# ── Embedded HTML SPA ───────────────────────────────────────

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HFO Gen90 Daemon Chat</title>
<style>
:root {
  --bg: #0d1117;
  --bg2: #161b22;
  --bg3: #21262d;
  --border: #30363d;
  --text: #c9d1d9;
  --text-dim: #8b949e;
  --accent: #58a6ff;
  --red: #f44336;
  --green: #81c784;
  --yellow: #ffb74d;
  --purple: #ce93d8;
  --cyan: #4fc3f7;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  height: 100vh;
  overflow: hidden;
}
/* Layout */
.app {
  display: grid;
  grid-template-columns: 220px 1fr;
  grid-template-rows: 48px 1fr;
  height: 100vh;
}
/* Header */
.header {
  grid-column: 1 / -1;
  background: var(--bg2);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 16px;
}
.header h1 {
  font-size: 16px;
  font-weight: 600;
  color: var(--accent);
}
.header .stats {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-dim);
}
.header .stats span { margin-left: 12px; }
/* Sidebar */
.sidebar {
  background: var(--bg2);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  padding: 8px 0;
}
.port-btn {
  display: block;
  width: 100%;
  padding: 10px 14px;
  border: none;
  background: transparent;
  color: var(--text);
  text-align: left;
  cursor: pointer;
  font-size: 13px;
  line-height: 1.4;
  transition: background 0.15s;
}
.port-btn:hover { background: var(--bg3); }
.port-btn.active { background: var(--bg3); border-left: 3px solid var(--accent); }
.port-btn .port-id { font-weight: 700; font-size: 14px; }
.port-btn .commander { font-size: 11px; color: var(--text-dim); }
/* Search box in sidebar */
.sidebar-search {
  padding: 8px 12px;
  border-top: 1px solid var(--border);
}
.sidebar-search input {
  width: 100%;
  padding: 6px 10px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 13px;
  outline: none;
}
.sidebar-search input:focus { border-color: var(--accent); }
/* Main area */
.main {
  display: grid;
  grid-template-rows: auto 1fr auto;
  overflow: hidden;
}
/* Tabs */
.tabs {
  display: flex;
  gap: 0;
  background: var(--bg2);
  border-bottom: 1px solid var(--border);
}
.tab-btn {
  padding: 10px 20px;
  border: none;
  background: transparent;
  color: var(--text-dim);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
}
.tab-btn:hover { color: var(--text); }
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }
/* Panels */
.panel { display: none; overflow-y: auto; padding: 0; }
.panel.active { display: block; }
/* Stigmergy feed */
#stigmergy-panel {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  padding: 8px 12px;
}
.stig-event {
  padding: 4px 0;
  border-bottom: 1px solid var(--bg3);
  display: grid;
  grid-template-columns: 48px 68px 1fr auto;
  gap: 8px;
  align-items: baseline;
}
.stig-id { color: var(--text-dim); font-size: 11px; }
.stig-time { color: var(--text-dim); }
.stig-type { font-weight: 500; }
.stig-subject { color: var(--text-dim); font-size: 11px; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 300px;}
/* Chat panel */
#chat-panel { padding: 12px 16px; }
.chat-msg {
  margin-bottom: 16px;
  max-width: 85%;
}
.chat-msg.user {
  margin-left: auto;
  text-align: right;
}
.chat-msg .bubble {
  display: inline-block;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
  text-align: left;
  white-space: pre-wrap;
  word-break: break-word;
}
.chat-msg.user .bubble {
  background: #1a3a5c;
  color: var(--text);
  border-bottom-right-radius: 4px;
}
.chat-msg.daemon .bubble {
  background: var(--bg3);
  color: var(--text);
  border-bottom-left-radius: 4px;
}
.chat-msg .meta {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: 4px;
}
.typing-indicator {
  color: var(--text-dim);
  font-style: italic;
  font-size: 13px;
  padding: 8px 0;
  display: none;
}
.typing-indicator.show { display: block; }
/* Search results */
#search-panel { padding: 12px 16px; }
.search-result {
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 8px;
  background: var(--bg2);
}
.search-result .sr-title { font-weight: 600; color: var(--accent); font-size: 14px; }
.search-result .sr-meta { font-size: 11px; color: var(--text-dim); margin: 4px 0; }
.search-result .sr-bluf { font-size: 13px; color: var(--text); line-height: 1.4; }
/* Input bar */
.input-bar {
  background: var(--bg2);
  border-top: 1px solid var(--border);
  padding: 12px 16px;
  display: flex;
  gap: 8px;
  align-items: center;
}
.input-bar input {
  flex: 1;
  padding: 10px 14px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-size: 14px;
  outline: none;
}
.input-bar input:focus { border-color: var(--accent); }
.input-bar select {
  padding: 8px 10px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-size: 12px;
  outline: none;
  cursor: pointer;
}
.send-btn {
  padding: 10px 20px;
  background: var(--accent);
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  font-size: 14px;
  transition: opacity 0.15s;
}
.send-btn:hover { opacity: 0.85; }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
/* Event type colors */
.et-heartbeat { color: #4a6a7a; }
.et-resource { color: #8a7a3a; }
.et-perceive { color: var(--green); font-weight: 700; }
.et-react { color: var(--accent); font-weight: 700; }
.et-execute { color: var(--purple); font-weight: 700; }
.et-yield { color: var(--cyan); font-weight: 700; }
.et-tamper { color: var(--red); font-weight: 700; }
.et-gate { color: var(--red); }
.et-memory { color: var(--red); }
.et-chimera { color: var(--yellow); }
.et-daemon { color: var(--green); }
.et-swarm { color: var(--cyan); }
.et-chat { color: #ffffff; font-weight: 700; }
.et-watchdog { color: var(--red); }
.et-song { color: var(--purple); }
.et-kraken { color: var(--accent); }
.et-lineage { color: #7aa2f7; }
.et-web { color: #ffffff; }
.et-default { color: var(--text); }
/* Scrollbar */
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--bg3); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--border); }
/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-dim);
  text-align: center;
  padding: 40px;
}
.empty-state .icon { font-size: 48px; margin-bottom: 16px; opacity: 0.5; }
.empty-state p { font-size: 14px; }
</style>
</head>
<body>
<div class="app">
  <!-- Header -->
  <div class="header">
    <h1>&#9670; HFO Gen90 Daemon Chat</h1>
    <span id="active-port-label" style="font-size:13px;"></span>
    <div class="stats">
      <span id="stat-docs">--</span>
      <span id="stat-events">--</span>
      <span id="stat-model">--</span>
    </div>
  </div>

  <!-- Sidebar -->
  <div class="sidebar">
    <div id="port-list"></div>
    <div class="sidebar-search">
      <input type="text" id="search-input" placeholder="Search SSOT..." />
    </div>
  </div>

  <!-- Main -->
  <div class="main">
    <!-- Tabs -->
    <div class="tabs">
      <button class="tab-btn active" data-tab="chat">Chat</button>
      <button class="tab-btn" data-tab="stigmergy">Stigmergy</button>
      <button class="tab-btn" data-tab="search">Search</button>
    </div>

    <!-- Panels -->
    <div id="chat-panel" class="panel active">
      <div class="empty-state" id="chat-empty">
        <div class="icon">&#9670;</div>
        <p>Select a port commander and start chatting.<br>
        Your exchanges are logged as stigmergy events.</p>
      </div>
    </div>
    <div id="stigmergy-panel" class="panel"></div>
    <div id="search-panel" class="panel">
      <div class="empty-state">
        <div class="icon">&#128269;</div>
        <p>Type a query in the search box to search ~9,861 SSOT documents.</p>
      </div>
    </div>

    <!-- Typing indicator -->
    <div class="typing-indicator" id="typing">Daemon is thinking...</div>

    <!-- Input bar -->
    <div class="input-bar">
      <input type="text" id="msg-input" placeholder="Message the daemon..." autocomplete="off" />
      <select id="model-select"></select>
      <button class="send-btn" id="send-btn">Send</button>
    </div>
  </div>
</div>

<script>
// ── State ──────────────────────────────────────────────────
let activePort = null;
let activeTab = 'chat';
let chatHistory = {};  // per-port
let maxStigId = 0;
let pollTimer = null;
let sending = false;

// ── API helpers ────────────────────────────────────────────
async function api(path, opts) {
  const r = await fetch(path, opts);
  return r.json();
}

// ── Init ───────────────────────────────────────────────────
async function init() {
  // Load ports
  const ports = await api('/api/ports');
  const list = document.getElementById('port-list');
  ports.forEach(p => {
    const btn = document.createElement('button');
    btn.className = 'port-btn';
    btn.dataset.port = p.port_id;
    btn.innerHTML = `<div class="port-id" style="color:${p.color}">${p.symbol} ${p.port_id} ${p.powerword}</div><div class="commander">${p.commander} &middot; ${p.spell}</div>`;
    btn.onclick = () => selectPort(p.port_id);
    list.appendChild(btn);
  });

  // Load models
  const models = await api('/api/models');
  const sel = document.getElementById('model-select');
  const allModels = [...new Set([...models.loaded, ...models.available])];
  allModels.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m;
    opt.textContent = m + (models.loaded.includes(m) ? ' *' : '');
    sel.appendChild(opt);
  });

  // Stats
  refreshStats();
  setInterval(refreshStats, 30000);

  // Stigmergy polling
  pollStigmergy();
  pollTimer = setInterval(pollStigmergy, 3000);

  // Select P4 by default
  selectPort('P4');

  // Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.onclick = () => switchTab(btn.dataset.tab);
  });

  // Send
  document.getElementById('send-btn').onclick = sendMessage;
  document.getElementById('msg-input').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });

  // Search
  let searchTimeout;
  document.getElementById('search-input').addEventListener('input', e => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => doSearch(e.target.value), 400);
  });
}

// ── Port selection ─────────────────────────────────────────
function selectPort(portId) {
  activePort = portId;
  document.querySelectorAll('.port-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.port === portId);
  });
  const label = document.getElementById('active-port-label');
  label.textContent = portId;
  label.style.color = getPortColor(portId);

  // Show chat history for this port
  renderChat();
  switchTab('chat');
}

function getPortColor(portId) {
  const colors = {P0:'#4fc3f7',P1:'#81c784',P2:'#ffb74d',P3:'#e57373',P4:'#f44336',P5:'#ce93d8',P6:'#90a4ae',P7:'#a1887f'};
  return colors[portId] || '#58a6ff';
}

// ── Tabs ───────────────────────────────────────────────────
function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById(tab + '-panel').classList.add('active');
}

// ── Stats ──────────────────────────────────────────────────
async function refreshStats() {
  try {
    const s = await api('/api/stats');
    document.getElementById('stat-docs').textContent = s.docs.toLocaleString() + ' docs';
    document.getElementById('stat-events').textContent = s.events.toLocaleString() + ' events';
  } catch(e) {}
  const model = document.getElementById('model-select').value;
  document.getElementById('stat-model').textContent = model || '--';
}

// ── Stigmergy ──────────────────────────────────────────────
function getEventClass(type) {
  const map = [
    ['heartbeat','et-heartbeat'],['resource','et-resource'],
    ['perceive','et-perceive'],['react','et-react'],
    ['execute','et-execute'],['yield','et-yield'],
    ['tamper','et-tamper'],['gate_blocked','et-gate'],
    ['memory_loss','et-memory'],['chimera','et-chimera'],
    ['daemon','et-daemon'],['swarm','et-swarm'],
    ['chat','et-chat'],['watchdog','et-watchdog'],
    ['song','et-song'],['kraken','et-kraken'],
    ['lineage','et-lineage'],['web','et-web']
  ];
  for (const [k,v] of map) { if (type.includes(k)) return v; }
  return 'et-default';
}

async function pollStigmergy() {
  try {
    const events = await api('/api/stigmergy?limit=80&after_id=0');
    const panel = document.getElementById('stigmergy-panel');
    if (!events.length) {
      panel.innerHTML = '<div class="empty-state"><div class="icon">&#128225;</div><p>No stigmergy events yet.</p></div>';
      return;
    }
    // track max id
    if (events.length) maxStigId = Math.max(...events.map(e => e.id));

    panel.innerHTML = events.map(evt => {
      const ts = (evt.timestamp || '').substring(11, 19);
      const shortType = (evt.event_type || '').replace('hfo.gen90.', '').replace('hfo.gen90.', '');
      const cls = getEventClass(evt.event_type || '');
      const subj = evt.subject || '';
      return `<div class="stig-event">
        <span class="stig-id">#${evt.id}</span>
        <span class="stig-time">${ts}</span>
        <span class="stig-type ${cls}">${shortType}</span>
        <span class="stig-subject" title="${subj}">${subj}</span>
      </div>`;
    }).join('');
  } catch(e) {
    console.error('Stigmergy poll error:', e);
  }
}

// ── Chat ───────────────────────────────────────────────────
function renderChat() {
  const panel = document.getElementById('chat-panel');
  const empty = document.getElementById('chat-empty');
  const history = chatHistory[activePort] || [];

  if (!history.length) {
    panel.innerHTML = '';
    panel.appendChild(empty);
    empty.style.display = 'flex';
    return;
  }

  if (empty) empty.style.display = 'none';
  panel.innerHTML = history.map(msg => {
    const cls = msg.role === 'user' ? 'user' : 'daemon';
    const meta = msg.role === 'daemon'
      ? `<div class="meta">${msg.model || ''} &middot; ${msg.tokens || 0} tok &middot; ${msg.duration || 0}s</div>`
      : `<div class="meta">${new Date(msg.ts).toLocaleTimeString()}</div>`;
    return `<div class="chat-msg ${cls}"><div class="bubble">${escapeHtml(msg.text)}</div>${meta}</div>`;
  }).join('');

  panel.scrollTop = panel.scrollHeight;
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

async function sendMessage() {
  if (sending) return;
  const input = document.getElementById('msg-input');
  const text = input.value.trim();
  if (!text || !activePort) return;

  const model = document.getElementById('model-select').value;
  sending = true;
  document.getElementById('send-btn').disabled = true;
  document.getElementById('typing').classList.add('show');

  // Add user message
  if (!chatHistory[activePort]) chatHistory[activePort] = [];
  chatHistory[activePort].push({ role: 'user', text, ts: new Date().toISOString() });
  input.value = '';
  renderChat();

  try {
    const result = await api('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ port_id: activePort, message: text, model })
    });

    chatHistory[activePort].push({
      role: 'daemon',
      text: result.response || '[no response]',
      model: result.model,
      tokens: result.eval_count,
      duration: result.duration_s,
      ts: new Date().toISOString()
    });
  } catch(e) {
    chatHistory[activePort].push({
      role: 'daemon',
      text: '[ERROR] ' + e.message,
      ts: new Date().toISOString()
    });
  }

  sending = false;
  document.getElementById('send-btn').disabled = false;
  document.getElementById('typing').classList.remove('show');
  renderChat();
  refreshStats();
}

// ── Search ─────────────────────────────────────────────────
async function doSearch(query) {
  if (!query || query.length < 2) return;
  switchTab('search');
  const panel = document.getElementById('search-panel');
  panel.innerHTML = '<div style="padding:20px;color:var(--text-dim)">Searching...</div>';

  try {
    const results = await api('/api/search?q=' + encodeURIComponent(query));
    if (!results.length) {
      panel.innerHTML = '<div class="empty-state"><p>No results for "' + escapeHtml(query) + '"</p></div>';
      return;
    }
    panel.innerHTML = results.map(r => `
      <div class="search-result">
        <div class="sr-title">[${r.id}] ${escapeHtml(r.title || 'Untitled')}</div>
        <div class="sr-meta">${r.port || '--'} &middot; ${r.source || '--'} &middot; ${r.doc_type || '--'}</div>
        <div class="sr-bluf">${escapeHtml(r.bluf || '')}</div>
      </div>
    `).join('');
  } catch(e) {
    panel.innerHTML = '<div class="empty-state"><p>Search error: ' + e.message + '</p></div>';
  }
}

// ── Boot ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>
"""


# ── App Factory ─────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/ports", handle_ports)
    app.router.add_get("/api/stigmergy", handle_stigmergy)
    app.router.add_post("/api/chat", handle_chat)
    app.router.add_get("/api/search", handle_search)
    app.router.add_get("/api/stats", handle_stats)
    app.router.add_get("/api/models", handle_models)
    return app


def main():
    global DEFAULT_CHAT_MODEL
    parser = argparse.ArgumentParser(description="HFO Gen90 Daemon Chat Web App")
    parser.add_argument("--port", type=int, default=8089, help="HTTP port (default: 8089)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--model", default=DEFAULT_CHAT_MODEL, help=f"Default model (default: {DEFAULT_CHAT_MODEL})")
    parser.add_argument("--no-open", action="store_true", help="Don't auto-open browser")
    args = parser.parse_args()

    DEFAULT_CHAT_MODEL = args.model

    app = create_app()

    # Log session start
    _write_stigmergy_sync(
        "hfo.gen90.web.session.start",
        {"host": args.host, "port": args.port, "model": args.model},
        "web-session-start",
    )

    url = f"http://{args.host}:{args.port}"
    print(f"\n  HFO Gen90 Daemon Chat Web")
    print(f"  =========================")
    print(f"  URL:   {url}")
    print(f"  Model: {args.model}")
    print(f"  SSOT:  {DB_PATH}")
    print(f"  Press Ctrl+C to stop\n")

    if not args.no_open:
        webbrowser.open(url)

    web.run_app(app, host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()
