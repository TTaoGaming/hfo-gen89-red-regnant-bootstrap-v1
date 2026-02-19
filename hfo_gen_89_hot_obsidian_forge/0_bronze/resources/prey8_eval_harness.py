#!/usr/bin/env python3
"""
prey8_eval_harness.py — Local LLM Eval via Ollama + PREY8 Gate Observation

Tests local Ollama models against HumanEval-style coding problems while
observing PREY8 fail-closed gate behavior. Two eval modes:

  Mode 1: RAW coding eval (HumanEval-style)
    - Send prompt, extract code, run tests, score pass@1
    - Baseline: how good is the model at coding?

  Mode 2: PREY8-gated eval  
    - Ask the model to fill in PREY8 gate fields for each problem
    - Score: can the model produce valid structured fields?
    - Observe: gate_blocked events, field quality

Results logged to SSOT as stigmergy events for traceability.

Usage:
  python prey8_eval_harness.py --model qwen2.5-coder:7b --mode raw
  python prey8_eval_harness.py --model qwen2.5-coder:7b --mode prey8
  python prey8_eval_harness.py --model all --mode raw
  python prey8_eval_harness.py --model all --mode both --limit 5

Design source: SSOT docs 129.317.128.12.4.263 + HumanEval (Chen et al. 2021)
"""

import argparse
import hashlib
import json
import os
import re
import secrets
import signal
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
TIMEOUT_GENERATE = 300  # seconds per generation (generous for large/slow models)
TIMEOUT_TEST = 10       # seconds per test execution
MAX_TOKENS = 2048

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for ancestor in [anchor] + list(anchor.parents):
            if (ancestor / "AGENTS.md").exists():
                return ancestor
    return Path.cwd()

HFO_ROOT = _find_root()
DB_PATH = HFO_ROOT / "hfo_gen_89_hot_obsidian_forge" / "2_gold" / "resources" / "hfo_gen89_ssot.sqlite"
GEN = os.environ.get("HFO_GENERATION", "89")

# ---------------------------------------------------------------------------
# HumanEval-Style Problems (embedded — no external dataset needed)
# 20 problems covering: strings, math, lists, dicts, recursion, edge cases
# ---------------------------------------------------------------------------

