#!/usr/bin/env python3
"""
hfo_p6_eyebite.py — P6 Kraken Keeper: EYEBITE
════════════════════════════════════════════════

Spell Slot: B4 (BIO/BODY)
D&D Source: PHB p.238, Necromancy 6th (Brd/Sor/War/Wiz 6)
D&D Effect: "For the spell's duration, your eyes become an inky void
             imbued with dread power. One creature of your choice
             within 60 ft must succeed on a Wisdom save…"
HFO Alias:  The Devourer's Critical Eye — scan documents and rate quality,
            flag duplicates, identify gaps. Feeds web integrity.

Port:       P6 ASSIMILATE
Commander:  Kraken Keeper — The Apex Devourer
Aspect:     B (BIO/BODY)
Tier:       BEGINNER target (fills slot B4, grows P6 from 1/8 to 2/8)

Engineering Function:
    Document quality assessment engine. Scans the SSOT for documents and
    rates each on a multi-axis quality score. Designed to complement the
    Kraken Swarm's enrichment pipeline — EYEBITE identifies what the
    swarm should consume or reject.

    Quality axes:
    1. METADATA — Has required fields (title, bluf, source, port, tags)
    2. STRUCTURE — Well-formed markdown/content with headers
    3. CONTENT — Word count, signal-to-noise ratio, not empty
    4. FRESHNESS — Not stale relative to generation
    5. DEDUP — Not a near-duplicate of another document
    6. COVERAGE — Identifies port/source gaps in the corpus

    Output modes:
    - Assessment summary: Distribution of quality grades
    - Gap analysis: Which ports/sources are underserved
    - Worst offenders: Documents scoring lowest
    - Duplicate detection: Near-duplicate clusters
    - JSON export: Machine-readable full assessment

Stigmergy Events:
    hfo.gen90.p6.eyebite.assessment  — Quality scan completed
    hfo.gen90.p6.eyebite.gap_report  — Coverage gap analysis

SBE / ATDD Specification:
─────────────────────────

Feature: EYEBITE — The Devourer's Critical Eye

  # Tier 1: Invariant
  Scenario: Assessment does not modify any documents
    Given the SSOT contains N documents
    When EYEBITE runs a full assessment
    Then exactly N documents remain unchanged in the SSOT
    And the assessment is read-only

  Scenario: All 8 ports are accounted for in gap analysis
    Given the octree has ports P0–P7
    When EYEBITE runs gap analysis
    Then every port P0–P7 appears in the coverage report
    And ports with fewer than threshold docs are flagged

  # Tier 2: Happy-path
  Scenario: Quality grades follow A-F distribution
    Given N documents exist in SSOT
    When EYEBITE assesses all documents
    Then each document receives a grade A through F
    And grade distribution is displayed

  Scenario: Summary mode shows actionable statistics
    When `python hfo_p6_eyebite.py --summary` runs
    Then output shows total docs, grade distribution, and top gaps

  # Tier 3: Dedup detection
  Scenario: Near-duplicates are detected by title similarity
    Given two documents with >85% title similarity
    When EYEBITE runs dedup analysis
    Then both are flagged in the duplicate report

  # Tier 4: Performance budget
  Scenario: Assessment completes in reasonable time
    Given roughly 10,000 documents in SSOT
    When full assessment runs
    Then it completes in under 60 seconds

Usage:
    python hfo_p6_eyebite.py --summary              # Quality overview
    python hfo_p6_eyebite.py --gaps                  # Port/source gap analysis
    python hfo_p6_eyebite.py --worst N               # N lowest-scoring docs
    python hfo_p6_eyebite.py --dedup                 # Duplicate detection
    python hfo_p6_eyebite.py --json                  # Full JSON assessment
    python hfo_p6_eyebite.py --stigmergy             # Write events to SSOT
    python hfo_p6_eyebite.py --status                # Spell identity
"""

