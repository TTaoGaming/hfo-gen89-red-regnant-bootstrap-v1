"""Fix ruff/mypy issues in tests/test_prey8_mcp_server.py."""
import re

path = 'tests/test_prey8_mcp_server.py'
with open(path, encoding='utf-8') as f:
    content = f.read()

original = content

# 1. Remove 'import pytest' line (unused)
content = re.sub(r'^import pytest\n', '', content, flags=re.MULTILINE)

# 2. Fix E712: some_expr == False -> not some_expr
content = re.sub(r'assert (prey8\._\w+\([^)]*\)) == False', r'assert not \1', content)
# Fix E712: some_expr == True -> just some_expr
content = re.sub(r'assert (prey8\._\w+\([^)]*\)) == True', r'assert \1', content)
# Fix gate_receipt passed == True
content = content.replace(
    'assert result["gate_receipt"]["passed"] == True',
    'assert result["gate_receipt"]["passed"]'
)

# 3. Add # type: ignore to import
content = content.replace(
    'import hfo_prey8_mcp_server as prey8\n',
    'import hfo_prey8_mcp_server as prey8  # type: ignore[import-not-found]\n'
)

# 4. Add -> None to zero-arg test functions
content = re.sub(r'def (test_\w+)\(\):', r'def \1() -> None:', content)

# 5. Add -> None to test functions with mocker only
content = re.sub(r'def (test_\w+)\(mocker\):', r'def \1(mocker: object) -> None:', content)

# 6. Add -> None to test functions with one non-mocker arg
content = re.sub(r'def (test_\w+)\(prey8_session\):', r'def \1(prey8_session: object) -> None:', content)

# 7. Multi-arg test functions: (mocker, something) -> add -> None
content = re.sub(
    r'def (test_\w+)\(mocker, (\w+)\):',
    r'def \1(mocker: object, \2: object) -> None:',
    content
)

# 8. Fixture functions - add correct return annotations
# @pytest.fixture\ndef name():  ->  \ndef name() -> dict / generator etc
# For fixtures that just yield or return None
content = re.sub(r'def (prey8_session)\(\):', r'def \1() -> object:', content)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

# Report
changed = original != content
remaining_e712 = len(re.findall(r'== (?:True|False)', content))
has_pytest_import = 'import pytest\n' in content
print(f"Changed: {changed}")
print(f"Remaining == True/False: {remaining_e712}")
print(f"Has bare 'import pytest': {has_pytest_import}")
print("Done")
