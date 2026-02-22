# Cognitive Persistence Sharding Options for 8 Ports

## Objective
Start 8 shards of cognitive persistence into SQLite memory for the 8 HFO ports/commanders.

## 4 Initial Options

1. **8 Separate SQLite Database Files**
   - *Architecture*: Each port gets its own `.sqlite` file (e.g., `p0_observe.sqlite`, `p1_bridge.sqlite`).
   - *Pros*: True physical isolation, zero lock contention between ports, easy to backup/restore individually.
   - *Cons*: Cross-port queries require `ATTACH DATABASE`, connection management overhead.

2. **1 SQLite Database with 8 Port-Specific Tables**
   - *Architecture*: A single `ssot.sqlite` with tables like `p0_memory`, `p1_memory`, etc.
   - *Pros*: Single connection, easy cross-port queries.
   - *Cons*: Schema duplication, potential write lock contention if multiple ports write simultaneously (though WAL mode helps).

3. **1 SQLite Database with 1 Unified Table and a `port` Column**
   - *Architecture*: A single `memory` table with a `port` column (e.g., `P0`, `P1`).
   - *Pros*: Simplest schema, easiest to query globally.
   - *Cons*: Not true sharding, large index required on `port` column, highest write contention.

4. **8 In-Memory SQLite Databases Synced to 1 Disk Database**
   - *Architecture*: Each port operates on an in-memory DB (`:memory:`) for fast read/write, and periodically flushes to a central on-disk DB.
   - *Pros*: Extremely fast, zero disk I/O blocking during operations.
   - *Cons*: High complexity, risk of data loss on crash before sync, complex conflict resolution.

---

## Collapsed to 2 Pareto Optimal Options

### Option A: 8 Separate SQLite Database Files (Maximum Isolation)
- **Why it's optimal**: SQLite has a single-writer lock per database file. If the 8 commanders operate concurrently and write frequently, a single file will bottleneck. Separate files guarantee zero write contention across ports.
- **Implementation**: 8 files (`p0.sqlite` to `p7.sqlite`). When a global view is needed, a master connection uses `ATTACH DATABASE 'p0.sqlite' AS p0;` to query across them.

### Option B: 1 Unified Database with WAL Mode (Maximum Coherence)
- **Why it's optimal**: If the system is read-heavy and writes are fast, a single database with Write-Ahead Logging (WAL) enabled provides sufficient concurrency while keeping the architecture drastically simpler.
- **Implementation**: One `ssot.sqlite` file. A single `documents` or `memory` table with a `port` column. Enable `PRAGMA journal_mode=WAL;` to allow concurrent readers and one writer without blocking.

## Critical Notes for Handoff
- **Current State**: The system currently uses a single `hfo_gen90_ssot.sqlite` database. Moving to Option A would require a significant migration of the existing 9,859 documents.
- **Recommendation**: Start with **Option B** (Unified DB with WAL and `port` column) as it aligns with the current SSOT structure. If write contention becomes a proven bottleneck, migrate to **Option A** (8 separate files).