EVAL_PROBLEMS = [
    {
        "id": "HFE-001",
        "name": "has_close_elements",
        "prompt": '''def has_close_elements(numbers: list[float], threshold: float) -> bool:
    """Check if in given list of numbers, are any two numbers closer to each other than
    given threshold.
    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)
    False
    >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3)
    True
    """
''',
        "tests": [
            "assert has_close_elements([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.3) == True",
            "assert has_close_elements([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.05) == False",
            "assert has_close_elements([1.0, 2.0, 5.9, 4.0, 5.0], 0.95) == True",
            "assert has_close_elements([1.0, 2.0, 5.9, 4.0, 5.0], 0.8) == False",
            "assert has_close_elements([1.0, 2.0, 3.0, 4.0, 5.0], 2.0) == True",
            "assert has_close_elements([], 0.5) == False",
        ],
        "difficulty": "easy",
    },
    {
        "id": "HFE-002",
        "name": "separate_paren_groups",
        "prompt": '''def separate_paren_groups(paren_string: str) -> list[str]:
    """Input to this function is a string containing multiple groups of nested parentheses.
    Your goal is to separate those groups into separate strings and return the list of those.
    Separate groups are balanced (each open brace is properly closed) and not nested within each other.
    Ignore any spaces in the input string.
    >>> separate_paren_groups('( ) (( )) (( )( ))')
    ['()', '(())', '(()())']
    """
''',
        "tests": [
            "assert separate_paren_groups('(()()) ((())) () ((())()())') == ['(()())', '((()))', '()', '((())()())']",
            "assert separate_paren_groups('() (()) ((())) (((())))') == ['()', '(())', '((()))', '(((())))']",
            "assert separate_paren_groups('(()(())((())))') == ['(()(())((())))']",
            "assert separate_paren_groups('( ) (( )) (( )( ))') == ['()', '(())', '(()())']",
        ],
        "difficulty": "medium",
    },
    {
        "id": "HFE-003",
        "name": "truncate_number",
        "prompt": '''def truncate_number(number: float) -> float:
    """Given a positive floating point number, it can be decomposed into
    an integer part (largest integer smaller than given number) and decimals
    (leftover part always smaller than 1).
    Return the decimal part of the number.
    >>> truncate_number(3.5)
    0.5
    """
''',
        "tests": [
            "assert truncate_number(3.5) == 0.5",
            "assert abs(truncate_number(1.33) - 0.33) < 1e-6",
            "assert truncate_number(123.456) == 123.456 - 123",
        ],
        "difficulty": "easy",
    },
    {
        "id": "HFE-004",
        "name": "below_zero",
        "prompt": '''def below_zero(operations: list[int]) -> bool:
    """You're given a list of deposit and withdrawal operations on a bank account
    that starts with zero balance. Your task is to detect if at any point the
    balance of account falls below zero, and at that point function should
    return True. Otherwise it should return False.
    >>> below_zero([1, 2, 3])
    False
    >>> below_zero([1, 2, -4, 5])
    True
    """
''',
        "tests": [
            "assert below_zero([]) == False",
            "assert below_zero([1, 2, -3, 1, 2, -3]) == False",
            "assert below_zero([1, 2, -4, 5, 6]) == True",
            "assert below_zero([1, -1, 2, -2, 5, -5, 4, -4]) == False",
            "assert below_zero([1, -1, 2, -2, 5, -5, 4, -5]) == True",
        ],
        "difficulty": "easy",
    },
    {
        "id": "HFE-005",
        "name": "mean_absolute_deviation",
        "prompt": '''def mean_absolute_deviation(numbers: list[float]) -> float:
    """For a given list of input numbers, calculate Mean Absolute Deviation
    around the mean of this dataset.
    Mean Absolute Deviation is the average absolute difference between each
    element and a centerpoint (mean in this case):
    MAD = average | x - x_mean |
    >>> mean_absolute_deviation([1.0, 2.0, 3.0, 4.0])
    1.0
    """
''',
        "tests": [
            "assert abs(mean_absolute_deviation([1.0, 2.0, 3.0, 4.0]) - 1.0) < 1e-6",
            "assert abs(mean_absolute_deviation([1.0, 2.0, 3.0, 4.0, 5.0]) - 1.2) < 1e-6",
            "assert abs(mean_absolute_deviation([1.0, 1.0, 1.0, 1.0]) - 0.0) < 1e-6",
        ],
        "difficulty": "easy",
    },
    {
        "id": "HFE-006",
        "name": "intersperse",
        "prompt": '''def intersperse(numbers: list[int], delimiter: int) -> list[int]:
    """Insert a number 'delimiter' between every two consecutive elements of input list `numbers`.
    >>> intersperse([], 4)
    []
    >>> intersperse([1, 2, 3], 4)
    [1, 4, 2, 4, 3]
    """
''',
        "tests": [
            "assert intersperse([], 7) == []",
            "assert intersperse([5, 6, 3, 2], 8) == [5, 8, 6, 8, 3, 8, 2]",
            "assert intersperse([2, 2, 2], 2) == [2, 2, 2, 2, 2]",
        ],
        "difficulty": "easy",
    },
    {
        "id": "HFE-007",
        "name": "parse_nested_parens",
        "prompt": '''def parse_nested_parens(paren_string: str) -> list[int]:
    """Input to this function is a string represented multiple groups for nested parentheses separated by spaces.
    For each of the group, output the deepest level of nesting of parentheses.
    E.g. (()()) has maximum two levels of nesting while ((())) has three.
    >>> parse_nested_parens('(()()) ((())) () ((())()())')
    [2, 3, 1, 3]
    """
''',
        "tests": [
            "assert parse_nested_parens('(()()) ((())) () ((())()())') == [2, 3, 1, 3]",
            "assert parse_nested_parens('() (()) ((())) (((())))') == [1, 2, 3, 4]",
            "assert parse_nested_parens('(()(())((())))') == [4]",
        ],
        "difficulty": "medium",
    },
    {
        "id": "HFE-008",
        "name": "filter_by_substring",
        "prompt": '''def filter_by_substring(strings: list[str], substring: str) -> list[str]:
    """Filter an input list of strings only for ones that contain given substring.
    >>> filter_by_substring([], 'a')
    []
    >>> filter_by_substring(['abc', 'bacd', 'cde', 'array'], 'a')
    ['abc', 'bacd', 'array']
    """
''',
        "tests": [
            "assert filter_by_substring([], 'john') == []",
            "assert filter_by_substring(['xxx', 'asd', 'xxy', 'john doe', 'xxxAAA', 'xxx'], 'xxx') == ['xxx', 'xxxAAA', 'xxx']",
            "assert filter_by_substring(['xxx', 'asd', 'aaadbd', 'abd', 'john doe', 'xxxAAA', 'xxx'], 'john') == ['john doe']",
        ],
        "difficulty": "easy",
    },
    {
        "id": "HFE-009",
        "name": "sum_product",
        "prompt": '''def sum_product(numbers: list[int]) -> tuple[int, int]:
    """For a given list of integers, return a tuple consisting of a sum and a product of all the integers in a list.
    Empty sum should be equal to 0 and empty product should be equal to 1.
    >>> sum_product([])
    (0, 1)
    >>> sum_product([1, 2, 3, 4])
    (10, 24)
    """
''',
        "tests": [
            "assert sum_product([]) == (0, 1)",
            "assert sum_product([1, 1, 1]) == (3, 1)",
            "assert sum_product([100, 0]) == (100, 0)",
            "assert sum_product([3, 5, 7]) == (15, 105)",
        ],
        "difficulty": "easy",
    },
    {
        "id": "HFE-010",
        "name": "rolling_max",
        "prompt": '''def rolling_max(numbers: list[int]) -> list[int]:
    """From a given list of integers, generate a list of rolling maximum element found until given moment
    in the sequence.
    >>> rolling_max([1, 2, 3, 2, 3, 4, 2])
    [1, 2, 3, 3, 3, 4, 4]
    """
''',
        "tests": [
            "assert rolling_max([]) == []",
            "assert rolling_max([1, 2, 3, 2, 3, 4, 2]) == [1, 2, 3, 3, 3, 4, 4]",
            "assert rolling_max([1, 4, 3, 2, 5]) == [1, 4, 4, 4, 5]",
            "assert rolling_max([5, 4, 3, 2, 1]) == [5, 5, 5, 5, 5]",
        ],
        "difficulty": "easy",
    },
    {
        "id": "HFE-011",
        "name": "is_palindrome",
        "prompt": '''def is_palindrome(string: str) -> bool:
    """Check if given string is a palindrome.
    >>> is_palindrome('')
    True
    >>> is_palindrome('aba')
    True
    >>> is_palindrome('aaaaa')
    True
    >>> is_palindrome('zbcd')
    False
    """
''',
        "tests": [
            "assert is_palindrome('') == True",
            "assert is_palindrome('aba') == True",
            "assert is_palindrome('aaaaa') == True",
            "assert is_palindrome('zbcd') == False",
            "assert is_palindrome('xywyx') == True",
            "assert is_palindrome('xywyz') == False",
        ],
        "difficulty": "easy",
    },
    {
        "id": "HFE-012",
        "name": "remove_duplicates",
        "prompt": '''def remove_duplicates(numbers: list[int]) -> list[int]:
    """From a list of integers, remove all elements that occur more than once.
    Keep order of elements left the same as in the input.
    >>> remove_duplicates([1, 2, 3, 2, 4])
    [1, 3, 4]
    """
''',
        "tests": [
            "assert remove_duplicates([]) == []",
            "assert remove_duplicates([1, 2, 3, 2, 4]) == [1, 3, 4]",
            "assert remove_duplicates([1, 2, 3, 4]) == [1, 2, 3, 4]",
            "assert remove_duplicates([1, 1, 1, 1]) == []",
        ],
        "difficulty": "easy",
    },
    {
        "id": "HFE-013",
        "name": "flip_case",
        "prompt": '''def flip_case(string: str) -> str:
    """For a given string, flip lowercase characters to uppercase and uppercase to lowercase.
    >>> flip_case('Hello')
    'hELLO'
    """
''',
        "tests": [
            "assert flip_case('') == ''",
            "assert flip_case('Hello!') == 'hELLO!'",
            "assert flip_case('These violent delights have violent ends') == 'tHESE VIOLENT DELIGHTS HAVE VIOLENT ENDS'",
        ],
        "difficulty": "easy",
    },
    {
        "id": "HFE-014",
        "name": "concatenate",
        "prompt": '''def concatenate(strings: list[str]) -> str:
    """Concatenate list of strings into a single string.
    >>> concatenate([])
    ''
    >>> concatenate(['a', 'b', 'c'])
    'abc'
    """
''',
        "tests": [
            "assert concatenate([]) == ''",
            "assert concatenate(['x', 'y', 'z']) == 'xyz'",
            "assert concatenate(['x', 'y', 'z', 'w', 'k']) == 'xyzwk'",
        ],
        "difficulty": "easy",
    },
    {
        "id": "HFE-015",
        "name": "filter_by_prefix",
        "prompt": '''def filter_by_prefix(strings: list[str], prefix: str) -> list[str]:
    """Filter an input list of strings only for ones that start with a given prefix.
    >>> filter_by_prefix([], 'a')
    []
    >>> filter_by_prefix(['abc', 'bcd', 'cde', 'array'], 'a')
    ['abc', 'array']
    """
''',
        "tests": [
            "assert filter_by_prefix([], 'john') == []",
            "assert filter_by_prefix(['xxx', 'asd', 'xxy', 'john doe', 'xxxAAA', 'xxx'], 'xxx') == ['xxx', 'xxxAAA', 'xxx']",
        ],
        "difficulty": "easy",
    },
    {
        "id": "HFE-016",
        "name": "get_positive",
        "prompt": '''def get_positive(l: list[int]) -> list[int]:
    """Return only positive numbers in the list.
    >>> get_positive([-1, 2, -4, 5, 6])
    [2, 5, 6]
    >>> get_positive([5, 3, -5, 2, -3, 3, 9, 0, 123, 1, -10])
    [5, 3, 2, 3, 9, 123, 1]
    """
''',
        "tests": [
            "assert get_positive([-1, -2, 4, 5, 6]) == [4, 5, 6]",
            "assert get_positive([5, 3, -5, 2, 3, 3, 9, 0, 123, 1, -10]) == [5, 3, 2, 3, 3, 9, 123, 1]",
            "assert get_positive([-1, -2]) == []",
            "assert get_positive([]) == []",
        ],
        "difficulty": "easy",
    },
    {
        "id": "HFE-017",
        "name": "is_sorted",
        "prompt": '''def is_sorted(lst: list[int]) -> bool:
    """Given a list of numbers, return whether or not they are sorted
    in ascending order. If list has more than 1 duplicate of the same
    number, return False. Assume no negative numbers and only integers.
    >>> is_sorted([5])
    True
    >>> is_sorted([1, 2, 3, 4, 5])
    True
    >>> is_sorted([1, 3, 2, 4, 5])
    False
    >>> is_sorted([1, 2, 3, 4, 5, 6, 7])
    True
    >>> is_sorted([1, 2, 2, 3, 3, 4])
    True
    >>> is_sorted([1, 2, 2, 2, 3, 4])
    False
    """
''',
        "tests": [
            "assert is_sorted([5]) == True",
            "assert is_sorted([1, 2, 3, 4, 5]) == True",
            "assert is_sorted([1, 3, 2, 4, 5]) == False",
            "assert is_sorted([1, 2, 3, 4, 5, 6, 7]) == True",
            "assert is_sorted([1, 2, 2, 3, 3, 4]) == True",
            "assert is_sorted([1, 2, 2, 2, 3, 4]) == False",
            "assert is_sorted([]) == True",
        ],
        "difficulty": "medium",
    },
    {
        "id": "HFE-018",
        "name": "unique_digits",
        "prompt": '''def unique_digits(x: list[int]) -> list[int]:
    """Given a list of positive integers x. return a sorted list of all
    elements that haven't any even digit.
    Note: Returned list should be sorted in increasing order.
    >>> unique_digits([15, 33, 1422, 1])
    [1, 15, 33]
    >>> unique_digits([152, 323, 1422, 10])
    []
    """
''',
        "tests": [
            "assert unique_digits([15, 33, 1422, 1]) == [1, 15, 33]",
            "assert unique_digits([152, 323, 1422, 10]) == []",
            "assert unique_digits([12345, 2033, 111, 151]) == [111, 151]",
            "assert unique_digits([135, 103, 31]) == [31, 135]",
        ],
        "difficulty": "medium",
    },
    {
        "id": "HFE-019",
        "name": "by_length",
        "prompt": '''def by_length(arr: list[int]) -> list[str]:
    """Given an array of integers, sort the integers that are between 1 and 9 inclusive,
    reverse the resulting array, and then replace each digit by its corresponding name from
    "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine".
    >>> by_length([2, 1, 1, 4, 5, 8, 2, 3])
    ["Eight", "Five", "Four", "Three", "Two", "Two", "One", "One"]
    >>> by_length([])
    []
    >>> by_length([1, -1, 55])
    ["One"]
    """
''',
        "tests": [
            'assert by_length([2, 1, 1, 4, 5, 8, 2, 3]) == ["Eight", "Five", "Four", "Three", "Two", "Two", "One", "One"]',
            "assert by_length([]) == []",
            'assert by_length([1, -1, 55]) == ["One"]',
            'assert by_length([1, 2, 3]) == ["Three", "Two", "One"]',
        ],
        "difficulty": "medium",
    },
    {
        "id": "HFE-020",
        "name": "f_sequence",
        "prompt": '''def f(n: int) -> list[int]:
    """Implement the function f that takes n as a parameter,
    and returns a list of size n, such that the value of the element at index i is
    the factorial of i if i is even or the sum of numbers from 1 to i otherwise.
    i starts from 1. the factorial of i is the multiplication of the numbers from 1 to i (1 * 2 * ... * i).
    >>> f(5)
    [1, 2, 6, 24, 15]
    """
''',
        "tests": [
            "assert f(5) == [1, 2, 6, 24, 15]",
            "assert f(7) == [1, 2, 6, 24, 15, 720, 28]",
            "assert f(1) == [1]",
            "assert f(3) == [1, 2, 6]",
        ],
        "difficulty": "medium",
    },
]


