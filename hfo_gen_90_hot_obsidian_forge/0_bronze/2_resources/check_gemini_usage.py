#!/usr/bin/env python3
"""
Check Gemini API usage from SQLite stigmergy.
"""

import sqlite3
import json
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))
SSOT_DB = HFO_ROOT / os.getenv(
    "HFO_SSOT_DB",
    "hfo_gen_90_hot_obsidian_forge/2_gold/resources/hfo_gen90_ssot.sqlite"
)

def check_usage():
    if not SSOT_DB.exists():
        print(f"Database not found at {SSOT_DB}")
        return

    conn = sqlite3.connect(str(SSOT_DB))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get events from the last 24 hours
    now = datetime.now(timezone.utc)
    yesterday = (now - timedelta(days=1)).isoformat()

    cursor.execute("""
        SELECT event_type, subject, data_json, timestamp
        FROM stigmergy_events
        WHERE event_type LIKE 'hfo.gemini.usage.%'
          AND timestamp >= ?
        ORDER BY timestamp DESC
    """, (yesterday,))

    events = cursor.fetchall()
    
    usage_by_model = {}
    for row in events:
        try:
            event = json.loads(row['data_json'])
            data = event.get('data', {})
            model = data.get('model', 'unknown')
            usage_by_model[model] = usage_by_model.get(model, 0) + 1
        except Exception:
            pass

    print("=== Gemini API Usage (Last 24 Hours) ===")
    if not usage_by_model:
        print("No Gemini API usage recorded in the last 24 hours.")
    else:
        for model, count in usage_by_model.items():
            print(f"Model: {model:<30} | Calls: {count}")
            
            # Show limits for common models
            if "flash" in model and "lite" not in model:
                print(f"  -> Free Tier Limit: 1500 RPD | Remaining: {max(0, 1500 - count)}")
            elif "pro" in model:
                print(f"  -> Free Tier Limit: 50 RPD   | Remaining: {max(0, 50 - count)}")
            elif "lite" in model:
                print(f"  -> Free Tier Limit: 1500 RPD | Remaining: {max(0, 1500 - count)}")

    print("\nNote: Usage is now persistently tracked in SQLite stigmergy.")
    conn.close()

if __name__ == "__main__":
    check_usage()
