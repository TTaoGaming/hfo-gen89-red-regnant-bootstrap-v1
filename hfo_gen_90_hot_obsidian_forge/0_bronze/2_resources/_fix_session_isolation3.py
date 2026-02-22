"""Add session isolation pops before first _get_session call per agent per test."""
import re
from pathlib import Path

path = Path('tests/test_prey8_mcp_server.py')
content = path.read_text(encoding='utf-8')
original = content

# For each match of _get_session("xxx"), check if we need to add a pop
# We want to add prey8._sessions.pop("xxx", None) before the FIRST occurrence
# of prey8._get_session("xxx") in each test function, unless it's already there.

# Find all test functions boundaries
func_starts = [m.start() for m in re.finditer(r'^def test_', content, re.MULTILINE)]
func_starts.append(len(content))

# Process in reverse order (bottom to top) so inserts don't mess up positions
all_insertions = []

for fi in range(len(func_starts) - 1):
    start = func_starts[fi]
    end = func_starts[fi + 1]
    func_block = content[start:end]
    
    # Find all get_session calls and their agents
    sessions_in_func = re.finditer(r'prey8\._get_session\("(\w+)"\)', func_block)
    seen_agents = set()
    
    for sm in sessions_in_func:
        agent_id = sm.group(1)
        if agent_id in seen_agents:
            continue  # Only process first occurrence per agent per test
        seen_agents.add(agent_id)
        
        # Absolute position of this match in content
        abs_pos = start + sm.start()
        
        # Check the preceding 200 chars for existing pop
        preceding = content[max(0, abs_pos - 200):abs_pos]
        pop_str = f'prey8._sessions.pop("{agent_id}", None)'
        
        if pop_str not in preceding:
            # Find the start of the line containing this _get_session call
            line_start = content.rfind('\n', 0, abs_pos) + 1
            # Insert the pop line before this line
            pop_line = f'    prey8._sessions.pop("{agent_id}", None)\n'
            all_insertions.append((line_start, pop_line))

# Apply in reverse order
all_insertions.sort(key=lambda x: x[0], reverse=True)
for pos, text in all_insertions:
    content = content[:pos] + text + content[pos:]

if content != original:
    path.write_text(content, encoding='utf-8')
    added = len(all_insertions)
    print(f"Added {added} session isolation pops")
else:
    print("No changes needed")
