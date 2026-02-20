#!/usr/bin/env python3
"""
hfo_stigmergy_weekly_report.py — HFO Gen89 Weekly Stigmergy Rollup
==================================================================

Generates a concise weekly report of stigmergy events using progressive
summarization (chunking events -> daily summaries -> weekly summary).
Does not delete any underlying stigmergy signal.

Medallion: bronze
Port: P6 ASSIMILATE
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Path resolution ────────────────────────────────────────────
def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))
SSOT_DB = HFO_ROOT / os.getenv(
    "HFO_SSOT_DB",
    "hfo_gen_89_hot_obsidian_forge/2_gold/resources/hfo_gen89_ssot.sqlite"
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hfo_gemini_models import create_gemini_client, get_model

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def summarize_chunk(client, model_id: str, chunk_text: str, prompt_context: str, retries: int = 3) -> str:
    """Summarize a chunk of text using Gemini."""
    prompt = f"""{prompt_context}

Please provide a concise, bulleted summary of the key events, actions, and insights from the following stigmergy data.
Focus on the most important signals. Do not lose critical information, but roll it up progressively.

Data:
{chunk_text}
"""
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config={
                    "temperature": 0.2,
                    "max_output_tokens": 2048,
                }
            )
            return response.text
        except Exception as e:
            print(f"  [Attempt {attempt+1}/{retries}] Error summarizing chunk: {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(5)
            else:
                return f"[Error summarizing chunk after {retries} attempts: {e}]"

def main():
    parser = argparse.ArgumentParser(description="Generate weekly stigmergy report via progressive summarization.")
    parser.add_argument("--days", type=int, default=7, help="Number of days to look back (default: 7)")
    parser.add_argument("--model", type=str, default="flash_25", help="Model to use (default: flash_25)")
    parser.add_argument("--chunk-size", type=int, default=500, help="Number of events per chunk (default: 500)")
    args = parser.parse_args()

    client, mode = create_gemini_client()
    if not client:
        print("Error: Could not initialize Gemini client. Check API key.", file=sys.stderr)
        sys.exit(1)

    model_id = get_model(args.model).model_id
    print(f"Using model: {model_id}")

    conn = get_db()
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(days=args.days)
    
    print(f"Fetching events from {start_time.isoformat()} to {now.isoformat()}...")
    
    cursor = conn.execute(
        """SELECT event_type, timestamp, subject, substr(data_json, 1, 500) as data_preview
           FROM stigmergy_events
           WHERE timestamp >= ?
           ORDER BY timestamp ASC""",
        (start_time.isoformat(),)
    )
    events = [dict(row) for row in cursor.fetchall()]
    conn.close()

    print(f"Found {len(events)} events.")
    if not events:
        print("No events found.")
        sys.exit(0)

    # Group by day
    events_by_day = {}
    for event in events:
        day = event["timestamp"][:10]
        if day not in events_by_day:
            events_by_day[day] = []
        events_by_day[day].append(event)

    daily_summaries = {}
    
    for day, day_events in sorted(events_by_day.items()):
        print(f"\nProcessing {day} ({len(day_events)} events)...")
        
        # Chunk events
        chunks = []
        for i in range(0, len(day_events), args.chunk_size):
            chunk = day_events[i:i + args.chunk_size]
            chunk_text = "\n".join([f"[{e['timestamp']}] {e['event_type']} - {e['subject']}: {e['data_preview']}" for e in chunk])
            chunks.append(chunk_text)
            
        print(f"  Split into {len(chunks)} chunks.")
        
        chunk_summaries = []
        for i, chunk_text in enumerate(chunks):
            print(f"  Summarizing chunk {i+1}/{len(chunks)}...")
            summary = summarize_chunk(client, model_id, chunk_text, f"You are summarizing stigmergy events for {day}.")
            chunk_summaries.append(summary)
            
        if len(chunk_summaries) > 1:
            print(f"  Rolling up {len(chunk_summaries)} chunk summaries into a daily summary...")
            combined_text = "\n\n".join([f"--- Chunk {i+1} Summary ---\n{s}" for i, s in enumerate(chunk_summaries)])
            daily_summary = summarize_chunk(client, model_id, combined_text, f"You are creating a final daily rollup for {day} based on partial summaries.")
            daily_summaries[day] = daily_summary
        else:
            daily_summaries[day] = chunk_summaries[0]
            
        print(f"  Daily summary for {day} complete.")

    print("\nGenerating final weekly rollup...")
    combined_daily = "\n\n".join([f"=== {day} ===\n{s}" for day, s in sorted(daily_summaries.items())])
    
    weekly_summary = summarize_chunk(client, model_id, combined_daily, "You are creating a concise weekly executive summary based on the following daily summaries. Highlight the major themes, architectural changes, and key agent activities.")

    report = f"""# Stigmergy Weekly Rollup ({start_time.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')})

## Executive Summary
{weekly_summary}

## Daily Breakdowns
"""
    for day, summary in sorted(daily_summaries.items(), reverse=True):
        report += f"\n### {day}\n{summary}\n"

    report_path = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "0_bronze" / "archives" / f"{now.strftime('%Y-%m-%d')}_stigmergy_weekly_rollup.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
        
    print(f"\nReport saved to {report_path}")

if __name__ == "__main__":
    main()
