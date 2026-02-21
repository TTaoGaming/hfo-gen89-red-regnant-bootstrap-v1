"""
v15_register_tiles.py — Bulk-register all Omega v15 tiles into obsidian_blackboard.

Classification:
  hardened       = Stryker-verified (kalman_filter, event_bus) — keep existing scores
  v15_target     = Real tiles to harden, sourced from v13 proven code
  v13_potemkin   = Exists in v13 but facade/untestable/not in v15 canon
  v13_antipattern = Known architectural defect (antipatterns from arch review)

Based on:
  - Pareto Blueprint (3 Pillars, 5 Core Pieces)
  - Architectural Review (4 Elite Patterns, 6 Lethal Antipatterns)
  - Source file inventory
"""

import sqlite3

DB = "C:/hfoDev/hfo_gen_90_hot_obsidian_forge/2_gold/2_resources/hfo_gen90_ssot.sqlite"

# (tile_key, source_file, status, priority, notes)
# priority: 10=highest, 1=lowest
TILES = [
    # ── ALREADY HARDENED ──────────────────────────────────────────────────────
    # (skip — already in DB with scores)

    # ── V15 TARGETS: Pareto Core Pieces (must harden) ────────────────────────
    ("foveated_cropper",         "foveated_cropper.ts",         "v15_target", 15,
     "Pareto Pillar 1 — Foveated ROI Cropping. 256x256 bounding box crop for thermal survival on phone."),

    ("biological_raycaster",     "biological_raycaster.ts",     "v15_target", 14,
     "Pareto Pillar 1 — Scale-Invariant Biological Raycasting. Pinch/palm anatomical ruler."),

    ("webrtc_udp_transport",     "webrtc_udp_transport.ts",     "v15_target", 13,
     "Pareto Pillar 2 — WebRTC UDP ordered:false maxRetransmits:0. Zero-latency transport."),

    ("symbiote_injector_plugin", "symbiote_injector_plugin.ts", "v15_target", 12,
     "Pareto Pillar 2 — W3C Level 3 Symbiote Injector. Translate UDP math to iframe pointer events."),

    ("iframe_delivery_adapter",  "iframe_delivery_adapter.ts",  "v15_target", 11,
     "Pareto Pillar 2 — Synthesizes pointerdown/pointermove with predictive lookahead arrays."),

    ("wood_grain_tuning",        "wood_grain_tuning.ts",        "v15_target", 10,
     "Pareto Pillar 3 — UserTuningProfile: Kalman+GA coefficients. Privacy-by-Math, GDPR-compliant."),

    # ── V15 TARGETS: Microkernel Core Tiles (infrastructure) ─────────────────
    ("plugin_supervisor",        "plugin_supervisor.ts",        "v15_target",  9,
     "Microkernel core — Plugin lifecycle, hot-swap, isolation. Critical path."),

    ("gesture_fsm",              "gesture_fsm.ts",              "v15_target",  8,
     "Core FSM — IDLE→READY→COMMIT_POINTER. Defense-in-depth state machine."),

    ("gesture_fsm_plugin",       "gesture_fsm_plugin.ts",       "v15_target",  7,
     "FSM plugin wrapper — loads gesture_fsm into microkernel. WARNING: imports omega_core_rs WASM."),

    ("w3c_pointer_fabric",       "w3c_pointer_fabric.ts",       "v15_target",  6,
     "W3C Pointer Fabric — shared data fabric for decoupled pointer event distribution."),

    ("visualization_plugin",     "visualization_plugin.ts",     "v15_target",  5,
     "Dot/ring visualization — state changes per hand. Synthesized synesthesia visual half."),

    ("temporal_rollup",          "temporal_rollup.ts",          "v15_target",  4,
     "Procedural observability — self-writing ADRs from floating-point matrix deltas."),

    # ── V13 ANTIPATTERNS: Real tiles with known defects requiring rewrite ─────
    ("audio_engine_plugin",      "audio_engine_plugin.ts",      "v13_antipattern", 3,
     "ANTIPATTERN: Zombie listener in destroy() — bind() ref not stored, never unsubscribed. "
     "ANTIPATTERN: Trusted Gesture trap — AudioContext muted on synthetic PointerEvent. "
     "Fix before Stryker: store boundOnStateChange, require physical tap to resume AudioContext."),

    ("behavioral_predictive_layer", "behavioral_predictive_layer.ts", "v13_antipattern", 2,
     "ANTIPATTERN(1): evolve() blocks main thread — must move to Web Worker. "
     "ANTIPATTERN(2): GC churn in simulatePrediction — Float32Array pre-alloc needed. "
     "ANTIPATTERN(3): Ground Truth Paradox — no real ground truth in prod, need Shadow Tracker. "
     "ANTIPATTERN(4): MAP-Elites Mirage — just a plain GA, not a real grid repertoire."),

    # ── V13 POTEMKIN VILLAGE: Exists but not v15 canon / untestable ──────────
    ("babylon_landmark_plugin",  "babylon_landmark_plugin.ts",  "v13_potemkin",  0,
     "Potemkin — Old Babylon.js integration. Not in v15 Pareto blueprint. Drop or replace."),

    ("babylon_physics",          "babylon_physics.ts",          "v13_potemkin",  0,
     "Potemkin — Old Babylon.js physics. Not in v15 arch. Replaced by Kalman+Havok on TV side."),

    ("gesture_fsm_rs_adapter",   "gesture_fsm_rs_adapter.ts",   "v13_potemkin",  0,
     "Potemkin — WASM adapter for gesture_fsm_rs. External binary, cannot Stryker. Facade."),

    ("mediapipe_vision_plugin",  "mediapipe_vision_plugin.ts",  "v13_potemkin",  0,
     "Potemkin — MediaPipe wrapper. External ML SDK, no pure-logic to mutation-test."),

    ("mediapipe_gesture",        "mediapipe_gesture.ts",        "v13_potemkin",  0,
     "Potemkin — MediaPipe gesture types/glue. Pure pass-through, no logic."),

    ("gesture_bridge",           "gesture_bridge.ts",           "v13_potemkin",  0,
     "Potemkin — Gesture bridge glue. Connects MediaPipe output to FSM input. Thin adapter."),

    ("shell",                    "shell.ts",                    "v13_potemkin",  0,
     "Potemkin — Top-level shell bootstrap. Glue code, no pure logic. Cannot unit test."),

    ("layer_manager",            "layer_manager.ts",            "v13_potemkin",  0,
     "Potemkin — Z-stack topology manager. DOM layout glue, low logic density."),

    ("hud_plugin",               "hud_plugin.ts",               "v13_potemkin",  0,
     "Potemkin — HUD overlay plugin. Visual-only, no pure testable logic."),

    ("overscan_canvas",          "overscan_canvas.ts",          "v13_potemkin",  0,
     "Potemkin — Canvas overscan utility. Thin DOM wrapper."),

    ("highlander_mutex_adapter", "highlander_mutex_adapter.ts", "v13_potemkin",  0,
     "Potemkin — Highlander mutex adapter. There-can-be-only-one pattern. Thin."),

    ("stillness_monitor_plugin", "stillness_monitor_plugin.ts", "v13_potemkin",  0,
     "Potemkin — Stillness monitor. Optional stability heuristic, not Pareto core."),

    ("video_throttle",           "video_throttle.ts",           "v13_potemkin",  0,
     "Potemkin — Video capture throttle. Media API wrapper, not unit testable."),

    ("behavioral_predictive_worker", "behavioral_predictive_worker.ts", "v13_potemkin", 0,
     "Potemkin — Web Worker counterpart for BPL. Currently empty/stub per arch review."),

    ("config_ui",                "config_ui.ts",                "v13_potemkin",  0,
     "Potemkin — Config UI form. DOM/form logic, not Stryker target."),

    ("symbiote_injector",        "symbiote_injector.ts",        "v13_potemkin",  0,
     "Potemkin — Raw injector (vs symbiote_injector_plugin). Thin inner class, covered by plugin test."),
]

