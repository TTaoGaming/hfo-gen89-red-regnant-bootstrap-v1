"""Seed a single chimera eval event into SSOT for BDD test verification."""
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

db = str(Path(__file__).resolve().parent.parent.parent / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite")
conn = sqlite3.connect(db)
ts = datetime.now(timezone.utc).isoformat()

event = {
    "specversion": "1.0",
    "type": "hfo.gen89.p2.chimera.eval",
    "source": "hfo_p2_chimera_loop/seed",
    "subject": "chimera-eval-seed",
    "time": ts,
    "data": {
        "genome_id": "seed_default_red_regnant",
        "traits": {
            "tone": "authoritative_coach",
            "adversarial_depth": "deep_structural",
            "reasoning_style": "chain_of_thought",
            "gate_philosophy": "fail_closed_strict",
            "meadows_strategy": "level_appropriate",
            "sbe_style": "5_tier_tower",
            "trust_posture": "verify_then_trust",
            "artifact_discipline": "structured_receipt",
        },
        "fitness": {
            "coding_accuracy": 0.7,
            "gate_compliance": 0.85,
            "adversarial_depth": 0.8,
            "meadows_alignment": 0.75,
            "token_efficiency": 0.6,
            "latency_score": 0.5,
        },
        "aggregate_score": 0.72,
        "model": "seed",
        "generation": 0,
        "population_slot": 0,
    },
}

c_hash = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
conn.execute(
    "INSERT OR IGNORE INTO stigmergy_events "
    "(event_type, timestamp, subject, source, data_json, content_hash) "
    "VALUES (?, ?, ?, ?, ?, ?)",
    (event["type"], ts, event["subject"], event["source"], json.dumps(event), c_hash),
)
conn.commit()
print("Seeded chimera eval event")
conn.close()
