#!/usr/bin/env python3
"""
hfo_p0_stigmergy_watchdog.py — Port 0 Stigmergy Watchdog Daemon

Monitors the stigmergy_events table for:
1. Orphaned sessions (Perceive without Yield after a timeout)
2. Broken chains (Yield without Perceive)

Writes memory_loss and tamper_alert events to enforce the PREY8 state machine.
"""

import json
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Ensure local imports work
sys.path.insert(0, str(Path(__file__).resolve().parent))

from hfo_ssot_write import write_stigmergy_event, build_signal_metadata

DB_PATH = Path(__file__).resolve().parent.parent.parent / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite"
ORPHAN_TIMEOUT_MINUTES = 5

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def scan_for_orphans(conn: sqlite3.Connection):
    """Find Perceive events older than timeout without a matching Yield."""
    now = datetime.now(timezone.utc)
    timeout_threshold = now - timedelta(minutes=ORPHAN_TIMEOUT_MINUTES)
    
    # Get recent perceives
    perceives = list(conn.execute(
        """SELECT id, timestamp, data_json FROM stigmergy_events
           WHERE event_type LIKE '%prey8.perceive%'
           ORDER BY timestamp DESC LIMIT 100"""
    ))
    
    # Get recent yields
    yields = list(conn.execute(
        """SELECT id, timestamp, data_json FROM stigmergy_events
           WHERE event_type LIKE '%prey8.yield%'
           ORDER BY timestamp DESC LIMIT 100"""
    ))
    
    yield_nonces = set()
    for row in yields:
        try:
            data = json.loads(row[2]).get("data", {})
            nonce = data.get("nonce", "")
            if nonce:
                yield_nonces.add(nonce)
        except Exception:
            pass
            
    for row in perceives:
        try:
            ts_str = row[1]
            # Handle different ISO formats
            if ts_str.endswith('Z'):
                ts_str = ts_str[:-1] + '+00:00'
            ts = datetime.fromisoformat(ts_str)
            
            if ts < timeout_threshold:
                data = json.loads(row[2]).get("data", {})
                nonce = data.get("nonce", "")
                agent_id = data.get("agent_id", "unknown")
                
                if nonce and nonce not in yield_nonces:
                    # Check if we already logged a memory loss for this nonce
                    existing = conn.execute(
                        """SELECT 1 FROM stigmergy_events 
                           WHERE event_type LIKE '%memory_loss%' 
                           AND data_json LIKE ?""",
                        (f'%{nonce}%',)
                    ).fetchone()
                    
                    if not existing:
                        print(f"Detected orphaned session: {nonce} (Agent: {agent_id})")
                        _record_memory_loss(conn, nonce, agent_id, ts_str)
        except Exception as e:
            print(f"Error processing perceive row {row[0]}: {e}")

def _record_memory_loss(conn: sqlite3.Connection, nonce: str, agent_id: str, perceive_ts: str):
    """Write a memory_loss event for an orphaned session."""
    signal_meta = build_signal_metadata(
        port="P0",
        model_id="system",
        daemon_name="p0_stigmergy_watchdog",
        daemon_version="1.0"
    )
    
    event_data = {
        "loss_type": "orphaned_session_timeout",
        "agent_id": agent_id,
        "orphaned_perceive_nonce": nonce,
        "perceive_timestamp": perceive_ts,
        "timeout_minutes": ORPHAN_TIMEOUT_MINUTES,
        "note": "Watchdog detected a Perceive event without a matching Yield within the timeout period."
    }
    
    write_stigmergy_event(
        event_type="hfo.gen90.prey8.memory_loss",
        subject="prey-memory-loss",
        data=event_data,
        signal_metadata=signal_meta,
        source="p0_stigmergy_watchdog",
        conn=conn
    )
    conn.commit()

def scan_for_broken_chains(conn: sqlite3.Connection):
    """Find Yield events without a matching Perceive."""
    # Get recent yields
    yields = list(conn.execute(
        """SELECT id, timestamp, data_json FROM stigmergy_events
           WHERE event_type LIKE '%prey8.yield%'
           ORDER BY timestamp DESC LIMIT 100"""
    ))
    
    # Get recent perceives
    perceives = list(conn.execute(
        """SELECT id, timestamp, data_json FROM stigmergy_events
           WHERE event_type LIKE '%prey8.perceive%'
           ORDER BY timestamp DESC LIMIT 100"""
    ))
    
    perceive_nonces = set()
    for row in perceives:
        try:
            data = json.loads(row[2]).get("data", {})
            nonce = data.get("nonce", "")
            if nonce:
                perceive_nonces.add(nonce)
        except Exception:
            pass
            
    for row in yields:
        try:
            data = json.loads(row[2]).get("data", {})
            nonce = data.get("nonce", "")
            agent_id = data.get("agent_id", "unknown")
            
            if nonce and nonce not in perceive_nonces:
                # Check if we already logged a tamper alert for this nonce
                existing = conn.execute(
                    """SELECT 1 FROM stigmergy_events 
                       WHERE event_type LIKE '%tamper_alert%' 
                       AND data_json LIKE ?""",
                    (f'%{nonce}%',)
                ).fetchone()
                
                if not existing:
                    print(f"Detected broken chain (Yield without Perceive): {nonce} (Agent: {agent_id})")
                    _record_tamper_alert(conn, nonce, agent_id, row[1])
        except Exception as e:
            print(f"Error processing yield row {row[0]}: {e}")

def _record_tamper_alert(conn: sqlite3.Connection, nonce: str, agent_id: str, yield_ts: str):
    """Write a tamper_alert event for a broken chain."""
    signal_meta = build_signal_metadata(
        port="P0",
        model_id="system",
        daemon_name="p0_stigmergy_watchdog",
        daemon_version="1.0"
    )
    
    event_data = {
        "alert_type": "broken_chain_yield_without_perceive",
        "agent_id": agent_id,
        "invalid_nonce": nonce,
        "yield_timestamp": yield_ts,
        "note": "Watchdog detected a Yield event with a nonce that has no corresponding Perceive event."
    }
    
    write_stigmergy_event(
        event_type="hfo.gen90.prey8.tamper_alert",
        subject="prey-tamper-alert",
        data=event_data,
        signal_metadata=signal_meta,
        source="p0_stigmergy_watchdog",
        conn=conn
    )
    conn.commit()

def main():
    print("Starting Port 0 Stigmergy Watchdog...")
    while True:
        try:
            conn = _get_conn()
            scan_for_orphans(conn)
            scan_for_broken_chains(conn)
            conn.close()
        except Exception as e:
            print(f"Watchdog error: {e}")
        
        time.sleep(60) # Scan every minute

if __name__ == "__main__":
    main()
