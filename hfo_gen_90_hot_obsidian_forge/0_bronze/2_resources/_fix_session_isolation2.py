"""Add session isolation to all tests that call prey8._get_session directly.

For each test function, find all agent IDs used via _get_session, and add
_sessions.pop() calls at the start of the function BEFORE the first get_session.
"""
import re
from pathlib import Path

path = Path('tests/test_prey8_mcp_server.py')
content = path.read_text(encoding='utf-8')
original = content

# Split into test function blocks
# Find all test function definitions and their body ranges
func_pattern = re.compile(r'^def (test_\w+)\(', re.MULTILINE)
matches = list(func_pattern.finditer(content))

# Process in reverse order so offsets stay valid after insertions
insertions = []  # (position, text_to_insert)

for j, match in enumerate(matches):
    func_start = match.start()
    func_end = matches[j+1].start() if j+1 < len(matches) else len(content)
    func_body = content[func_start:func_end]
    
    # Find all agent_ids used in this function
    agent_ids = re.findall(r'prey8\._get_session\("(\w+)"\)', func_body)
    if not agent_ids:
        continue
    
    unique_agents = list(dict.fromkeys(agent_ids))  # preserve order, dedupe
    
    # Find the colon at end of function def line (end of signature)
    colon_pos = content.find(':\n', func_start)
    insert_pos = colon_pos + 2  # After ':\n'
    
    # Skip the docstring/first lines that are blank
    # Find first non-blank line in the function body
    body_start = colon_pos + 2
    body_chunk = content[body_start:body_start + 400]
    
    # Check if we already have a pop for each agent
    pops_needed = []
    for aid in unique_agents:
        pop_str = f'prey8._sessions.pop("{aid}", None)'
        # Check if already in the first 300 chars of the function body
        already_has = pop_str in content[body_start:body_start + 300]
        if not already_has:
            pops_needed.append(pop_str)
    
    if pops_needed:
        # Find the position to insert: after the opening of the function body
        # Skip past any mocker.patch lines that come before session setup
        # Actually, insert right after the function def line
        pop_code = '\n'.join(f'    {p}' for p in pops_needed) + '\n'
        insertions.append((insert_pos, pop_code))

# Apply insertions in reverse order
insertions.sort(key=lambda x: x[0], reverse=True)
for pos, text in insertions:
    content = content[:pos] + text + content[pos:]

if content != original:
    path.write_text(content, encoding='utf-8')
    added = content.count('_sessions.pop') - original.count('_sessions.pop')
    print(f"Added {added} session pops total")
else:
    print("No changes needed")