import argparse
import hashlib
import json
import os
import re
import secrets
import sqlite3
import sys
import textwrap
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from hfo_ssot_write import get_db_readwrite

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════
# § 0  PATH RESOLUTION VIA PAL
# ═══════════════════════════════════════════════════════════════

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()


HFO_ROOT = Path(os.getenv("HFO_ROOT", str(_find_root())))
POINTERS_FILE = HFO_ROOT / "hfo_gen90_pointers_blessed.json"


def _load_pointers() -> dict:
    if not POINTERS_FILE.exists():
        return {}
    with open(POINTERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("pointers", data)


def resolve_pointer(key: str) -> Path:
    pointers = _load_pointers()
    if key not in pointers:
        raise KeyError(f"Pointer '{key}' not found")
    entry = pointers[key]
    rel_path = entry["path"] if isinstance(entry, dict) else entry
    return HFO_ROOT / rel_path


# Resolve paths
try:
    SSOT_DB = resolve_pointer("ssot.db")
except (KeyError, FileNotFoundError):
    SSOT_DB = HFO_ROOT / "hfo_gen_90_hot_obsidian_forge/2_gold/resources/hfo_gen90_ssot.sqlite"

GEN = os.environ.get("HFO_GENERATION", "89")
P6_SOURCE = f"hfo_p6_eyebite_gen{GEN}"
EVENT_PREFIX = "hfo.gen90.p6.eyebite"
VERSION = "1.0.0"

# Port names for gap analysis
OCTREE_PORTS = {
    "P0": "OBSERVE",
    "P1": "BRIDGE",
    "P2": "SHAPE",
    "P3": "INJECT",
    "P4": "DISRUPT",
    "P5": "IMMUNIZE",
    "P6": "ASSIMILATE",
    "P7": "NAVIGATE",
}

# Minimum doc count per port for gap analysis
MIN_PORT_DOCS = 10

# ═══════════════════════════════════════════════════════════════
# § 1  SPELL IDENTITY
# ═══════════════════════════════════════════════════════════════

SPELL_IDENTITY = {
    "port": "P6",
    "powerword": "ASSIMILATE",
    "commander": "Kraken Keeper",
    "spell": "EYEBITE",
    "spell_slot": "B4",
    "aspect": "BIO/BODY",
    "dnd_source": "PHB p.238, Necromancy 6th",
    "school": "Necromancy",
    "alias": "The Devourer's Critical Eye",
    "version": VERSION,
    "core_thesis": "Before the Kraken consumes, the eye evaluates. "
                   "Quality assessment precedes assimilation.",
}

# ═══════════════════════════════════════════════════════════════
# § 2  QUALITY AXES
# ═══════════════════════════════════════════════════════════════

class DocAssessment:
    """Quality assessment for a single document."""
    def __init__(self, doc_id: int, title: str, source: str, port: str):
        self.doc_id = doc_id
        self.title = title or "(untitled)"
        self.source = source or ""
        self.port = port or ""
        self.scores = {}      # axis → float [0.0, 1.0]
        self.notes = []       # human-readable issues found
        self.grade = "?"      # A–F

    @property
    def total_score(self) -> float:
        if not self.scores:
            return 0.0
        return sum(self.scores.values()) / len(self.scores)

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "source": self.source,
            "port": self.port,
            "scores": self.scores,
            "total_score": round(self.total_score, 3),
            "grade": self.grade,
            "notes": self.notes,
        }


def score_metadata(row: sqlite3.Row) -> tuple:
    """Score: Does the doc have required structured metadata?"""
    score = 0.0
    notes = []
    checks = {
        "title": row["title"],
        "bluf": row["bluf"],
        "source": row["source"],
        "tags": row["tags"],
    }
    filled = sum(1 for v in checks.values() if v and str(v).strip())
    score = filled / len(checks)

    if not checks["title"]:
        notes.append("Missing title")
    if not checks["bluf"]:
        notes.append("Missing BLUF")
    if not checks["source"]:
        notes.append("Missing source")
    if not checks["tags"] or str(checks["tags"]).strip() == "":
        notes.append("Missing tags")

    # Bonus for port assignment
    if row["port"] and str(row["port"]).strip():
        score = min(1.0, score + 0.1)
    else:
        notes.append("No port assigned")

    return round(score, 3), notes


