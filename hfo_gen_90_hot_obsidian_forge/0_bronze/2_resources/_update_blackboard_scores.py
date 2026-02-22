"""Update obsidian_blackboard with real Stryker scores from the hardening run."""
import sqlite3
from datetime import datetime, timezone

DB = 'hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite'
NOW = datetime.now(timezone.utc).isoformat()

conn = sqlite3.connect(DB)

# Update event_bus tile with real score
conn.execute("""
    UPDATE obsidian_blackboard SET
        status = 'passed',
        stryker_score = 84.31,
        test_file = 'hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/test_event_bus.test.ts',
        notes = 'Stryker 84.31% (Goldilocks 80-99%). 37 killed, 6 timeout, 8 survived. Remaining: conditional+unary in NODE_ENV dev block (unkillable in test env) + 6 sentinel string literals.',
        updated_at = ?
    WHERE tile_key = 'event_bus'
""", (NOW,))

# Register kalman_filter tile with real score (was unvalidated, now passed)
conn.execute("""
    UPDATE obsidian_blackboard SET
        status = 'passed',
        stryker_score = 95.08,
        assignee = 'p7_spider_sovereign',
        test_file = 'hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15/test_kalman_filter.test.ts',
        notes = 'Stryker 95.08% (Goldilocks 80-99%). 56 killed, 2 timeout, 3 survived. Near-perfect. Remaining: 2 ArithmeticOp + 1 ConditionalExpr.',
        updated_at = ?
    WHERE tile_key = 'kalman_filter'
""", (NOW,))

conn.commit()

print("=== BLACKBOARD AFTER HARDENING ===")
for r in conn.execute("""
    SELECT tile_key, status, stryker_score, assignee
    FROM obsidian_blackboard ORDER BY priority
"""):
    score = f"{r[2]:.1f}%" if r[2] else "n/a"
    assignee = r[3] or "-"
    print(f"  {r[0]:35s} | {r[1]:12s} | {score:8s} | {assignee}")

conn.close()
print("\nDONE")
