---
medallion_layer: gold
mutation_score: 0
hive: V
hfo_header_v3: compact
schema_id: hfo.mosaic_microkernel_header.v3
mnemonic: "O·B·S·I·D·I·A·N = 8 ports = 1 octree"
bluf: "Tutorial: Mine Your SSOT for Institutional Knowledge"
primary_port: P6
role: "P6 ASSIMILATE — memory/SSOT"
tags: [gold, forge:hot, para:resources, diataxis:tutorial, p6, omega, mine, ssot, institutional, markdown]
full_header: "braided_mission_thread_alpha_omega_hfo_gen88v7.yaml (lines 1–512)"
generated: "2026-02-10T08:32:49Z"
---

# Tutorial: Mine Your SSOT for Institutional Knowledge

## Goal

By the end of this tutorial you will know how to:
1. Connect to the SSOT SQLite database
2. Run exploratory queries to understand what's inside
3. Extract thematic clusters of memories
4. Distill raw memories into a structured analytical artifact
5. Write an SSOT status update recording your work

## Prerequisites

- Python venv activated: `source .venv/bin/activate`
- SSOT SQLite path: `hfo_hot_obsidian_forge/0_bronze/2_resources/memory_fragments_storehouse/blessed_ssot/artifacts__mcp_memory_service__gen88_v4__hfo_gen88_v4_ssot_sqlite_vec_2026_01_26.db`
- `scripts/mcp_env_wrap.sh` available (wraps Python calls with correct env)

## Mosaic Tiles Exercised

| Tile ID | Category | How It Applies |
|---------|----------|---------------|
| `archetype.survival.phoenix_protocol` | survival | Resurrecting knowledge from raw data stores |
| `archetype.quality.goldilocks_zone` | quality | Calibrating how much to extract (not too little, not too much) |
| `archetype.growth.ssot_single_write_path` | growth | Using the blessed write-path for all memory operations |

## Steps

### Step 1 — Verify Database Access

```bash
cd /home/tommytai3/active/hfo_gen_88_chromebook_v_1

DB_PATH="hfo_hot_obsidian_forge/0_bronze/2_resources/memory_fragments_storehouse/blessed_ssot/artifacts__mcp_memory_service__gen88_v4__hfo_gen88_v4_ssot_sqlite_vec_2026_01_26.db"

bash scripts/mcp_env_wrap.sh ./.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('${DB_PATH}')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM memories')
count = cur.fetchone()[0]
print(f'Total memories: {count}')
cur.execute('SELECT SUM(LENGTH(content)) FROM memories')
chars = cur.fetchone()[0]
print(f'Total characters: {chars:,}')
conn.close()
"
```

Expected output:
```
Total memories: 8557
Total characters: 63,800,000+
```

### Step 2 — Understand the Schema

The `memories` table has these columns:

| Column | Type | Purpose |
|--------|------|---------|
| `id` | TEXT | Unique memory ID |
| `content_hash` | TEXT | SHA-256 of content (dedup) |
| `content` | TEXT | The actual memory text |
| `tags` | TEXT | JSON array of tags |
| `memory_type` | TEXT | Classification (e.g., "status_update") |
| `metadata` | TEXT | JSON metadata blob |
| `created_at` | REAL | Unix timestamp |
| `updated_at` | REAL | Unix timestamp |
| `created_at_iso` | TEXT | ISO 8601 date |
| `updated_at_iso` | TEXT | ISO 8601 date |
| `deleted_at` | TEXT | Soft delete marker |

**Important**: `created_at_iso` reflects *ingestion* date (Jan–Feb 2026), NOT the event date. Real timelines must be inferred from content analysis.

### Step 3 — Explore by Tags

```bash
bash scripts/mcp_env_wrap.sh ./.venv/bin/python -c "
import sqlite3, json
conn = sqlite3.connect('${DB_PATH}')
cur = conn.cursor()
cur.execute('SELECT tags FROM memories WHERE tags IS NOT NULL')
tag_counts = {}
for (tags_json,) in cur.fetchall():
    try:
        tags = json.loads(tags_json) if tags_json else []
        for t in tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    except: pass
for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1])[:20]:
    print(f'{count:5d}  {tag}')
conn.close()
"
```

This shows the 20 most common tags. Use these to orient your search.

### Step 4 — Extract a Thematic Cluster

Pick a topic (e.g., "phoenix" or "omega" or "medallion"). Search for memories containing that term:

```bash
TOPIC="phoenix"

bash scripts/mcp_env_wrap.sh ./.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('${DB_PATH}')
cur = conn.cursor()
cur.execute('''
    SELECT id, LENGTH(content), substr(content, 1, 200)
    FROM memories
    WHERE content LIKE '%${TOPIC}%'
    ORDER BY created_at DESC
    LIMIT 20
''')
for row in cur.fetchall():
    mid, length, preview = row
    print(f'[{mid[:8]}] {length:6d} chars | {preview[:120]}...')
conn.close()
"
```

### Step 5 — Read Full Memories and Take Notes

Once you've identified interesting memory IDs, read them fully:

```bash
MEM_ID="your-memory-id-here"

bash scripts/mcp_env_wrap.sh ./.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('${DB_PATH}')
cur = conn.cursor()
cur.execute('SELECT content, tags, memory_type FROM memories WHERE id = ?', ('${MEM_ID}',))
row = cur.fetchone()
if row:
    content, tags, mtype = row
    print(f'Type: {mtype}')
    print(f'Tags: {tags}')
    print(f'Content ({len(content)} chars):')
    print(content)
conn.close()
"
```

As you read, look for:
- **Patterns**: What recurs across multiple memories?
- **Antipatterns**: What failed and why?
- **Pivot points**: Where did direction change?
- **Naming events**: When did concepts get their names?

### Step 6 — Distill into an Artifact

Create a markdown file in the appropriate location:
- Bronze (experimental): `hfo_hot_obsidian_forge/0_bronze/2_resources/reports/`
- Silver (verified): `hfo_hot_obsidian_forge/1_silver/2_resources/reports/`
- Gold (hardened): `hfo_hot_obsidian_forge/2_gold/2_resources/reports/`

Use the era deep dive template or a Diataxis template from `5_templates/`.

### Step 7 — Write SSOT Status Update

```bash
bash scripts/mcp_env_wrap.sh ./.venv/bin/python hfo_ssot_status_update.py \
  --topic "ssot_mining_<your_topic>" \
  --payload-json '{
    "summary": "Mined SSOT for <topic>. Extracted N memories, distilled into <artifact>.",
    "artifacts_created": ["path/to/your/artifact.md"],
    "memories_examined": 42,
    "mosaic_tiles_extracted": ["archetype.category.name"],
    "next_steps": ["What to mine next"]
  }'
```

## Expected Result (Proof)

- A new artifact file exists at the appropriate medallion layer
- SSOT status update written and queryable
- At least 1 mosaic tile identified (pattern or antipattern)

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `no such table: memories` | Wrong DB path | Check `hfo_pointers.json → paths.mcp_memory_ssot_sqlite` |
| 0 memories returned | Topic not in content | Try broader search terms; check spelling |
| `created_at_iso` dates all Jan 2026 | Ingestion dates, not event dates | Infer real dates from content text |
| Very large memories (>50K chars) | Bulk ingested docs | These are often the richest; read selectively |

## What You Learned

- The SSOT SQLite is the single source of truth for HFO institutional memory
- Tags and content search are the two primary access patterns
- Raw memories must be distilled through analytical lenses to become reusable
- Every mining session ends with an SSOT status update (single write-path)
- Mosaic tiles are the transferable output: named, behavioral, positioned patterns
