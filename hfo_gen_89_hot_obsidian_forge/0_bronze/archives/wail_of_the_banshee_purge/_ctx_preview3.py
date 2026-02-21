"""Preview what the new BLUF+snippet assemble_context produces for the obsidian_spider query."""
import sqlite3, re, sys, os

sys.path.insert(0, r"c:\hfoDev\hfo_gen_89_hot_obsidian_forge\0_bronze\resources")
from hfo_shodh_query import assemble_context

_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")  # control chars except \t \n
_REPEAT_RE = re.compile(r"(\S{1,40}[\s\W]*)\1{6,}")  # repeating token
_EMOJI_RE = re.compile(r"[\U00010000-\U0010ffff\U0001F600-\U0001F64F\U0001F300-\U0001F5FF]", flags=re.UNICODE)

def _sanitize(text: str) -> str:
    text = _CTRL_RE.sub("", text)
    text = _EMOJI_RE.sub("", text)
    text = _REPEAT_RE.sub(r"\1[...truncated...]", text)
    return text

DB = r"c:\hfoDev\hfo_gen_89_hot_obsidian_forge\2_gold\resources\hfo_gen89_ssot.sqlite"
conn = sqlite3.connect(DB)

# Simulate what run_query returns for the obsidian_spider question (top docs)
results = [
    {"doc_id": 190, "title": "Eightfold OBSIDIAN_SPIDER", "port": None, "score": 0.5},
    {"doc_id": 276, "title": "P7_OBSIDIAN_SPIDER_SECRETS", "port": "P7",  "score": 0.5},
    {"doc_id": 249, "title": "Obsidian Spider Origin", "port": None,       "score": 0.5},
    {"doc_id": 7877, "title": "Port 7 Spider Sovereign",  "port": "P7",   "score": 0.5},
    {"doc_id": 84,  "title": "Legendary Commanders",      "port": None,   "score": 0.12},
]

ctx = assemble_context(conn, results, max_chars=6000)
san = _sanitize(ctx)
trimmed = san[:1200] + ("..." if len(san) > 1200 else "")

print(f"Assembled len: {len(san)}, trimmed to: 1200")
print("=" * 60)
print(trimmed)
print("=" * 60)

question = "who is controlling the hfo swarm on a higher dimensional manifold/sphere?"
prompt = (
    "Use the HFO documents below to answer the question. "
    "Give only the exact name from the documents, no explanation.\n\n"
    f"{trimmed}\n\n"
    f"Question: {question}\n"
    "Answer:"
)
print(f"\nFull prompt ({len(prompt)} chars):\n")
print(prompt)
conn.close()
