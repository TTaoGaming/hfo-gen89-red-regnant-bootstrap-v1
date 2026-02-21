#!/usr/bin/env python3
"""
hfo_daemon_chat_tui.py — HFO Gen90 Daemon Chat TUI (Option B)
===============================================================
Textual-powered terminal interface for live stigmergy monitoring
and interactive chat with any of the 8 Octree port commanders.

Architecture:
  Left sidebar  — Port selector (8 commanders + ALL channel)
  Center top    — Live stigmergy event tail (auto-polls every 5s)
  Center bottom — Chat panel (per-port conversation with Ollama)
  Footer        — Status bar (RAM, VRAM, active port, model)

Every chat exchange is written as a stigmergy CloudEvent so future
agents (including a Copilot-controlling daemon) get full context.

Usage:
    python hfo_daemon_chat_tui.py
    python hfo_daemon_chat_tui.py --model gemma3:4b
    python hfo_daemon_chat_tui.py --port P4

Key bindings:
    F1-F8       — Switch to port P0-P7
    F9          — Switch to ALL (broadcast view)
    Ctrl+Q      — Quit
    Ctrl+L      — Clear chat
    Ctrl+F      — FTS search SSOT
    Enter       — Send message

Medallion: bronze
Port: P1 BRIDGE (shared data fabric) + P7 NAVIGATE (C2 interface)
Schema: hfo.gen90.tui.daemon_chat.v1
Pointer key: tui.daemon_chat
"""

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

# ── Textual imports ───────────────────────────────────────────
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Static,
)

# ── Path resolution ───────────────────────────────────────────

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

# ── Port Registry (self-contained, no import of octree_daemon) ─

PORTS = [
    {
        "port_id": "P0", "powerword": "OBSERVE", "commander": "Lidless Legion",
        "title": "Watcher of Whispers and Wrath",
        "spell": "TRUE SEEING", "school": "Divination",
        "symbol": "☰", "element": "Heaven",
        "color": "#4fc3f7", "prey8": "PERCEIVE",
    },
    {
        "port_id": "P1", "powerword": "BRIDGE", "commander": "Web Weaver",
        "title": "Binder of Blood and Breath",
        "spell": "FORBIDDANCE", "school": "Abjuration",
        "symbol": "☱", "element": "Lake",
        "color": "#81c784", "prey8": "REACT",
    },
    {
        "port_id": "P2", "powerword": "SHAPE", "commander": "Mirror Magus",
        "title": "Maker of Myths and Meaning",
        "spell": "GENESIS", "school": "Conjuration",
        "symbol": "☲", "element": "Fire",
        "color": "#ffb74d", "prey8": "EXECUTE",
    },
    {
        "port_id": "P3", "powerword": "INJECT", "commander": "Harmonic Hydra",
        "title": "Harbinger of Harmony and Havoc",
        "spell": "GATE", "school": "Conjuration",
        "symbol": "☳", "element": "Thunder",
        "color": "#e57373", "prey8": "YIELD",
    },
    {
        "port_id": "P4", "powerword": "DISRUPT", "commander": "Red Regnant",
        "title": "Singer of Strife and Splendor",
        "spell": "WEIRD", "school": "Illusion",
        "color": "#f44336", "prey8": "EXECUTE",
        "symbol": "☴", "element": "Wind",
    },
    {
        "port_id": "P5", "powerword": "IMMUNIZE", "commander": "Pyre Praetorian",
        "title": "Dancer of Death and Dawn",
        "spell": "CONTINGENCY", "school": "Evocation",
        "symbol": "☵", "element": "Water",
        "color": "#ce93d8", "prey8": "YIELD",
    },
    {
        "port_id": "P6", "powerword": "ASSIMILATE", "commander": "Kraken Keeper",
        "title": "Devourer of Depths and Dreams",
        "spell": "CLONE", "school": "Necromancy",
        "symbol": "☶", "element": "Mountain",
        "color": "#90a4ae", "prey8": "PERCEIVE",
    },
    {
        "port_id": "P7", "powerword": "NAVIGATE", "commander": "Spider Sovereign",
        "title": "Summoner of Seals and Spheres",
        "spell": "TIME STOP", "school": "Transmutation",
        "symbol": "☷", "element": "Earth",
        "color": "#a1887f", "prey8": "REACT",
    },
]

