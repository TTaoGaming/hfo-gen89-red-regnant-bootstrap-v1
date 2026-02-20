#!/usr/bin/env python3
"""precommit_test_harness.py

Lightweight, non-destructive simulator of the `.githooks/pre-commit` gates.
Usage: run with file paths to simulate staged files. Returns exit code 0 if
all checks pass, non-zero otherwise. Prints diagnostic evidence for failures.
"""
import sys
import os
import re

SECRET_FILENAME_RE = re.compile(r"\.env$|\.hfo_secret|\.pem$|\.key$|password|api_key|secret_key", re.I)
CONTENT_SECRET_RE = re.compile(r"(BRAVE_API_KEY|TAVILY_API_KEY|GITHUB_PERSONAL_ACCESS_TOKEN|GITHUB_TOKEN|OPENAI_API_KEY|ANTHROPIC_API_KEY|HFO_SECRET|api[_-]?key|secret[_-]?key|access[_-]?token|Bearer [A-Za-z0-9_\-\.]+)\s*[=:]\s*['\"]?[A-Za-z0-9_\-\.]{16,}", re.I)
KEY_PATTERNS = re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----|-----BEGIN CERTIFICATE-----|PRIVATE KEY")

ALLOWED_ROOT = re.compile(r"^(AGENTS.md|\.env\.example|\.gitignore|\.gitattributes|\.githooks|\.github|\.vscode|hfo_gen89_pointers_blessed\.json|hfo_gen_89_hot_obsidian_forge|LICENSE|README\.md|\.git)$")

def check_root_cleanliness(path):
    # path is repo-relative
    if os.path.dirname(path) == "":
        base = os.path.basename(path)
        if not ALLOWED_ROOT.match(base):
            return False, f"ROOT VIOLATION: {path} is not allowed at repo root"
    return True, None

def check_secret_filename(path):
    if SECRET_FILENAME_RE.search(path):
        if path != ".env.example":
            return False, f"SECRET FILENAME MATCH: {path}"
    return True, None

def check_large_file(path):
    try:
        size = os.path.getsize(path)
        if size > 10 * 1024 * 1024:
            return False, f"LARGE FILE: {path} ({size} bytes) > 10MB"
    except Exception:
        # If missing, skip size check
        pass
    return True, None

def check_content_secrets(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            if CONTENT_SECRET_RE.search(content):
                return False, f"SECRET IN CONTENT: {path}"
            if KEY_PATTERNS.search(content):
                return False, f"PRIVATE KEY / CERT DETECTED IN: {path}"
    except Exception:
        pass
    return True, None

def check_medallion_boundary(path):
    if path.startswith("hfo_gen_89_hot_obsidian_forge/1_silver/") or path.startswith("hfo_gen_89_hot_obsidian_forge/2_gold/") or path.startswith("hfo_gen_89_hot_obsidian_forge/3_hyper_fractal_obsidian/"):
        return False, f"MEDALLION VIOLATION: {path} — direct write to non-bronze layer prohibited"
    return True, None

def main(paths):
    errors = []
    for p in paths:
        ok, msg = check_root_cleanliness(p)
        if not ok: errors.append(msg)
        ok, msg = check_secret_filename(p)
        if not ok: errors.append(msg)
        ok, msg = check_medallion_boundary(p)
        if not ok: errors.append(msg)
        ok, msg = check_large_file(p)
        if not ok: errors.append(msg)
        ok, msg = check_content_secrets(p)
        if not ok: errors.append(msg)

    if errors:
        print("PRE-COMMIT HARNESS: BLOCKED — the following issues were found:")
        for e in errors:
            print(" -", e)
        return 2
    print("PRE-COMMIT HARNESS: PASSED — no gate violations detected for given paths.")
    return 0

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: precommit_test_harness.py <path1> [path2 ...]")
        sys.exit(1)
    sys.exit(main(sys.argv[1:]))