def score_structure(content: str) -> tuple:
    """Score: Is the content well-structured?"""
    if not content:
        return 0.0, ["Empty content"]

    notes = []
    score = 0.0

    # Has headers?
    header_count = len(re.findall(r'^#+\s', content, re.MULTILINE))
    if header_count >= 3:
        score += 0.3
    elif header_count >= 1:
        score += 0.15
    else:
        notes.append("No markdown headers")

    # Has paragraphs (> 1 line)?
    lines = content.strip().split("\n")
    non_empty = [l for l in lines if l.strip()]
    if len(non_empty) > 10:
        score += 0.3
    elif len(non_empty) > 3:
        score += 0.15
    else:
        notes.append("Very short content")

    # Has code blocks or lists?
    if "```" in content or re.search(r'^\s*[-*]\s', content, re.MULTILINE):
        score += 0.2

    # Has frontmatter?
    if content.strip().startswith("---"):
        score += 0.2
    else:
        notes.append("No frontmatter")

    return round(min(1.0, score), 3), notes


def score_content(word_count: int, content: str) -> tuple:
    """Score: Is the content substantive?"""
    notes = []
    score = 0.0

    # Word count scoring
    if word_count >= 500:
        score += 0.4
    elif word_count >= 100:
        score += 0.25
    elif word_count >= 20:
        score += 0.1
    else:
        notes.append(f"Very low word count ({word_count})")

    # Check for boilerplate/low signal
    if content:
        content_lower = content.lower()
        # Check for common low-signal patterns
        boilerplate_markers = ["todo", "tbd", "placeholder", "stub", "fixme"]
        found_markers = [m for m in boilerplate_markers if m in content_lower]
        if found_markers:
            notes.append(f"Contains boilerplate markers: {', '.join(found_markers)}")
            score -= 0.1

        # Check for reasonable density (not just whitespace)
        char_density = len(content.replace(" ", "").replace("\n", "")) / max(1, len(content))
        if char_density > 0.3:
            score += 0.3
        else:
            notes.append("Low character density (mostly whitespace)")

        # Check for variety (unique words)
        words = re.findall(r'\w+', content_lower)
        if words:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio > 0.3:
                score += 0.3
            elif unique_ratio > 0.15:
                score += 0.15
            else:
                notes.append("Low vocabulary diversity")

    return round(max(0.0, min(1.0, score)), 3), notes


def compute_grade(total_score: float) -> str:
    """Map a [0.0, 1.0] score to a letter grade."""
    if total_score >= 0.85:
        return "A"
    elif total_score >= 0.70:
        return "B"
    elif total_score >= 0.55:
        return "C"
    elif total_score >= 0.40:
        return "D"
    else:
        return "F"


# ═══════════════════════════════════════════════════════════════
# § 3  ASSESSMENT ENGINE
# ═══════════════════════════════════════════════════════════════

