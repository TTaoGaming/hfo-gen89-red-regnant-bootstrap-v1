"""Smoke test for hfo_port_journal + hfo_identity_loader."""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

from hfo_port_journal import write_entry, get_time_ladder, get_chain_head, verify_chain
from hfo_identity_loader import get_identity_prompt, get_full_bundle
from hfo_port_context_bundle import get_identity_prompt as gip, get_full_bundle_md as gfb

errors = []
_ts = str(time.time())  # unique suffix so re-runs don't hit UNIQUE constraint

# 1. Journal write P4
r = write_entry(4, f"Smoke test: Red Regnant identity loader initialised [{_ts}]", entry_type="memory", perceive_nonce="SMOKE01")
assert r["port"] == 4
assert len(r["chain_hash"]) == 64
print(f"[1] Journal write P4  chain:{r['chain_hash'][:12]}  parent:{r['parent_hash'][:12]}")

# 2. Journal write P7
r2 = write_entry(7, f"Smoke test: Spider Sovereign navigator initialised [{_ts}]", entry_type="memory", perceive_nonce="SMOKE01")
assert r2["port"] == 7
print(f"[2] Journal write P7  chain:{r2['chain_hash'][:12]}  parent:{r2['parent_hash'][:12]}")

# 3. Chain head
head = get_chain_head(4)
assert head is not None
assert head["entry_type"] == "memory"
print(f"[3] Chain head P4  id:{head['id']}  type:{head['entry_type']}")

# 4. Verify chain
v = verify_chain(4)
assert v["valid"], f"Chain broken at: {v['broken_at']}"
print(f"[4] Chain verify P4  entries:{v['total_entries']}  valid:{v['valid']}")

# 5. Time ladder (markdown)
ladder = get_time_ladder(4, as_markdown=True)
lines = [l for l in ladder.splitlines() if l.strip()]
assert "TIER-1" in ladder
print(f"[5] Time ladder P4  lines:{len(lines)}  header:{lines[0][:60]}")

# 6. Identity prompt
prompt = get_identity_prompt(4)
assert "Red Regnant" in prompt
assert "EMBODIMENT DIRECTIVE" in prompt
assert "INHABITATION PROTOCOL" in prompt
prompt_lines = prompt.splitlines()
print(f"[6] Identity prompt P4  lines:{len(prompt_lines)}  header:{prompt_lines[0][:60]}")

# 7. Full bundle
full = get_full_bundle(4)
assert "Red Regnant" in full
assert "TIER-1" in full
print(f"[7] Full bundle P4  chars:{len(full)}")

# 8. Assembler re-exports
p = gip(0)
assert "Lidless Legion" in p
print(f"[8] Assembler re-export P0 get_identity_prompt  lines:{len(p.splitlines())}")

fb = gfb(0)
assert "Lidless Legion" in fb
print(f"[8] Assembler re-export P0 get_full_bundle_md  chars:{len(fb)}")

# 9. All 8 ports identity prompt
for port in range(8):
    ip = get_identity_prompt(port)
    assert "EMBODIMENT DIRECTIVE" in ip, f"P{port} missing EMBODIMENT DIRECTIVE"
print(f"[9] All 8 ports identity prompts OK")

# 10. Verify chain integrity for all written ports
for port in [4, 7]:
    vc = verify_chain(port)
    assert vc["valid"], f"P{port} chain broken: {vc['broken_at']}"
print(f"[10] Chain integrity P4 + P7 OK")

print()
print("ALL SMOKE TESTS PASSED")
