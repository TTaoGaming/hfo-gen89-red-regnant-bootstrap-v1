import os
import sys
import time
import json
import uuid
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
HFO_ROOT = Path(os.getenv("HFO_ROOT", "C:/hfoDev"))
FORGE_DIR = HFO_ROOT / os.getenv("HFO_FORGE", "hfo_gen_90_hot_obsidian_forge")
SSOT_DB = FORGE_DIR / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite"
BRONZE_RESOURCES = FORGE_DIR / "0_bronze" / "2_resources"
HFO_RESOURCES = FORGE_DIR / "3_hyper_fractal_obsidian" / "2_resources"
CONFIG_FILE = HFO_RESOURCES / "p5_lifecycle_config.json"

def load_config():
    default_config = {
        "HFO_P5_MAX_VRAM_PERCENT": 85.0,
        "HFO_P5_MAX_CPU_PERCENT": 90.0,
        "HFO_P5_AUTOTUNE_ENABLED": True,
        "HFO_P5_RESTART_DELAY_SEC": 10,
        "HFO_OLLAMA_BATCH_SIZE": 5,
        "HFO_GEMINI_DELAY_SEC": 2
    }
    if not CONFIG_FILE.exists():
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(default_config, f, indent=4)
        return default_config
    
    with open(CONFIG_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return default_config

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

# Daemons to manage
DAEMONS = {
    "resource_governor": ["python", "-u", str(BRONZE_RESOURCES / "hfo_resource_governor.py"), "monitor"],
    "shodh": ["python", "-u", str(BRONZE_RESOURCES / "hfo_shodh.py"), "--seed-from-stigmergy"],
    "npu_embedder": ["python", "-u", str(BRONZE_RESOURCES / "hfo_npu_embedder.py"), "embed"],
    "gpu_devourer": ["python", "-u", str(BRONZE_RESOURCES / "hfo_p6_devourer_daemon.py")],
    "cloud_summarizer": ["python", "-u", str(BRONZE_RESOURCES / "hfo_progressive_summarizer.py"), "--daemon"]
}

class P5LifecycleDaemon:
    def __init__(self, reset=False):
        self.processes = {}
        self.crash_counts = {name: 0 for name in DAEMONS}
        self.total_crashes = {name: 0 for name in DAEMONS}
        self.last_crash_time = {name: 0 for name in DAEMONS}
        self.dead_daemons = set()
        self.conn = sqlite3.connect(SSOT_DB)
        self.cursor = self.conn.cursor()
        self._ensure_stigmergy_table()
        
        if reset:
            self._reset_stigmergy_state()
        else:
            self._restore_state_from_stigmergy()

    def _reset_stigmergy_state(self):
        print("[P5 IMMUNIZE] Resetting stigmergy state for all daemons...")
        for name in DAEMONS:
            self.cursor.execute('''
                DELETE FROM stigmergy_events 
                WHERE subject = ? AND event_type LIKE 'hfo.gen90.p5.lifecycle.%'
            ''', (name,))
        self.conn.commit()
        print("State reset complete.")

    def _restore_state_from_stigmergy(self):
        print("[P5 IMMUNIZE] Restoring state from stigmergy trail...")
        for name in DAEMONS:
            self.cursor.execute('''
                SELECT event_type, data_json, timestamp 
                FROM stigmergy_events 
                WHERE subject = ? AND event_type LIKE 'hfo.gen90.p5.lifecycle.%'
                ORDER BY timestamp DESC LIMIT 50
            ''', (name,))
            rows = self.cursor.fetchall()
            
            if not rows:
                continue
                
            latest_event_type = rows[0][0]
            latest_data_json = rows[0][1]
            try:
                cloudevent = json.loads(latest_data_json)
                event_data = cloudevent.get("data", {})
            except:
                event_data = {}
                
            if latest_event_type == 'hfo.gen90.p5.lifecycle.completed':
                print(f"  -> {name} was previously marked as DONE. Skipping.")
                self.dead_daemons.add(name)
            elif latest_event_type == 'hfo.gen90.p5.lifecycle.circuit_breaker':
                print(f"  -> {name} previously tripped the circuit breaker. Marking as DEAD.")
                self.dead_daemons.add(name)
                self.total_crashes[name] = event_data.get('total_crashes', 5)
            else:
                self.cursor.execute('''
                    SELECT COUNT(*) FROM stigmergy_events
                    WHERE subject = ? AND event_type = 'hfo.gen90.p5.lifecycle.crash'
                ''', (name,))
                crash_count = self.cursor.fetchone()[0]
                if crash_count > 0:
                    self.total_crashes[name] = crash_count
                    print(f"  -> {name} has {crash_count} previous crashes recorded.")
                    if crash_count >= 5:
                        print(f"  -> {name} has >= 5 crashes. Marking as DEAD.")
                        self.dead_daemons.add(name)

    def _ensure_stigmergy_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS stigmergy_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT,
                subject TEXT,
                data_json TEXT,
                content_hash TEXT UNIQUE NOT NULL
            )
        ''')
        self.conn.commit()

    def emit_stigmergy(self, event_type: str, subject: str, data: dict):
        timestamp = datetime.now(timezone.utc).isoformat()
        event_id = uuid.uuid4().hex
        
        cloudevent = {
            "specversion": "1.0",
            "id": event_id,
            "type": event_type,
            "source": "hfo_p5_lifecycle_daemon",
            "subject": subject,
            "time": timestamp,
            "data": data
        }
        
        data_str = json.dumps(cloudevent)
        content_hash = uuid.uuid5(uuid.NAMESPACE_URL, data_str).hex
        
        try:
            self.cursor.execute(
                "INSERT INTO stigmergy_events (event_type, timestamp, source, subject, data_json, content_hash) VALUES (?, ?, ?, ?, ?, ?)",
                (event_type, timestamp, "hfo_p5_lifecycle_daemon", subject, data_str, content_hash)
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass # Duplicate

    def start_daemon(self, name: str):
        if name in self.processes and self.processes[name].poll() is None:
            return # Already running
            
        print(f"[P5 IMMUNIZE] Starting {name}...")
        cmd = DAEMONS[name]
        # Start process, redirecting output to devnull to avoid console spam, or to a log file
        log_file = open(f"{name}_p5.log", "a", encoding="utf-8")
        
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        self.processes[name] = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT, env=env)
        self.emit_stigmergy("hfo.gen90.p5.lifecycle.start", name, {"pid": self.processes[name].pid})

    def autotune(self, name: str):
        config = load_config()
        if not config.get("HFO_P5_AUTOTUNE_ENABLED", True):
            return
            
        print(f"[P5 IMMUNIZE] Autotuning triggered for {name} due to frequent crashes.")
        
        # Example autotuning logic: increase delay or reduce batch size
        if name == "gpu_devourer":
            current_batch = config.get("HFO_OLLAMA_BATCH_SIZE", 5)
            new_batch = max(1, current_batch - 1)
            config["HFO_OLLAMA_BATCH_SIZE"] = new_batch
            save_config(config)
            print(f"  -> Reduced HFO_OLLAMA_BATCH_SIZE to {new_batch}")
            self.emit_stigmergy("hfo.gen90.p5.lifecycle.autotune", name, {"param": "HFO_OLLAMA_BATCH_SIZE", "new_value": new_batch})
            
        elif name == "cloud_summarizer":
            current_delay = config.get("HFO_GEMINI_DELAY_SEC", 2)
            new_delay = current_delay + 2
            config["HFO_GEMINI_DELAY_SEC"] = new_delay
            save_config(config)
            print(f"  -> Increased HFO_GEMINI_DELAY_SEC to {new_delay}")
            self.emit_stigmergy("hfo.gen90.p5.lifecycle.autotune", name, {"param": "HFO_GEMINI_DELAY_SEC", "new_value": new_delay})

    def monitor_loop(self):
        print("[P5 IMMUNIZE] Lifecycle Daemon Started. Monitoring swarm...")
        self.emit_stigmergy("hfo.gen90.p5.lifecycle.heartbeat", "swarm", {"status": "monitoring"})
        
        # Initial start
        for name in DAEMONS:
            self.start_daemon(name)
            
        try:
            while True:
                for name, proc in list(self.processes.items()):
                    if name in self.dead_daemons:
                        continue
                        
                    if proc.poll() is not None:
                        # Process died
                        exit_code = proc.returncode
                        
                        if exit_code == 0:
                            print(f"\n[P5 IMMUNIZE] INFO: {name} completed successfully (exit code 0). Marking as DONE.")
                            self.emit_stigmergy("hfo.gen90.p5.lifecycle.completed", name, {"exit_code": exit_code})
                            self.dead_daemons.add(name)
                            continue
                            
                        print(f"\n[P5 IMMUNIZE] WARNING: {name} died with exit code {exit_code}")
                        self.emit_stigmergy("hfo.gen90.p5.lifecycle.crash", name, {"exit_code": exit_code})
                        
                        # Print the tail of the log file so the user knows WHY it died
                        log_path = f"{name}_p5.log"
                        if os.path.exists(log_path):
                            print(f"--- TAIL OF {log_path} ---")
                            try:
                                with open(log_path, "r", encoding="utf-8") as f:
                                    lines = f.readlines()
                                    for line in lines[-10:]:
                                        print(line.strip())
                            except Exception as e:
                                print(f"Could not read log file: {e}")
                            print("---------------------------\n")
                        
                        self.total_crashes[name] += 1
                        if self.total_crashes[name] >= 5:
                            print(f"[P5 IMMUNIZE] CIRCUIT BREAKER TRIPPED: {name} has crashed 5 times. Marking as DEAD and will not restart.")
                            self.emit_stigmergy("hfo.gen90.p5.lifecycle.circuit_breaker", name, {"total_crashes": self.total_crashes[name]})
                            self.dead_daemons.add(name)
                            continue
                        
                        now = time.time()
                        if now - self.last_crash_time[name] < 60:
                            self.crash_counts[name] += 1
                        else:
                            self.crash_counts[name] = 1
                            
                        self.last_crash_time[name] = now
                        
                        if self.crash_counts[name] >= 3:
                            self.autotune(name)
                            self.crash_counts[name] = 0 # Reset after autotune
                            
                        config = load_config()
                        restart_delay = config.get("HFO_P5_RESTART_DELAY_SEC", 10)
                        print(f"[P5 IMMUNIZE] Restarting {name} in {restart_delay} seconds... (Crash {self.total_crashes[name]}/5)")
                        time.sleep(restart_delay)
                        self.start_daemon(name)
                        
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("\n[P5 IMMUNIZE] Shutting down swarm...")
            for name, proc in self.processes.items():
                proc.terminate()
            self.emit_stigmergy("hfo.gen90.p5.lifecycle.shutdown", "swarm", {})
            print("Shutdown complete.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="P5 Lifecycle Daemon")
    parser.add_argument("--reset", action="store_true", help="Reset stigmergy state for all daemons")
    args = parser.parse_args()
    
    daemon = P5LifecycleDaemon(reset=args.reset)
    daemon.monitor_loop()
