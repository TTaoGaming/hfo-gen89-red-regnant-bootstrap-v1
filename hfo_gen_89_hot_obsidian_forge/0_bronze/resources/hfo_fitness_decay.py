"""
HFO Fitness Decay — Half-Life Staleness Detection for Mission Tasks.

Port: P7 NAVIGATE (Spider Sovereign) — steering through temporal fitness landscape.
Medallion: bronze (new implementation).

Implements exponential decay: fitness_decayed = fitness * (0.5 ^ (age_days / half_life_days))

This ensures tasks that haven't been touched decay toward zero,
surfacing stale work that needs attention.
"""

import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def compute_decayed_fitness(
    fitness: float,
    age_days: float = 0.0,
    half_life_days: float = 14.0,
) -> float:
    """Compute exponentially decayed fitness using half-life model.

    Args:
        fitness: Raw fitness score (0.0 - 1.0)
        age_days: Days since last touch
        half_life_days: Days until fitness halves (default: 14)

    Returns:
        Decayed fitness score (0.0 - 1.0)

    SBE:
        Given a task with fitness F last touched T days ago
        When compute_decayed_fitness(F, T, half_life=H) is called
        Then returns F * 2^(-T/H)
    """
    if half_life_days <= 0:
        raise ValueError("half_life_days must be positive")
    if fitness < 0 or fitness > 1:
        raise ValueError(f"fitness must be 0-1, got {fitness}")

    decay_factor = math.pow(0.5, age_days / half_life_days)
    return fitness * decay_factor


def get_task_ages(db_path: str) -> list[dict]:
    """Get all mission_state tasks with their age in days.

    Returns list of dicts with: thread_key, title, fitness, updated_at, age_days, decayed_fitness
    """
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "SELECT thread_key, title, fitness, updated_at "
            "FROM mission_state WHERE thread_type = 'task'"
        )
        now = datetime.now(timezone.utc)
        tasks = []
        for row in cur.fetchall():
            thread_key, title, fitness, updated_at = row
            age_days = 0.0
            if updated_at:
                try:
                    ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                    age_days = (now - ts).total_seconds() / 86400
                except ValueError:
                    age_days = 0.0
            fitness_val = float(fitness) if fitness else 0.0
            tasks.append({
                "thread_key": thread_key,
                "title": title,
                "fitness": fitness_val,
                "updated_at": updated_at,
                "age_days": round(age_days, 2),
                "decayed_fitness": round(compute_decayed_fitness(fitness_val, age_days), 4),
            })
        return tasks
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).resolve().parent.parent.parent
        / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
    )
    tasks = get_task_ages(db_path)
    print(f"\n{'Key':<15} {'Fitness':>8} {'Age(d)':>8} {'Decayed':>8}  Title")
    print("-" * 70)
    for t in sorted(tasks, key=lambda x: x["decayed_fitness"]):
        print(f"{t['thread_key']:<15} {t['fitness']:>8.2f} {t['age_days']:>8.1f} "
              f"{t['decayed_fitness']:>8.4f}  {t['title'][:40]}")