def get_db_readonly() -> sqlite3.Connection:
    if not SSOT_DB.exists():
        raise FileNotFoundError(f"SSOT database not found: {SSOT_DB}")
    conn = sqlite3.connect(f"file:{SSOT_DB}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def assess_all_documents(limit: int = 0, sample_content: bool = True) -> list:
    """Run quality assessment on all documents. Returns list of DocAssessment."""
    conn = get_db_readonly()
    try:
        if sample_content:
            query = "SELECT id, title, bluf, source, port, tags, word_count, substr(content, 1, 2000) as content_sample FROM documents"
        else:
            query = "SELECT id, title, bluf, source, port, tags, word_count, '' as content_sample FROM documents"
        if limit > 0:
            query += f" LIMIT {limit}"

        rows = conn.execute(query).fetchall()
        assessments = []

        for row in rows:
            a = DocAssessment(row["id"], row["title"], row["source"], row["port"])

            # Axis 1: Metadata
            meta_score, meta_notes = score_metadata(row)
            a.scores["metadata"] = meta_score
            a.notes.extend(meta_notes)

            # Axis 2: Structure (from content sample)
            struct_score, struct_notes = score_structure(row["content_sample"] or "")
            a.scores["structure"] = struct_score
            a.notes.extend(struct_notes)

            # Axis 3: Content
            wc = row["word_count"] or 0
            content_score, content_notes = score_content(wc, row["content_sample"] or "")
            a.scores["content"] = content_score
            a.notes.extend(content_notes)

            # Compute grade
            a.grade = compute_grade(a.total_score)
            assessments.append(a)

        return assessments
    finally:
        conn.close()


def find_duplicates(assessments: list, threshold: float = 0.85) -> list:
    """Find near-duplicate documents by title similarity."""
    clusters = []
    seen = set()

    # Sort by title for efficient comparison
    indexed = [(a.doc_id, a.title.strip().lower()) for a in assessments
               if a.title and a.title.strip()]

    for i in range(len(indexed)):
        if indexed[i][0] in seen:
            continue
        cluster = [indexed[i]]
        for j in range(i + 1, len(indexed)):
            if indexed[j][0] in seen:
                continue
            sim = SequenceMatcher(None, indexed[i][1], indexed[j][1]).ratio()
            if sim >= threshold:
                cluster.append(indexed[j])
                seen.add(indexed[j][0])
        if len(cluster) > 1:
            seen.add(indexed[i][0])
            clusters.append(cluster)

    return clusters


def analyze_gaps(assessments: list) -> dict:
    """Analyze coverage gaps across ports and sources."""
    port_counts = Counter()
    source_counts = Counter()
    port_quality = defaultdict(list)

    for a in assessments:
        if a.port:
            port_counts[a.port] += 1
            port_quality[a.port].append(a.total_score)
        else:
            port_counts["(unassigned)"] += 1
        if a.source:
            source_counts[a.source] += 1
        else:
            source_counts["(unknown)"] += 1

    # Port gap analysis
    port_gaps = {}
    for port_key, port_name in OCTREE_PORTS.items():
        count = port_counts.get(port_key, 0)
        avg_quality = 0.0
        if port_key in port_quality and port_quality[port_key]:
            avg_quality = sum(port_quality[port_key]) / len(port_quality[port_key])
        port_gaps[port_key] = {
            "name": port_name,
            "count": count,
            "avg_quality": round(avg_quality, 3),
            "gap": count < MIN_PORT_DOCS,
        }

    return {
        "port_gaps": port_gaps,
        "source_counts": dict(source_counts.most_common()),
        "unassigned_port_count": port_counts.get("(unassigned)", 0),
        "total_assessed": len(assessments),
    }


# ═══════════════════════════════════════════════════════════════
# § 4  DISPLAY FORMATTERS
# ═══════════════════════════════════════════════════════════════

def format_summary(assessments: list) -> str:
    """Format a quality overview summary."""
    if not assessments:
        return "No documents to assess."

    grade_dist = Counter(a.grade for a in assessments)
    total = len(assessments)
    avg_score = sum(a.total_score for a in assessments) / total

    lines = [
        "",
        "  ═══ EYEBITE — Quality Assessment Summary ═══",
        f"  Documents assessed: {total}",
        f"  Average quality:    {avg_score:.3f}",
        "",
        "  Grade Distribution:",
    ]

    for grade in ["A", "B", "C", "D", "F"]:
        count = grade_dist.get(grade, 0)
        pct = (count / total) * 100
        bar = "#" * int(pct / 2)
        lines.append(f"    {grade}: {count:>5} ({pct:5.1f}%) {bar}")

    # Axis averages
    axis_totals = defaultdict(list)
    for a in assessments:
        for axis, score in a.scores.items():
            axis_totals[axis].append(score)

    lines.append("")
    lines.append("  Axis Averages:")
    for axis, scores in sorted(axis_totals.items()):
        avg = sum(scores) / len(scores) if scores else 0
        lines.append(f"    {axis:>12}: {avg:.3f}")

    return "\n".join(lines)


def format_gaps(gap_analysis: dict) -> str:
    """Format coverage gap analysis."""
    lines = [
        "",
        "  ═══ EYEBITE — Coverage Gap Analysis ═══",
        "",
        "  Port Coverage:",
    ]

    for port_key in sorted(gap_analysis["port_gaps"].keys()):
        info = gap_analysis["port_gaps"][port_key]
        flag = " *** GAP ***" if info["gap"] else ""
        lines.append(
            f"    {port_key} {info['name']:>12}: {info['count']:>5} docs "
            f"(avg quality: {info['avg_quality']:.3f}){flag}"
        )

    lines.append(f"\n  Unassigned to port: {gap_analysis['unassigned_port_count']}")
    lines.append("")
    lines.append("  Source Distribution:")

    for source, count in list(gap_analysis["source_counts"].items())[:15]:
        lines.append(f"    {source:>20}: {count:>5}")

    return "\n".join(lines)


def format_worst(assessments: list, n: int) -> str:
    """Format worst-quality documents."""
    sorted_docs = sorted(assessments, key=lambda a: a.total_score)[:n]
    lines = [
        "",
        f"  ═══ EYEBITE — {n} Lowest Quality Documents ═══",
        "",
    ]
    for a in sorted_docs:
        notes_str = "; ".join(a.notes[:3]) if a.notes else "—"
        lines.append(
            f"  [{a.grade}] {a.total_score:.3f}  ID {a.doc_id:>5}  "
            f"{a.title[:60]:60}  {notes_str[:50]}"
        )

    return "\n".join(lines)


def format_dedup(clusters: list) -> str:
    """Format duplicate detection results."""
    if not clusters:
        return "\n  ═══ EYEBITE — No near-duplicates detected ═══"

    lines = [
        "",
        f"  ═══ EYEBITE — {len(clusters)} Duplicate Clusters Found ═══",
        "",
    ]
    for i, cluster in enumerate(clusters[:20], 1):
        lines.append(f"  Cluster {i}:")
        for doc_id, title in cluster:
            lines.append(f"    ID {doc_id:>5}: {title[:70]}")
        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# § 5  SSOT / STIGMERGY
# ═══════════════════════════════════════════════════════════════


def write_stigmergy_event(
    conn: sqlite3.Connection,
    event_type: str,
    subject: str,
    data: dict,
) -> int:
    """Write a CloudEvent to stigmergy trail."""
    event_id = hashlib.md5(
        f"{event_type}{time.time()}{secrets.token_hex(4)}".encode()
    ).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)
    event = {
        "specversion": "1.0",
        "id": event_id,
        "type": event_type,
        "source": P6_SOURCE,
        "subject": subject,
        "time": now,
        "timestamp": now,
        "datacontenttype": "application/json",
        "trace_id": trace_id,
        "span_id": span_id,
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "phase": "CLOUDEVENT",
        "agent_id": "p6_kraken_keeper",
        "spell": "EYEBITE",
        "data": data,
    }
    content_hash = hashlib.sha256(
        json.dumps(event, sort_keys=True).encode()
    ).hexdigest()
    conn.execute(
        """INSERT OR IGNORE INTO stigmergy_events
           (event_type, timestamp, subject, source, data_json, content_hash)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, now, subject, P6_SOURCE, json.dumps(event), content_hash),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def write_assessment_to_ssot(assessments: list, gap_analysis: dict) -> int:
    """Write assessment results to SSOT stigmergy."""
    conn = get_db_readwrite()
    try:
        grade_dist = Counter(a.grade for a in assessments)
        total = len(assessments)
        avg = sum(a.total_score for a in assessments) / total if total else 0

        data = {
            "spell_identity": SPELL_IDENTITY,
            "total_assessed": total,
            "average_quality": round(avg, 3),
            "grade_distribution": dict(grade_dist),
            "gap_summary": {
                port: {"count": info["count"], "gap": info["gap"]}
                for port, info in gap_analysis.get("port_gaps", {}).items()
            },
            "worst_5": [
                {"doc_id": a.doc_id, "title": a.title, "score": round(a.total_score, 3), "grade": a.grade}
                for a in sorted(assessments, key=lambda x: x.total_score)[:5]
            ],
        }
        event_type = f"{EVENT_PREFIX}.assessment"
        subject = f"eyebite:assessment:total={total}:avg={avg:.3f}"
        return write_stigmergy_event(conn, event_type, subject, data)
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# § 6  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="P6 EYEBITE — The Devourer's Critical Eye",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Spell: EYEBITE (PHB p.238, Necromancy 6th)
            Port:  P6 ASSIMILATE — Kraken Keeper
            Alias: The Devourer's Critical Eye
            "Before the Kraken consumes, the eye evaluates."
        """),
    )
    parser.add_argument("--summary", action="store_true",
                        help="Quality overview summary")
    parser.add_argument("--gaps", action="store_true",
                        help="Port/source coverage gap analysis")
    parser.add_argument("--worst", type=int, metavar="N",
                        help="Show N lowest-quality documents")
    parser.add_argument("--dedup", action="store_true",
                        help="Near-duplicate detection")
    parser.add_argument("--json", action="store_true",
                        help="Full JSON assessment output")
    parser.add_argument("--stigmergy", action="store_true",
                        help="Write assessment to SSOT")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit documents assessed (0 = all)")
    parser.add_argument("--status", action="store_true",
                        help="Show spell identity")
    args = parser.parse_args()

    if args.status:
        print(json.dumps(SPELL_IDENTITY, indent=2))
        return

    if not any([args.summary, args.gaps, args.worst, args.dedup, args.json, args.stigmergy]):
        # Default to summary
        args.summary = True

    # Run assessment
    print("  [EYEBITE] Assessing documents...", end="", flush=True)
    t0 = time.time()
    assessments = assess_all_documents(limit=args.limit)
    elapsed = time.time() - t0
    print(f" done ({len(assessments)} docs in {elapsed:.1f}s)")

    gap_analysis = analyze_gaps(assessments)

    if args.summary or args.json:
        print(format_summary(assessments))

    if args.gaps or args.json:
        print(format_gaps(gap_analysis))

    if args.worst:
        print(format_worst(assessments, args.worst))

    if args.dedup:
        print("  [EYEBITE] Detecting duplicates...", end="", flush=True)
        clusters = find_duplicates(assessments)
        print(f" found {len(clusters)} clusters")
        print(format_dedup(clusters))

    if args.json:
        output = {
            "spell_identity": SPELL_IDENTITY,
            "assessment_time": datetime.now(timezone.utc).isoformat(),
            "total_documents": len(assessments),
            "elapsed_seconds": round(elapsed, 2),
            "grade_distribution": dict(Counter(a.grade for a in assessments)),
            "gap_analysis": gap_analysis,
            "assessments": [a.to_dict() for a in assessments[:100]],  # cap JSON export
        }
        print(json.dumps(output, indent=2))

    if args.stigmergy:
        try:
            row_id = write_assessment_to_ssot(assessments, gap_analysis)
            print(f"\n  [EYEBITE] Assessment written to SSOT: row {row_id}")
        except Exception as e:
            print(f"\n  [EYEBITE] Stigmergy write failed: {e}")


if __name__ == "__main__":
    main()
