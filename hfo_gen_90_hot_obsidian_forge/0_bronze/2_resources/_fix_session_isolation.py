"""Add prey8._sessions.pop() isolation to all tests that set session state directly."""
import re
from pathlib import Path

path = Path('tests/test_prey8_mcp_server.py')
content = path.read_text(encoding='utf-8')
lines = content.split('\n')

result_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    result_lines.append(line)
    
    # Pattern: session = prey8._get_session("xxx")
    m = re.match(r'^    session = prey8\._get_session\("(\w+)"\)$', line)
    if m:
        agent_id = m.group(1)
        # Look back: do we already have a pop for this agent in the last few lines?
        recent_block = '\n'.join(result_lines[-5:])
        pop_str = f'prey8._sessions.pop("{agent_id}", None)'
        if pop_str not in recent_block:
            # Insert the pop BEFORE this line
            result_lines.pop()  # remove the session line
            result_lines.append(f'    prey8._sessions.pop("{agent_id}", None)')
            result_lines.append(line)
    
    i += 1

new_content = '\n'.join(result_lines)

if new_content != content:
    path.write_text(new_content, encoding='utf-8')
    pops_added = new_content.count('_sessions.pop') - content.count('_sessions.pop')
    print(f"Added {pops_added} session isolation pops")
else:
    print("No changes needed")
