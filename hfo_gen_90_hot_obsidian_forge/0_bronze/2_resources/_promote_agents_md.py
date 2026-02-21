"""Promote AGENTS.md (doc 7852) to silver — it's the root SSOT, actively maintained by TTAO."""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from hfo_medallion_promotion import promote_to_silver

from pathlib import Path
db = str(Path(__file__).resolve().parent.parent.parent / "2_gold" / "2_resources" / "hfo_gen90_ssot.sqlite")

validation = {
    "reviewed_by": "TTAO",
    "review_date": "2026-02-18",
    "validation_type": "human_review",
    "claims_verified": "Workspace layout verified against filesystem, pointer system tested, SSOT schema confirmed, medallion architecture documented",
    "cross_referenced": "hfo_gen90_pointers_blessed.json, hfo_gen90_ssot.sqlite schema, .githooks/pre-commit",
}

result = promote_to_silver(db, 7852, validation)
print(f"Result: {result}")
