"""Update obsidian_blackboard to mark gesture_fsm as hardened at 81.91%."""
import sqlite3
import os

DB = r'C:/hfoDev/hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite'

if not os.path.exists(DB):
    print(f'DB NOT FOUND: {DB}')
    raise SystemExit(1)

conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute(
    """UPDATE obsidian_blackboard
       SET status='hardened',
           stryker_score=81.91,
           test_file='test_gesture_fsm.ts',
           notes='81.91% goldilocks | 100 tests | 4 Stryker rounds | FsmDriver helper injectable timestamps'
       WHERE tile_key='gesture_fsm'"""
)
print(f'Rows updated: {cur.rowcount}')
conn.commit()

cur.execute(
    "SELECT tile_key, status, stryker_score, test_file FROM obsidian_blackboard WHERE tile_key='gesture_fsm'"
)
row = cur.fetchone()
print(f'Verified: {row}')

# Also show full hardened tiles
cur.execute("SELECT tile_key, stryker_score, status FROM obsidian_blackboard WHERE status='hardened' ORDER BY stryker_score DESC")
print('All hardened tiles:', cur.fetchall())

conn.close()
print('Done.')
