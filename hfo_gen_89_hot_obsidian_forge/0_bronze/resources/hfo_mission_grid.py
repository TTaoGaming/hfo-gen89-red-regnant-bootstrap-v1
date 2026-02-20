"""
HFO Mission Grid — MAP-Elites Behavioral Grid Query Module
===========================================================
Social spider optimization: query the stigmergy manifold by positional
data and get a MATRIX of elites per niche, not a single best.

Behavioral Descriptors (positional coordinates):
  - port:           P0-P7 octree position
  - era:            ERA_0 through ERA_5+
  - thread:         alpha/omega/specific thread name
  - meadows_level:  L1-L12 leverage depth

Usage:
    from hfo_mission_grid import MissionGrid

    grid = MissionGrid()  # auto-discovers DB via PAL

    # Get the full matrix
    matrix = grid.grid_slice(port="P4")

    # Get neighborhood around a position
    neighbors = grid.neighborhood(port="P4", era="ERA_4", radius=1)

    # Get elite at a specific position
    elite = grid.elite_at("T-P4-001")

    # Replace elite if fitter (MAP-Elites replacement rule)
    grid.replace_if_fitter("T-P4-001", fitness=0.85, mutation_confidence=80,
                           summary="Gates passed 30/30")

    # Get the tree rooted at a thread_key
    tree = grid.descendants("ERA_4")

    # Optimistic concurrency update
    grid.update_status("T-P4-001", "done", expected_version=1)

Schema ID: hfo.gen89.mission_grid.v1
"""
import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any


def _find_root():
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        if os.path.isfile(os.path.join(d, "AGENTS.md")):
            return d
        d = os.path.dirname(d)
    raise FileNotFoundError("Cannot find HFO_ROOT (AGENTS.md)")


HFO_ROOT = _find_root()
DB_PATH = os.path.join(
    HFO_ROOT,
    "hfo_gen_89_hot_obsidian_forge", "2_gold", "resources",
    "hfo_gen89_ssot.sqlite"
)