conn = sqlite3.connect(DB)
cur = conn.cursor()

inserted = 0
skipped = 0
for tile_key, source_file, status, priority, notes in TILES:
    existing = cur.execute(
        "SELECT status, stryker_score FROM obsidian_blackboard WHERE tile_key = ?",
        (tile_key,)
    ).fetchone()

    if existing:
        # Never overwrite hardened tiles
        if existing[0] == "hardened":
            print(f"  [SKIP hardened]  {tile_key}")
            skipped += 1
            continue
        # Update status/priority/notes for existing non-hardened entries
        cur.execute(
            "UPDATE obsidian_blackboard SET status=?, priority=?, notes=?, updated_at=datetime('now') WHERE tile_key=?",
            (status, priority, notes, tile_key)
        )
        print(f"  [UPDATE {status:16}]  {tile_key}")
    else:
        cur.execute(
            "INSERT INTO obsidian_blackboard (tile_key, source_file, status, priority, notes, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
            (tile_key, source_file, status, priority, notes)
        )
        print(f"  [INSERT {status:16}]  {tile_key}")
        inserted += 1

conn.commit()
conn.close()

total = len(TILES)
print(f"\nDone. {inserted} inserted, {skipped} skipped (hardened), {total - inserted - skipped} updated.")
print(f"Total tiles registered: {inserted + skipped + (total - inserted - skipped)}")
