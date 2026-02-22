"""Fail-closed path validation: DEGRADED + BROKEN + restore."""
import sys
sys.path.insert(0, 'hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources')
import hfo_identity_sqlite as ids

conn = ids.open_ssot()

# --- DEGRADED: P3 has identity but no journal ---
r3 = ids.rehydrate(3, conn)
assert r3["health"] == ids.HEALTH_DEGRADED, f"Expected DEGRADED, got {r3['health']}"
assert r3["identity"] is not None, "DEGRADED should still have identity"
assert r3["missing"] == [], f"DEGRADED should have no missing, got {r3['missing']}"
assert len(r3["degraded"]) > 0, "DEGRADED should have degraded list"
print(f"[PASS] P3 DEGRADED — identity:{r3['identity'] is not None}, degraded_msgs:{len(r3['degraded'])}")
print(f"       Degraded: {r3['degraded'][0][:80]}")
print(f"       Operator report first line: {(r3.get('operator_report') or '').splitlines()[0]}")
print()

# --- BROKEN: delete P5 identity row to simulate missing ingest ---
conn.execute("DELETE FROM port_commander_identity WHERE port = 5")
conn.commit()
r5 = ids.rehydrate(5, conn)
assert r5["health"] == ids.HEALTH_BROKEN, f"Expected BROKEN, got {r5['health']}"
assert r5["identity"] is None, "BROKEN should have no identity"
assert len(r5["missing"]) > 0, "BROKEN should have missing list"
report_lines = (r5.get("operator_report") or "").splitlines()
assert len(report_lines) > 2, "operator_report should be multi-line"
print(f"[PASS] P5 BROKEN — missing:{len(r5['missing'])}, report_lines:{len(report_lines)}")
print(f"       Missing: {r5['missing'][0][:80]}")
print(f"       Remediation visible: {'ingest' in r5.get('operator_report','')}")
print()

# --- Restore P5 ---
ri = ids.ingest_port(5, conn, force=True)
assert ri["action"] == "inserted", f"Expected inserted, got {ri['action']}"
r5r = ids.rehydrate(5, conn)
assert r5r["health"] in (ids.HEALTH_HEALTHY, ids.HEALTH_DEGRADED)
print(f"[PASS] P5 restored via ingest — health now: {r5r['health']}")
print()

# --- JSON-key completeness check on HEALTHY port ---
r4 = ids.rehydrate(4, conn)
assert r4["health"] == ids.HEALTH_HEALTHY
required_keys = ["port","commander","trigram","word","health","missing","degraded",
                 "identity","cognitive_persistence","diagnostics","ingested_at","bundle_hash"]
for k in required_keys:
    assert k in r4, f"Key missing from rehydrate output: {k}"
print(f"[PASS] P4 HEALTHY — all {len(required_keys)} required keys present")

# --- Cognitive persistence structure ---
cog = r4["cognitive_persistence"]
for tier in ["tier_1_1hr","tier_2_1day","tier_3_1week","tier_4_1month"]:
    assert tier in cog, f"Missing tier: {tier}"
assert "total_entries" in cog
assert "chain_head" in cog
print(f"[PASS] P4 cognitive_persistence has all 4 tiers, total_entries={cog['total_entries']}")

conn.close()
print()
print("ALL FAIL-CLOSED PATH TESTS PASSED")