class MissionGrid:
    """
    MAP-Elites behavioral grid over the stigmergy manifold.
    
    Every query returns a MATRIX (list of elites), not a single best.
    Social spider optimization: read vibrations, write to your niche.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    # ─────────────────────────────────────────────
    #  GRID QUERIES: matrix by positional data
    # ─────────────────────────────────────────────

    def grid_slice(self, *,
                   port: Optional[str] = None,
                   era: Optional[str] = None,
                   thread: Optional[str] = None,
                   meadows_level: Optional[int] = None,
                   thread_type: Optional[str] = None,
                   status: Optional[str] = None,
                   min_fitness: Optional[float] = None,
                   limit: int = 100) -> List[Dict[str, Any]]:
        """
        Query the MAP-Elites grid by any combination of behavioral descriptors.
        Returns a MATRIX of all matching elites — not a single best.
        
        This is the core social spider query: "What vibrations exist at this
        position in the manifold?"
        """
        conn = self._conn()
        conditions = []
        params = []

        if port is not None:
            conditions.append("port = ?")
            params.append(port)
        if era is not None:
            conditions.append("era = ?")
            params.append(era)
        if thread is not None:
            conditions.append("thread = ?")
            params.append(thread)
        if meadows_level is not None:
            conditions.append("meadows_level = ?")
            params.append(meadows_level)
        if thread_type is not None:
            conditions.append("thread_type = ?")
            params.append(thread_type)
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if min_fitness is not None:
            conditions.append("fitness >= ?")
            params.append(min_fitness)

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT thread_key, parent_key, thread_type, title, bluf,
                   port, era, thread, meadows_level,
                   fitness, mutation_confidence,
                   status, priority, assignee,
                   metadata_json, updated_at, version
            FROM mission_state
            WHERE {where}
            ORDER BY fitness DESC, priority DESC
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def neighborhood(self, *,
                     port: Optional[str] = None,
                     era: Optional[str] = None,
                     thread: Optional[str] = None,
                     meadows_level: Optional[int] = None,
                     radius: int = 1,
                     limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get all elites within `radius` steps of a position in the manifold.
        
        Distance metric:
          - port match/mismatch = 0/1
          - era match/mismatch = 0/1
          - thread match/mismatch = 0/1
          - |meadows_level - target| (if provided)
          
        Returns matrix sorted by distance ASC, fitness DESC.
        """
        conn = self._conn()
        
        # Build distance calculation
        dist_parts = []
        params = []
        
        if port is not None:
            dist_parts.append("CASE WHEN port = ? THEN 0 WHEN port IS NULL THEN 0.5 ELSE 1 END")
            params.append(port)
        if era is not None:
            dist_parts.append("CASE WHEN era = ? THEN 0 WHEN era IS NULL THEN 0.5 ELSE 1 END")
            params.append(era)
        if thread is not None:
            dist_parts.append("CASE WHEN thread = ? THEN 0 WHEN thread IS NULL THEN 0.5 ELSE 1 END")
            params.append(thread)
        if meadows_level is not None:
            dist_parts.append("ABS(COALESCE(meadows_level, ?) - ?)")
            params.extend([meadows_level, meadows_level])

        if not dist_parts:
            # No position given — return everything
            return self.grid_slice(limit=limit)

        distance_expr = " + ".join(dist_parts)
        # distance_expr appears twice in SQL (SELECT + WHERE), so duplicate params
        threshold = radius + 0.5  # allow half-matches for NULL
        select_params = list(params)
        where_params = list(params) + [threshold]
        all_params = select_params + where_params + [limit]

        sql = f"""
            SELECT *,
                   ({distance_expr}) AS manifold_distance
            FROM mission_state
            WHERE status != 'archived'
              AND ({distance_expr}) <= ?
            ORDER BY manifold_distance ASC, fitness DESC
            LIMIT ?
        """
        rows = conn.execute(sql, all_params).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def elite_at(self, thread_key: str) -> Optional[Dict[str, Any]]:
        """Get a single elite by its thread_key."""
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM mission_state WHERE thread_key = ?",
            (thread_key,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def descendants(self, thread_key: str) -> List[Dict[str, Any]]:
        """
        Recursive CTE: get the full tree rooted at thread_key.
        Returns the matrix of all descendants (children, grandchildren, ...).
        """
        conn = self._conn()
        rows = conn.execute("""
            WITH RECURSIVE tree AS (
                SELECT * FROM mission_state WHERE thread_key = ?
                UNION ALL
                SELECT ms.* FROM mission_state ms
                JOIN tree t ON ms.parent_key = t.thread_key
            )
            SELECT * FROM tree ORDER BY thread_type, fitness DESC
        """, (thread_key,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ─────────────────────────────────────────────
    #  MAP-ELITES VIEWS: pre-computed matrix slices
    # ─────────────────────────────────────────────

    def grid_view(self) -> List[Dict[str, Any]]:
        """Full MAP-Elites grid from the map_elites_grid VIEW."""
        conn = self._conn()
        rows = conn.execute("SELECT * FROM map_elites_grid ORDER BY port, era").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def port_heatmap(self) -> List[Dict[str, Any]]:
        """Fitness heatmap by port."""
        conn = self._conn()
        rows = conn.execute("SELECT * FROM port_heatmap").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def thread_health(self) -> List[Dict[str, Any]]:
        """Thread health by thread+era."""
        conn = self._conn()
        rows = conn.execute("SELECT * FROM thread_health").fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ─────────────────────────────────────────────
    #  MUTATIONS: write to niche cells
    # ─────────────────────────────────────────────

    def replace_if_fitter(self, thread_key: str, *,
                          fitness: float,
                          mutation_confidence: int = 0,
                          summary: str = "") -> Dict[str, Any]:
        """
        MAP-Elites replacement rule:
        Replace the current elite if the new fitness is strictly higher.
        
        From Doc 90 (R33): mutation_score >= 0.80 AND fitness > current_occupant.
        Adapted: mutation_confidence is tracked but fitness is the replacement key.
        
        Returns dict with 'replaced' bool, old/new fitness, and version.
        """
        conn = self._conn()
        row = conn.execute(
            "SELECT fitness, mutation_confidence, version FROM mission_state WHERE thread_key = ?",
            (thread_key,)
        ).fetchone()

        if row is None:
            conn.close()
            return {"error": f"No elite at {thread_key}", "replaced": False}

        old_fitness = row[0]
        old_version = row[2]

        if fitness <= old_fitness:
            conn.close()
            return {
                "replaced": False,
                "reason": f"New fitness {fitness:.3f} <= current {old_fitness:.3f}",
                "thread_key": thread_key,
                "current_fitness": old_fitness,
            }

        # Replace — optimistic concurrency via version check
        result = conn.execute("""
            UPDATE mission_state
            SET fitness = ?,
                mutation_confidence = ?,
                version = version + 1,
                updated_at = ?,
                metadata_json = json_set(
                    COALESCE(metadata_json, '{}'),
                    '$.last_replacement', ?,
                    '$.replaced_fitness', ?
                )
            WHERE thread_key = ? AND version = ?
        """, (fitness, mutation_confidence, self._now(),
              summary, old_fitness,
              thread_key, old_version))

        if result.rowcount == 0:
            conn.close()
            return {"replaced": False, "reason": "Version conflict — concurrent write", "thread_key": thread_key}

        conn.commit()
        conn.close()
        return {
            "replaced": True,
            "thread_key": thread_key,
            "old_fitness": old_fitness,
            "new_fitness": fitness,
            "new_version": old_version + 1,
            "mutation_confidence": mutation_confidence,
        }

    def update_status(self, thread_key: str, status: str,
                      expected_version: Optional[int] = None) -> Dict[str, Any]:
        """
        Update status with optimistic concurrency.
        If expected_version is provided, update only if version matches.
        Trigger will automatically write to stigmergy_events.
        """
        conn = self._conn()

        if expected_version is not None:
            result = conn.execute("""
                UPDATE mission_state
                SET status = ?, version = version + 1, updated_at = ?
                WHERE thread_key = ? AND version = ?
            """, (status, self._now(), thread_key, expected_version))
        else:
            result = conn.execute("""
                UPDATE mission_state
                SET status = ?, version = version + 1, updated_at = ?
                WHERE thread_key = ?
            """, (status, self._now(), thread_key))

        if result.rowcount == 0:
            conn.close()
            return {"updated": False, "reason": "Not found or version conflict"}

        conn.commit()
        conn.close()
        return {"updated": True, "thread_key": thread_key, "new_status": status}

    def insert_elite(self, *,
                     thread_key: str,
                     parent_key: Optional[str] = None,
                     thread_type: str = "task",
                     title: str,
                     bluf: Optional[str] = None,
                     port: Optional[str] = None,
                     era: Optional[str] = None,
                     thread: Optional[str] = None,
                     meadows_level: Optional[int] = None,
                     fitness: float = 0.0,
                     mutation_confidence: int = 0,
                     status: str = "active",
                     priority: int = 0,
                     assignee: Optional[str] = None,
                     metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Insert a new elite into the grid.
        Trigger will automatically write to stigmergy_events.
        """
        conn = self._conn()
        now = self._now()
        try:
            conn.execute("""
                INSERT INTO mission_state
                (thread_key, parent_key, thread_type, title, bluf,
                 port, era, thread, meadows_level,
                 fitness, mutation_confidence,
                 status, priority, assignee,
                 metadata_json, created_at, updated_at, version, medallion)
                VALUES (?,?,?,?,?, ?,?,?,?, ?,?, ?,?,?, ?,?,?,1,'bronze')
            """, (
                thread_key, parent_key, thread_type, title, bluf,
                port, era, thread, meadows_level,
                fitness, mutation_confidence,
                status, priority, assignee,
                json.dumps(metadata or {}), now, now
            ))
            conn.commit()
            conn.close()
            return {"inserted": True, "thread_key": thread_key}
        except sqlite3.IntegrityError as e:
            conn.close()
            return {"inserted": False, "error": str(e)}

    # ─────────────────────────────────────────────
    #  AUDIT TRAIL: query stigmergy for history
    # ─────────────────────────────────────────────

    def audit_trail(self, thread_key: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get the full stigmergy audit history for a thread_key."""
        conn = self._conn()
        rows = conn.execute("""
            SELECT id, event_type, timestamp, source, subject, data_json
            FROM stigmergy_events
            WHERE event_type LIKE 'hfo.gen89.mission.%'
              AND subject = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (thread_key, limit)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def mission_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all mission state events from stigmergy trail."""
        conn = self._conn()
        rows = conn.execute("""
            SELECT id, event_type, timestamp, subject,
                   json_extract(data_json, '$.thread_key') as thread_key,
                   json_extract(data_json, '$.new_status') as new_status,
                   json_extract(data_json, '$.new_fitness') as new_fitness
            FROM stigmergy_events
            WHERE event_type LIKE 'hfo.gen89.mission.%'
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ─────────────────────────────────────────────
    #  PRETTY PRINTERS
    # ─────────────────────────────────────────────

    def print_grid(self, rows: Optional[List[Dict]] = None):
        """Print a matrix of elites in table format."""
        if rows is None:
            rows = self.grid_slice(limit=200)
        if not rows:
            print("(empty grid)")
            return

        print(f"{'KEY':<22s} {'TYPE':<10s} {'PORT':<5s} {'ERA':<6s} {'THREAD':<8s} {'ML':>3s} {'FIT':>5s} {'MC':>4s} {'STATUS':<8s} TITLE")
        print("─" * 110)
        for r in rows:
            print(f"{r['thread_key']:<22s} {r['thread_type']:<10s} "
                  f"{(r.get('port') or '---'):<5s} {(r.get('era') or '---'):<6s} "
                  f"{(r.get('thread') or '---'):<8s} {r.get('meadows_level') or '-':>3} "
                  f"{r['fitness']:>5.2f} {r['mutation_confidence']:>4d} "
                  f"{r['status']:<8s} {r['title'][:40]}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CLI demo
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    import sys
    grid = MissionGrid()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "slice":
            # e.g.: python hfo_mission_grid.py slice port=P4 era=ERA_4
            kwargs = {}
            for arg in sys.argv[2:]:
                if "=" in arg:
                    k, v = arg.split("=", 1)
                    if k == "meadows_level":
                        v = int(v)
                    elif k == "min_fitness":
                        v = float(v)
                    kwargs[k] = v
            rows = grid.grid_slice(**kwargs)
            grid.print_grid(rows)

        elif cmd == "neighborhood":
            kwargs = {}
            for arg in sys.argv[2:]:
                if "=" in arg:
                    k, v = arg.split("=", 1)
                    if k in ("meadows_level", "radius"):
                        v = int(v)
                    kwargs[k] = v
            rows = grid.neighborhood(**kwargs)
            grid.print_grid(rows)

        elif cmd == "tree":
            key = sys.argv[2] if len(sys.argv) > 2 else "alpha"
            rows = grid.descendants(key)
            grid.print_grid(rows)

        elif cmd == "heatmap":
            for row in grid.port_heatmap():
                print(f"  {row['port']}: total={row['total_cells']} avg_fitness={row['avg_fitness']:.2f} "
                      f"max={row['max_fitness']:.2f} active={row['active']} done={row['done']}")

        elif cmd == "health":
            for row in grid.thread_health():
                print(f"  {row.get('thread') or '---':8s} [{row.get('era') or '---':5s}] "
                      f"total={row['total_cells']} avg={row['avg_fitness']:.2f} "
                      f"active={row['active']} done={row['done']}")

        elif cmd == "audit":
            key = sys.argv[2] if len(sys.argv) > 2 else None
            if key:
                events = grid.audit_trail(key)
                for e in events:
                    print(f"  [{e['timestamp']}] {e['event_type']} → {e['subject']}")
            else:
                events = grid.mission_events()
                for e in events:
                    print(f"  [{e['timestamp']}] {e['event_type']} | {e.get('thread_key')} "
                          f"status={e.get('new_status')} fitness={e.get('new_fitness')}")
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python hfo_mission_grid.py [slice|neighborhood|tree|heatmap|health|audit] [args...]")
    else:
        # Default: show full grid
        print("=== MAP-Elites Behavioral Grid ===\n")
        grid.print_grid()
        print(f"\n=== Port Heatmap ===")
        for row in grid.port_heatmap():
            print(f"  {row['port']}: total={row['total_cells']} avg_fitness={row['avg_fitness']:.2f} "
                  f"max={row['max_fitness']:.2f} active={row['active']} done={row['done']}")
        print(f"\n=== Thread Health ===")
        for row in grid.thread_health():
            print(f"  {row.get('thread') or '---':8s} [{row.get('era') or '---':5s}] "
                  f"total={row['total_cells']} avg={row['avg_fitness']:.2f} "
                  f"active={row['active']} done={row['done']}")