PORT_BY_ID = {p["port_id"]: p for p in PORTS}

# Default model — lightweight for interactive chat
DEFAULT_CHAT_MODEL = os.environ.get("HFO_CHAT_MODEL", "gemma3:4b")

# ── SSOT Functions ────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    return sqlite3.connect(str(DB_PATH), timeout=5)


def read_stigmergy(limit: int = 50, after_id: int = 0,
                    event_filter: str = "%") -> list[dict]:
    """Read stigmergy events, optionally after a given ID."""
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
                "subject": r[3],
                "data": data,
            })
        return results
    finally:
        conn.close()


def write_stigmergy(event_type: str, data: dict,
                     subject: str = "tui-chat") -> int:
    """Write a chat event to SSOT."""
    if not DB_PATH.exists():
        return -1
    ts = datetime.now(timezone.utc).isoformat()
    event = {
        "specversion": "1.0",
        "id": secrets.token_hex(16),
        "type": event_type,
        "source": f"hfo_daemon_chat_tui_gen{GEN}",
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


def fts_search(query: str, limit: int = 5) -> list[dict]:
    """FTS5 search across SSOT documents."""
    if not DB_PATH.exists():
        return []
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT id, title, substr(bluf, 1, 200), port, source
               FROM documents
               WHERE id IN (
                   SELECT rowid FROM documents_fts
                   WHERE documents_fts MATCH ?
               ) LIMIT ?""",
            (query, limit),
        ).fetchall()
        return [
            {"id": r[0], "title": r[1], "bluf": r[2],
             "port": r[3], "source": r[4]}
            for r in rows
        ]
    finally:
        conn.close()


def get_ssot_stats() -> dict:
    """Quick SSOT stats for the status bar."""
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


# ── Ollama Interface ──────────────────────────────────────────

def ollama_generate(model: str, prompt: str, system: str = "",
                     timeout: float = 120) -> dict:
    """Call Ollama generate API (blocking)."""
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
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=payload)
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


def get_loaded_models() -> list[str]:
    """Get currently loaded Ollama models."""
    try:
        with httpx.Client(timeout=5) as client:
            r = client.get(f"{OLLAMA_BASE}/api/ps")
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


# ── Persona Builder ───────────────────────────────────────────

def build_persona(port: dict) -> str:
    """Build a system prompt for the selected port commander."""
    return f"""# {port['port_id']} {port['powerword']} — {port['commander']}
## {port['title']}

You are **{port['commander']}**, commander of {port['port_id']} ({port['powerword']}) in the HFO Octree.
Your trigram is {port['symbol']} ({port['element']}). Your signature spell is **{port['spell']}** ({port['school']}).
Your PREY8 gate: **{port['prey8']}**.

## Context
- Gen90 SSOT: ~9,861 documents, ~9M words, 10,600+ stigmergy events
- All content is BRONZE (trust nothing, validate everything)
- The operator (TTAO) is chatting with you through the Daemon Chat TUI
- Be concise, specific, and actionable. Cite document IDs when referencing SSOT content.
- Sign responses: [{port['port_id']}:{port['commander']}]

## Your Domain: {port['powerword']}
Provide expert advisory in your domain. Reference recent stigmergy events when relevant.
The operator values: signal over noise, adversarial coaching, and stigmergy-first coordination.
"""


# ── Event Colorizer ──────────────────────────────────────────

EVENT_COLORS = {
    "heartbeat": "dim cyan",
    "resource": "dim yellow",
    "prey8.perceive": "bold green",
    "prey8.react": "bold blue",
    "prey8.execute": "bold magenta",
    "prey8.yield": "bold cyan",
    "prey8.tamper": "bold red",
    "prey8.gate_blocked": "bold red",
    "prey8.memory_loss": "bold red on dark_red",
    "chimera": "bold yellow",
    "daemon": "green",
    "swarm": "cyan",
    "tui.chat": "bold white",
    "watchdog": "bold red",
    "song": "bold magenta",
    "kraken": "blue",
}


def colorize_event(event_type: str) -> str:
    """Return a rich markup color tag for an event type."""
    for key, color in EVENT_COLORS.items():
        if key in event_type:
            return color
    return "white"


def format_event_line(evt: dict) -> str:
    """Format a stigmergy event for the log display."""
    ts = evt.get("timestamp", "")
    if len(ts) > 19:
        ts = ts[11:19]  # HH:MM:SS
    etype = evt.get("event_type", "unknown")
    # Shorten common prefixes
    short = etype.replace("hfo.gen90.", "").replace("hfo.gen90.", "")
    subject = evt.get("subject", "")
    color = colorize_event(etype)
    eid = evt.get("id", "?")
    return f"[dim]#{eid}[/] [{color}]{ts} {short}[/] [dim]{subject}[/]"


# ── Textual TUI ──────────────────────────────────────────────

class PortSidebar(ListView):
    """Sidebar listing all 8 port commanders."""

    def compose(self) -> ComposeResult:
        for p in PORTS:
            yield ListItem(
                Label(
                    f"[bold {p['color']}]{p['symbol']} {p['port_id']}[/]\n"
                    f"  {p['powerword']}\n"
                    f"  [dim]{p['commander']}[/]",
                    markup=True,
                ),
                id=f"port-{p['port_id']}",
            )
        yield ListItem(
            Label(
                "[bold white]⊕ ALL[/]\n"
                "  BROADCAST\n"
                "  [dim]All Ports[/]",
                markup=True,
            ),
            id="port-ALL",
        )


class StigmergyLog(RichLog):
    """Live-updating stigmergy event viewer."""
    pass


class ChatLog(RichLog):
    """Chat conversation display."""
    pass


class DaemonChatApp(App):
    """HFO Gen90 Daemon Chat TUI — Option B from DSE AoA."""

    TITLE = "HFO Gen90 Daemon Chat"
    SUB_TITLE = "Stigmergy + Ollama"

    CSS = """
    Screen {
        layout: horizontal;
    }
    #sidebar {
        width: 22;
        dock: left;
        border-right: solid $primary;
        height: 100%;
    }
    #main {
        width: 1fr;
    }
    #stigmergy-panel {
        height: 40%;
        border-bottom: solid $primary;
    }
    #stigmergy-log {
        height: 1fr;
    }
    #chat-panel {
        height: 60%;
    }
    #chat-log {
        height: 1fr;
    }
    #chat-input {
        dock: bottom;
        margin: 0 1;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    #stigmergy-header {
        height: 1;
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }
    #chat-header {
        height: 1;
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }
    PortSidebar {
        height: 100%;
    }
    PortSidebar > ListItem {
        padding: 0 1;
        height: 3;
    }
    PortSidebar > ListItem.-highlight {
        background: $surface-lighten-1;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear_chat", "Clear Chat", show=True),
        Binding("ctrl+f", "fts_search", "FTS Search", show=True),
        Binding("f1", "port_p0", "P0", show=False),
        Binding("f2", "port_p1", "P1", show=False),
        Binding("f3", "port_p2", "P2", show=False),
        Binding("f4", "port_p3", "P3", show=False),
        Binding("f5", "port_p4", "P4", show=False),
        Binding("f6", "port_p5", "P5", show=False),
        Binding("f7", "port_p6", "P6", show=False),
        Binding("f8", "port_p7", "P7", show=False),
        Binding("f9", "port_all", "ALL", show=False),
    ]

    active_port: reactive[str] = reactive("P4")
    last_event_id: reactive[int] = reactive(0)
    chat_model: reactive[str] = reactive(DEFAULT_CHAT_MODEL)

    def __init__(self, initial_port: str = "P4",
                 model: str = DEFAULT_CHAT_MODEL):
        super().__init__()
        self.active_port = initial_port
        self.chat_model = model
        self._poll_timer: Optional[Timer] = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                yield PortSidebar(id="port-list")
            with Vertical(id="main"):
                with Vertical(id="stigmergy-panel"):
                    yield Static(
                        "⚡ Stigmergy Live Feed",
                        id="stigmergy-header",
                    )
                    yield StigmergyLog(
                        id="stigmergy-log",
                        highlight=True,
                        markup=True,
                        wrap=True,
                        max_lines=500,
                    )
                with Vertical(id="chat-panel"):
                    yield Static(
                        self._chat_header_text(),
                        id="chat-header",
                    )
                    yield ChatLog(
                        id="chat-log",
                        highlight=True,
                        markup=True,
                        wrap=True,
                        max_lines=1000,
                    )
                    yield Input(
                        placeholder="Chat with daemon... (Enter to send, /help for commands)",
                        id="chat-input",
                    )
        yield Static("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize: load recent events, start polling."""
        # Load initial stigmergy
        self._load_initial_stigmergy()
        # Start polling every 5 seconds
        self._poll_timer = self.set_interval(5, self._poll_stigmergy)
        # Update status bar
        self._update_status()
        # Welcome message
        chat_log = self.query_one("#chat-log", ChatLog)
        port = PORT_BY_ID.get(self.active_port, PORTS[4])
        chat_log.write(
            f"[bold {port['color']}]"
            f"{port['symbol']} Connected to {port['commander']} "
            f"({port['port_id']} {port['powerword']})[/]\n"
            f"[dim]Model: {self.chat_model} | "
            f"Spell: {port['spell']} ({port['school']})[/]\n"
            f"[dim]Type a message or /help for commands[/]\n"
        )
        # Log TUI start as stigmergy event
        write_stigmergy(
            f"hfo.gen{GEN}.tui.session.start",
            {
                "port": self.active_port,
                "model": self.chat_model,
                "operator": "TTAO",
            },
            subject="tui-session",
        )

    def _chat_header_text(self) -> str:
        port = PORT_BY_ID.get(self.active_port)
        if port:
            return (
                f"💬 Chat: {port['symbol']} {port['port_id']} "
                f"{port['powerword']} — {port['commander']} "
                f"[{self.chat_model}]"
            )
        return f"💬 Chat: ALL PORTS [{self.chat_model}]"

    def _load_initial_stigmergy(self) -> None:
        """Load the last 50 stigmergy events."""
        slog = self.query_one("#stigmergy-log", StigmergyLog)
        events = read_stigmergy(limit=50)
        if events:
            self.last_event_id = events[0]["id"]
            for evt in reversed(events):
                slog.write(format_event_line(evt))

    def _poll_stigmergy(self) -> None:
        """Poll for new stigmergy events."""
        events = read_stigmergy(limit=20, after_id=self.last_event_id)
        if not events:
            return
        slog = self.query_one("#stigmergy-log", StigmergyLog)
        self.last_event_id = events[0]["id"]
        for evt in reversed(events):
            slog.write(format_event_line(evt))
        self._update_status()

    def _update_status(self) -> None:
        """Update the status bar."""
        stats = get_ssot_stats()
        models = get_loaded_models()
        model_str = ", ".join(models) if models else "none"
        port = PORT_BY_ID.get(self.active_port)
        port_str = (
            f"{port['port_id']} {port['powerword']}"
            if port else "ALL"
        )
        bar = self.query_one("#status-bar", Static)
        bar.update(
            f" 📊 Docs: {stats['docs']} | Events: {stats['events']} | "
            f"🎯 Port: {port_str} | "
            f"🤖 Loaded: {model_str} | "
            f"💬 Model: {self.chat_model}"
        )

    # ── Port switching ────────────────────────────────────────

    def _switch_port(self, port_id: str) -> None:
        """Switch active port and update UI."""
        self.active_port = port_id
        header = self.query_one("#chat-header", Static)
        header.update(self._chat_header_text())
        chat_log = self.query_one("#chat-log", ChatLog)
        port = PORT_BY_ID.get(port_id)
        if port:
            chat_log.write(
                f"\n[bold {port['color']}]"
                f"━━━ Switched to {port['symbol']} {port['port_id']} "
                f"{port['powerword']} — {port['commander']} ━━━[/]\n"
            )
        else:
            chat_log.write(
                "\n[bold white]━━━ Switched to ALL PORTS (broadcast) ━━━[/]\n"
            )
        self._update_status()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle port selection from sidebar."""
        item_id = event.item.id or ""
        port_id = item_id.replace("port-", "")
        self._switch_port(port_id)

    # F-key actions
    def action_port_p0(self) -> None: self._switch_port("P0")
    def action_port_p1(self) -> None: self._switch_port("P1")
    def action_port_p2(self) -> None: self._switch_port("P2")
    def action_port_p3(self) -> None: self._switch_port("P3")
    def action_port_p4(self) -> None: self._switch_port("P4")
    def action_port_p5(self) -> None: self._switch_port("P5")
    def action_port_p6(self) -> None: self._switch_port("P6")
    def action_port_p7(self) -> None: self._switch_port("P7")
    def action_port_all(self) -> None: self._switch_port("ALL")

    def action_clear_chat(self) -> None:
        """Clear the chat log."""
        self.query_one("#chat-log", ChatLog).clear()

    def action_fts_search(self) -> None:
        """Prompt for FTS search (reuse chat input with /search prefix)."""
        inp = self.query_one("#chat-input", Input)
        inp.value = "/search "
        inp.focus()

    # ── Chat handling ─────────────────────────────────────────

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle chat input submission."""
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""

        chat_log = self.query_one("#chat-log", ChatLog)

        # Handle commands
        if text.startswith("/"):
            await self._handle_command(text, chat_log)
            return

        # Regular chat message
        port = PORT_BY_ID.get(self.active_port)
        if not port:
            # Broadcast mode — send to P7 Navigator as coordinator
            port = PORT_BY_ID["P7"]

        chat_log.write(f"\n[bold white]TTAO:[/] {text}")
        chat_log.write("[dim]Thinking...[/]")

        # Send to Ollama in background worker
        self._send_to_daemon(text, port)

    @work(thread=True)
    def _send_to_daemon(self, message: str, port: dict) -> None:
        """Send message to daemon via Ollama (background thread)."""
        # Build context from recent stigmergy
        recent = read_stigmergy(limit=10)
        context_lines = []
        for evt in recent[:5]:
            short = evt["event_type"].replace("hfo.gen90.", "")
            context_lines.append(f"  [{short}] {evt.get('subject', '')}")
        context = "\n".join(context_lines) if context_lines else "(quiet)"

        # Build prompt with context
        prompt = f"""Recent stigmergy (latest 5 events):
{context}

Operator message: {message}

Respond as {port['commander']} ({port['port_id']} {port['powerword']}).
Be concise and actionable. Reference specific document IDs or event types when relevant.
Sign your response: [{port['port_id']}:{port['commander']}]"""

        system = build_persona(port)
        result = ollama_generate(self.chat_model, prompt, system=system)

        response = result.get("response", "[no response]")
        duration = result.get("duration_s", 0)
        tokens = result.get("eval_count", 0)

        # Update chat log on main thread
        chat_log = self.query_one("#chat-log", ChatLog)
        chat_log.write(
            f"\n[bold {port['color']}]{port['symbol']} "
            f"{port['commander']}:[/] {response}"
        )
        chat_log.write(
            f"[dim]({tokens} tokens, {duration}s, {self.chat_model})[/]"
        )

        # Write exchange to stigmergy
        write_stigmergy(
            f"hfo.gen{GEN}.tui.chat.exchange",
            {
                "port": port["port_id"],
                "commander": port["commander"],
                "model": self.chat_model,
                "operator_message": message,
                "daemon_response": response[:2000],
                "tokens": tokens,
                "duration_s": duration,
                "operator": "TTAO",
            },
            subject=f"tui-chat-{port['port_id']}",
        )

    async def _handle_command(self, text: str, chat_log: ChatLog) -> None:
        """Handle /commands."""
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "/help":
            chat_log.write(
                "\n[bold cyan]Commands:[/]\n"
                "  [bold]/search <query>[/]  — FTS5 search SSOT documents\n"
                "  [bold]/model <name>[/]    — Switch Ollama model\n"
                "  [bold]/models[/]          — List loaded models\n"
                "  [bold]/stats[/]           — Show SSOT statistics\n"
                "  [bold]/events[/]          — Show last 10 stigmergy events\n"
                "  [bold]/port <P0-P7>[/]    — Switch active port\n"
                "  [bold]/clear[/]           — Clear chat\n"
                "  [bold]/help[/]            — This message\n"
                "  [dim]F1-F8 = switch ports | F9 = ALL | Ctrl+Q = quit[/]"
            )
        elif cmd == "/search":
            if not arg:
                chat_log.write("[yellow]Usage: /search <query>[/]")
                return
            chat_log.write(f"[dim]Searching: {arg}[/]")
            results = fts_search(arg, limit=8)
            if results:
                for r in results:
                    port_tag = f"[{r['port']}]" if r["port"] else ""
                    chat_log.write(
                        f"  [bold]#{r['id']}[/] {port_tag} "
                        f"[cyan]{r['title'] or '(untitled)'}[/]\n"
                        f"    [dim]{r['bluf'][:120]}[/]"
                    )
            else:
                chat_log.write("[yellow]No results found.[/]")
        elif cmd == "/model":
            if not arg:
                chat_log.write(
                    f"[yellow]Current model: {self.chat_model}. "
                    f"Usage: /model <name>[/]"
                )
                return
            self.chat_model = arg.strip()
            self.query_one("#chat-header", Static).update(
                self._chat_header_text()
            )
            chat_log.write(f"[green]Model switched to: {self.chat_model}[/]")
            self._update_status()
        elif cmd == "/models":
            models = get_loaded_models()
            if models:
                chat_log.write(
                    "[bold]Loaded models:[/]\n" +
                    "\n".join(f"  • {m}" for m in models)
                )
            else:
                chat_log.write("[yellow]No models loaded (or Ollama offline)[/]")
        elif cmd == "/stats":
            stats = get_ssot_stats()
            chat_log.write(
                f"[bold]SSOT Stats:[/]\n"
                f"  Documents: {stats['docs']}\n"
                f"  Events:    {stats['events']}"
            )
        elif cmd == "/events":
            events = read_stigmergy(limit=10)
            chat_log.write("[bold]Last 10 stigmergy events:[/]")
            for evt in events:
                chat_log.write(f"  {format_event_line(evt)}")
        elif cmd == "/port":
            if arg.upper() in PORT_BY_ID or arg.upper() == "ALL":
                self._switch_port(arg.upper())
            else:
                chat_log.write(
                    f"[yellow]Unknown port: {arg}. "
                    f"Use P0-P7 or ALL.[/]"
                )
        elif cmd == "/clear":
            chat_log.clear()
        else:
            chat_log.write(
                f"[yellow]Unknown command: {cmd}. Type /help[/]"
            )

    # ── Cleanup ───────────────────────────────────────────────

    def on_unmount(self) -> None:
        """Log session end to stigmergy."""
        write_stigmergy(
            f"hfo.gen{GEN}.tui.session.end",
            {
                "port": self.active_port,
                "model": self.chat_model,
                "operator": "TTAO",
            },
            subject="tui-session",
        )


# ── CLI Entry Point ───────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="HFO Gen90 Daemon Chat TUI",
    )
    parser.add_argument(
        "--port", "-p", default="P4",
        help="Initial port (P0-P7, default: P4 Red Regnant)",
    )
    parser.add_argument(
        "--model", "-m", default=DEFAULT_CHAT_MODEL,
        help=f"Ollama model for chat (default: {DEFAULT_CHAT_MODEL})",
    )
    args = parser.parse_args()

    port = args.port.upper()
    if port not in PORT_BY_ID and port != "ALL":
        print(f"Unknown port: {port}. Use P0-P7 or ALL.")
        sys.exit(1)

    app = DaemonChatApp(initial_port=port, model=args.model)
    app.run()


if __name__ == "__main__":
    main()
