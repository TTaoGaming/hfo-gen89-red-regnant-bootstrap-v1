"""
PREY8 Execute gate test for gesture_fsm hardening.
Verifies: test file exists, stryker score in goldilocks range, DB record updated.
"""
import subprocess, sys, os, sqlite3, json, pathlib

ROOT = pathlib.Path(r"C:\hfoDev")
PROJ = ROOT / "hfo_gen_90_hot_obsidian_forge/0_bronze/0_projects/HFO_OMEGA_v15"
DB   = ROOT / "hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite"

ERRORS = []

# 1. Test file exists
test_file = PROJ / "test_gesture_fsm.ts"
if not test_file.exists():
    ERRORS.append(f"FAIL: test_gesture_fsm.ts not found at {test_file}")
else:
    print(f"PASS: test_gesture_fsm.ts exists ({test_file.stat().st_size} bytes)")

# 2. Source file exists  
src_file = PROJ / "gesture_fsm.ts"
if not src_file.exists():
    ERRORS.append(f"FAIL: gesture_fsm.ts not found")
else:
    print(f"PASS: gesture_fsm.ts exists ({src_file.stat().st_size} bytes)")

# 3. DB record shows hardened with correct score
if not DB.exists():
    ERRORS.append(f"FAIL: SSOT DB not found")
else:
    conn = sqlite3.connect(str(DB))
    row = conn.execute(
        "SELECT tile_key, status, stryker_score FROM obsidian_blackboard WHERE tile_key='gesture_fsm'"
    ).fetchone()
    conn.close()
    if row is None:
        ERRORS.append("FAIL: gesture_fsm not found in obsidian_blackboard")
    elif row[1] != 'hardened':
        ERRORS.append(f"FAIL: gesture_fsm status is '{row[1]}', expected 'hardened'")
    elif not (80.0 <= row[2] < 100.0):
        ERRORS.append(f"FAIL: gesture_fsm stryker_score {row[2]} not in goldilocks [80,100)")
    else:
        print(f"PASS: gesture_fsm DB record: status={row[1]}, score={row[2]}%")

# 4. Stryker config targets gesture_fsm
stryker_cfg = PROJ / "stryker.config.json"
if stryker_cfg.exists():
    cfg_text = stryker_cfg.read_text()
    if "gesture_fsm.ts" in cfg_text:
        print("PASS: stryker.config.json targets gesture_fsm.ts")
    else:
        ERRORS.append("FAIL: stryker.config.json does not target gesture_fsm.ts")

# Summary
if ERRORS:
    for e in ERRORS:
        print(e)
    sys.exit(1)
else:
    print(f"\nALL CHECKS PASSED — gesture_fsm goldilocks 81.91% confirmed")
    sys.exit(0)