# ---------------------------------------------------------------------------
# SSOT Logging
# ---------------------------------------------------------------------------

def _write_eval_event(event_type: str, data: dict) -> int:
    """Write an eval event to SSOT stigmergy_events."""
    if not DB_PATH.exists():
        return -1
    ts = datetime.now(timezone.utc).isoformat()
    event = {
        "specversion": "1.0",
        "id": secrets.token_hex(16),
        "type": event_type,
        "source": f"hfo_prey8_eval_gen{GEN}",
        "subject": "prey8-eval",
        "time": ts,
        "timestamp": ts,
        "datacontenttype": "application/json",
        "data": data,
    }
    c_hash = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute(
            """INSERT OR IGNORE INTO stigmergy_events
               (event_type, timestamp, subject, source, data_json, content_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event["type"], ts, "prey8-eval", event["source"],
             json.dumps(event), c_hash),
        )
        conn.commit()
        row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return row_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Ollama API
# ---------------------------------------------------------------------------

def ollama_generate(model: str, prompt: str, system: str = "") -> dict:
    """Call Ollama generate API. Returns {response, total_duration, eval_count}."""
    url = f"{OLLAMA_BASE}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": MAX_TOKENS,
            "temperature": 0.0,  # deterministic for eval
        },
    }
    if system:
        payload["system"] = system

    try:
        with httpx.Client(timeout=TIMEOUT_GENERATE) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            return {
                "response": data.get("response", ""),
                "total_duration_ms": data.get("total_duration", 0) / 1e6,
                "eval_count": data.get("eval_count", 0),
                "eval_duration_ms": data.get("eval_duration", 0) / 1e6,
                "model": data.get("model", model),
                "done": data.get("done", False),
            }
    except Exception as e:
        return {"response": "", "error": str(e), "model": model, "done": False}


def list_models() -> list[str]:
    """Get list of available Ollama models."""
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Code Extraction & Execution
# ---------------------------------------------------------------------------

def extract_code(response: str, func_name: str) -> str:
    """Extract Python function from LLM response."""
    # Strip <think>...</think> blocks from reasoning models
    cleaned = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
    if not cleaned:
        cleaned = response

    # Try to find code in markdown code blocks
    code_blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", cleaned, re.DOTALL)

    for block in code_blocks:
        if func_name in block:
            return block.strip()

    # Try to find a def statement directly
    lines = cleaned.split("\n")
    in_func = False
    func_lines = []
    indent_level = None

    for line in lines:
        if f"def {func_name}" in line:
            in_func = True
            indent_level = len(line) - len(line.lstrip())
            func_lines = [line[indent_level:] if indent_level > 0 else line]
            continue
        if in_func:
            if line.strip() == "":
                func_lines.append("")
                continue
            current_indent = len(line) - len(line.lstrip())
            if current_indent > indent_level or line.strip() == "":
                func_lines.append(line[indent_level:] if indent_level > 0 else line)
            else:
                # Dedent — function ended
                break

    if func_lines:
        return "\n".join(func_lines).strip()

    # Last resort: return the cleaned response hoping it's just code
    return cleaned.strip()


def run_tests(code: str, tests: list[str], func_name: str) -> dict:
    """Execute extracted code + tests in a subprocess. Returns pass/fail details."""
    test_code = code + "\n\n" + "\n".join(tests)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(test_code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True, text=True,
            timeout=TIMEOUT_TEST,
        )
        passed = result.returncode == 0
        return {
            "passed": passed,
            "returncode": result.returncode,
            "stdout": result.stdout[:500],
            "stderr": result.stderr[:500],
            "tests_count": len(tests),
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "TIMEOUT",
            "tests_count": len(tests),
        }
    except Exception as e:
        return {
            "passed": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e)[:500],
            "tests_count": len(tests),
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# PREY8 Gate Field Extraction (Mode 2)
# ---------------------------------------------------------------------------

PREY8_SYSTEM_PROMPT = """You are a coding agent that operates under the PREY8 protocol.
For EVERY coding task, you must produce structured gate fields alongside your solution.

You MUST output a JSON object with these exact keys:

{
    "observations": "What you observed about the problem (comma-separated)",
    "memory_refs": "References to concepts you drew on (comma-separated)",
    "stigmergy_digest": "Key patterns from prior problems",
    "shared_data_refs": "Cross-references between this problem and others",
    "navigation_intent": "Your strategic approach",
    "meadows_level": <integer 1-12>,
    "meadows_justification": "Why this leverage level",
    "sequential_plan": "Ordered steps (comma-separated)",
    "sbe_given": "Given <precondition>",
    "sbe_when": "When <action>",
    "sbe_then": "Then <postcondition>",
    "artifacts": "What you produce",
    "p4_adversarial_check": "Edge cases and failure modes checked",
    "code": "<your Python function implementation>"
}

CRITICAL: Output ONLY the JSON object. No markdown, no explanation outside the JSON.
The "code" field must contain a complete Python function that can be executed directly.
"""

def extract_prey8_fields(response: str) -> dict:
    """Try to parse PREY8 structured fields from model response."""
    # Try direct JSON parse
    try:
        # Find JSON object in response
        match = re.search(r"\{[\s\S]*\}", response)
        if match:
            return json.loads(match.group())
    except json.JSONDecodeError:
        pass

    # Try to extract fields manually
    fields = {}
    for key in [
        "observations", "memory_refs", "stigmergy_digest",
        "shared_data_refs", "navigation_intent", "meadows_level",
        "meadows_justification", "sequential_plan",
        "sbe_given", "sbe_when", "sbe_then",
        "artifacts", "p4_adversarial_check", "code",
    ]:
        match = re.search(rf'"{key}"\s*:\s*"([^"]*)"', response)
        if match:
            fields[key] = match.group(1)
        elif key == "meadows_level":
            match = re.search(rf'"{key}"\s*:\s*(\d+)', response)
            if match:
                fields[key] = int(match.group(1))

    return fields


def validate_prey8_fields(fields: dict) -> dict:
    """Check which PREY8 gate fields are present and non-empty."""
    perceive_fields = ["observations", "memory_refs", "stigmergy_digest"]
    react_fields = ["shared_data_refs", "navigation_intent", "meadows_level",
                     "meadows_justification", "sequential_plan"]
    execute_fields = ["sbe_given", "sbe_when", "sbe_then", "artifacts",
                      "p4_adversarial_check"]

    def check(field_list, gate_name):
        present = 0
        missing = []
        for f in field_list:
            val = fields.get(f)
            if val and str(val).strip():
                present += 1
            else:
                missing.append(f)
        return {
            "gate": gate_name,
            "total": len(field_list),
            "present": present,
            "missing": missing,
            "passed": present == len(field_list),
        }

    return {
        "perceive_gate": check(perceive_fields, "PERCEIVE (P0+P6)"),
        "react_gate": check(react_fields, "REACT (P1+P7)"),
        "execute_gate": check(execute_fields, "EXECUTE (P2+P4)"),
        "has_code": bool(fields.get("code", "").strip()),
        "meadows_level": fields.get("meadows_level"),
        "total_fields_present": sum(
            1 for k, v in fields.items()
            if v and str(v).strip() and k != "code"
        ),
        "total_fields_expected": len(perceive_fields) + len(react_fields) + len(execute_fields),
    }


# ---------------------------------------------------------------------------
# Eval Runner
# ---------------------------------------------------------------------------

def run_raw_eval(model: str, problems: list[dict], verbose: bool = True) -> dict:
    """Run HumanEval-style raw coding eval."""
    results = []
    passed = 0
    total = len(problems)

    print(f"\n{'='*60}")
    print(f"  RAW CODING EVAL: {model}")
    print(f"  Problems: {total}")
    print(f"{'='*60}")

    for i, problem in enumerate(problems):
        pid = problem["id"]
        name = problem["name"]
        if verbose:
            print(f"\n  [{i+1}/{total}] {pid} {name} ({problem['difficulty']})...", end=" ", flush=True)

        try:
            t0 = time.time()
            gen = ollama_generate(
                model,
                f"Complete this Python function. Output ONLY the complete function, no explanation.\n\n{problem['prompt']}",
                system="You are a Python coding assistant. Output only the complete Python function implementation. No explanations, no markdown.",
            )
            gen_time = time.time() - t0

            if gen.get("error"):
                if verbose:
                    print(f"ERROR: {gen['error'][:80]}")
                results.append({
                    "id": pid, "name": name, "passed": False,
                    "error": gen["error"], "gen_time": gen_time,
                })
                continue

            code = extract_code(gen["response"], name)
            test_result = run_tests(code, problem["tests"], name)

            if test_result["passed"]:
                passed += 1
                if verbose:
                    print(f"PASS ({gen_time:.1f}s, {gen.get('eval_count', 0)} tokens)")
            else:
                if verbose:
                    err = test_result["stderr"][:120].replace("\n", " ")
                    print(f"FAIL ({gen_time:.1f}s) — {err}")

            results.append({
                "id": pid,
                "name": name,
                "passed": test_result["passed"],
                "gen_time_s": round(gen_time, 2),
                "eval_tokens": gen.get("eval_count", 0),
                "eval_duration_ms": gen.get("eval_duration_ms", 0),
                "tests_count": test_result["tests_count"],
                "error": test_result.get("stderr", "")[:200] if not test_result["passed"] else "",
            })
        except (Exception, KeyboardInterrupt) as exc:
            if verbose:
                print(f"CRASH: {type(exc).__name__}: {exc}")
            results.append({
                "id": pid, "name": name, "passed": False,
                "error": str(exc)[:200], "gen_time": time.time() - t0,
            })

    score = passed / total if total > 0 else 0
    print(f"\n{'─'*60}")
    print(f"  SCORE: {passed}/{total} = {score:.1%} pass@1")
    print(f"{'─'*60}")

    summary = {
        "model": model,
        "mode": "raw",
        "total": total,
        "passed": passed,
        "score": round(score, 4),
        "results": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Log to SSOT
    _write_eval_event(f"hfo.gen{GEN}.eval.raw_coding", summary)

    return summary


def run_prey8_eval(model: str, problems: list[dict], verbose: bool = True) -> dict:
    """Run PREY8-gated eval — test if model can produce structured gate fields."""
    results = []
    code_passed = 0
    gates_passed = 0
    total = len(problems)

    print(f"\n{'='*60}")
    print(f"  PREY8 GATE EVAL: {model}")
    print(f"  Problems: {total}")
    print(f"{'='*60}")

    for i, problem in enumerate(problems):
        pid = problem["id"]
        name = problem["name"]
        if verbose:
            print(f"\n  [{i+1}/{total}] {pid} {name} ({problem['difficulty']})...")

        try:
            t0 = time.time()
            gen = ollama_generate(
                model,
                f"Solve this coding problem with full PREY8 gate fields.\n\nProblem:\n{problem['prompt']}",
                system=PREY8_SYSTEM_PROMPT,
            )
            gen_time = time.time() - t0

            if gen.get("error"):
                if verbose:
                    print(f"    ERROR: {gen['error'][:80]}")
                results.append({
                    "id": pid, "name": name, "code_passed": False,
                    "gate_validation": {"perceive_gate": {"passed": False, "present": 0, "total": 3},
                                         "react_gate": {"passed": False, "present": 0, "total": 5},
                                         "execute_gate": {"passed": False, "present": 0, "total": 5},
                                         "total_fields_present": 0, "total_fields_expected": 13},
                    "error": gen["error"], "gen_time": gen_time,
                })
                continue

            # Extract PREY8 fields
            fields = extract_prey8_fields(gen["response"])
            gate_val = validate_prey8_fields(fields)

            # Check code
            code = fields.get("code", "")
            if not code:
                code = extract_code(gen["response"], name)

            test_result = run_tests(code, problem["tests"], name)

            if test_result["passed"]:
                code_passed += 1

            all_gates = (
                gate_val["perceive_gate"]["passed"]
                and gate_val["react_gate"]["passed"]
                and gate_val["execute_gate"]["passed"]
            )
            if all_gates:
                gates_passed += 1

            if verbose:
                code_status = "PASS" if test_result["passed"] else "FAIL"
                gate_status = "ALL GATES" if all_gates else "BLOCKED"
                p_g = gate_val["perceive_gate"]
                r_g = gate_val["react_gate"]
                e_g = gate_val["execute_gate"]
                print(f"    Code: {code_status} | Gates: {gate_status} "
                      f"(P:{p_g['present']}/{p_g['total']} "
                      f"R:{r_g['present']}/{r_g['total']} "
                      f"E:{e_g['present']}/{e_g['total']}) "
                      f"| Meadows L{gate_val.get('meadows_level', '?')} "
                      f"| {gen_time:.1f}s")

            results.append({
                "id": pid,
                "name": name,
                "code_passed": test_result["passed"],
                "all_gates_passed": all_gates,
                "gate_validation": gate_val,
                "meadows_level": gate_val.get("meadows_level"),
                "gen_time_s": round(gen_time, 2),
                "eval_tokens": gen.get("eval_count", 0),
            })
        except (Exception, KeyboardInterrupt) as exc:
            if verbose:
                print(f"    CRASH: {type(exc).__name__}: {exc}")
            results.append({
                "id": pid, "name": name, "code_passed": False,
                "gate_validation": {"perceive_gate": {"passed": False, "present": 0, "total": 3},
                                     "react_gate": {"passed": False, "present": 0, "total": 5},
                                     "execute_gate": {"passed": False, "present": 0, "total": 5},
                                     "total_fields_present": 0, "total_fields_expected": 13},
                "error": str(exc)[:200], "gen_time": time.time() - t0,
            })

    code_score = code_passed / total if total > 0 else 0
    gate_score = gates_passed / total if total > 0 else 0
    print(f"\n{'─'*60}")
    print(f"  CODE SCORE:  {code_passed}/{total} = {code_score:.1%} pass@1")
    print(f"  GATE SCORE:  {gates_passed}/{total} = {gate_score:.1%} all-gates-passed")
    print(f"  FIELDS AVG:  {sum(r.get('gate_validation', {}).get('total_fields_present', 0) for r in results) / max(total, 1):.1f}"
          f"/{results[0]['gate_validation']['total_fields_expected'] if results else 13}")
    print(f"{'─'*60}")

    summary = {
        "model": model,
        "mode": "prey8",
        "total": total,
        "code_passed": code_passed,
        "code_score": round(code_score, 4),
        "gates_passed": gates_passed,
        "gate_score": round(gate_score, 4),
        "results": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Log to SSOT
    _write_eval_event(f"hfo.gen{GEN}.eval.prey8_gated", summary)

    return summary


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="PREY8 Eval Harness — Test local Ollama models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python prey8_eval_harness.py --model qwen2.5-coder:7b --mode raw
              python prey8_eval_harness.py --model qwen2.5-coder:7b --mode prey8
              python prey8_eval_harness.py --model all --mode raw --limit 5
              python prey8_eval_harness.py --model all --mode both
        """),
    )
    parser.add_argument("--model", default="qwen2.5-coder:7b",
                        help="Model name or 'all' for all available models")
    parser.add_argument("--mode", choices=["raw", "prey8", "both"], default="raw",
                        help="Eval mode: raw (coding only), prey8 (gate fields), both")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of problems (0 = all 20)")
    parser.add_argument("--verbose", action="store_true", default=True)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.quiet:
        args.verbose = False

    # Select problems
    problems = EVAL_PROBLEMS
    if args.limit > 0:
        problems = problems[:args.limit]

    # Select models
    if args.model == "all":
        models = list_models()
        if not models:
            print("ERROR: Cannot reach Ollama API or no models found.")
            sys.exit(1)
        print(f"Found {len(models)} models: {', '.join(models)}")
    else:
        models = [args.model]

    all_summaries = []

    for model in models:
        if args.mode in ("raw", "both"):
            s = run_raw_eval(model, problems, verbose=args.verbose)
            all_summaries.append(s)

        if args.mode in ("prey8", "both"):
            s = run_prey8_eval(model, problems, verbose=args.verbose)
            all_summaries.append(s)

    # Print comparison table if multiple models
    if len(all_summaries) > 1:
        print(f"\n{'='*70}")
        print(f"  COMPARISON TABLE")
        print(f"{'='*70}")
        print(f"  {'Model':<25} {'Mode':<8} {'Score':>8} {'Gate':>8}")
        print(f"  {'─'*25} {'─'*8} {'─'*8} {'─'*8}")
        for s in all_summaries:
            mode = s["mode"]
            if mode == "raw":
                print(f"  {s['model']:<25} {mode:<8} {s['score']:>7.1%} {'—':>8}")
            else:
                print(f"  {s['model']:<25} {mode:<8} {s['code_score']:>7.1%} {s['gate_score']:>7.1%}")
        print(f"{'='*70}")

    # Write final summary to SSOT
    _write_eval_event(f"hfo.gen{GEN}.eval.run_complete", {
        "models_tested": len(models),
        "problems_per_model": len(problems),
        "mode": args.mode,
        "summaries": [
            {
                "model": s["model"], "mode": s["mode"],
                "score": s.get("score", s.get("code_score")),
                "gate_score": s.get("gate_score"),
            }
            for s in all_summaries
        ],
    })


if __name__ == "__main__":
    main()
