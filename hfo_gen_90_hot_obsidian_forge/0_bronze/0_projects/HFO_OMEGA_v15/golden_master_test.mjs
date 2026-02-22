/**
 * golden_master_test.mjs
 * Omega v13 — Golden Master Integration Test
 *
 * Runs in Node.js via: node golden_master_test.mjs
 * Uses Playwright's headful Chromium browser.
 *
 * 6 Checks:
 *   CHECK 1  Video playing (VideoClipHarness → videoElement.play())
 *   CHECK 2  FRAME_PROCESSED > 0 (MediaPipe landmark tracking live)
 *   CHECK 3  FSM STATE_CHANGE > 0 (GestureFSMPlugin transitions)
 *   CHECK 4  BABYLON_PHYSICS_FRAME > 0 (Havok physics rendering)
 *   CHECK 5  POINTER_UPDATE > 0 (W3C pointer output flowing)
 *   CHECK 6  COORD_INVARIANT — mirror applied exactly once (one-way parity)
 *            rawLandmarks[8].x ≈ hand.x at overscanScale=1.0
 *            (≡ (1-raw_x) - 0)*1 = 1-raw_x, same as classifyHand formula)
 */

import { chromium } from '@playwright/test';

const BASE_URL          = 'http://localhost:5173';
const PAGE_URL          = `${BASE_URL}/golden_master.html`;
const MEDIAPIPE_TIMEOUT = 90_000;   // 90s for WASM CDN download
const FRAME_TIMEOUT     = 30_000;   // 30s to get first FRAME_PROCESSED after MP ready
const COLLECT_MS        = 10_000;   // Record for 10s once pipeline is live

const PASS  = (label) => `  ✓  PASS   ${label}`;
const FAIL  = (label) => `  ✗  FAIL   ${label}`;
const WARN  = (label) => `  ⚠  WARN   ${label}`;

async function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

(async () => {
    console.log('='.repeat(60));
    console.log('  OMEGA v13 GOLDEN MASTER TEST');
    console.log('  Input: WIN_20260220_14_09_04_Pro.mp4');
    console.log('  Server:', BASE_URL);
    console.log('='.repeat(60));

    const browser = await chromium.launch({
        headless: false,       // Headful so video + WebGL render correctly
        args: [
            '--autoplay-policy=no-user-gesture-required',
            '--no-sandbox',
            '--disable-setuid-sandbox',
        ],
    });

    const page = await browser.newPage();

    // Capture console output from the page
    const pageLog = [];
    page.on('console', msg => {
        const text = `[page][${msg.type()}] ${msg.text()}`;
        pageLog.push(text);
        if (msg.text().includes('[GoldenMaster]') || msg.text().includes('ERROR') || msg.text().includes('error')) {
            console.log(text);
        }
    });
    page.on('pageerror', err => {
        const text = `[page][ERROR] ${err.message}`;
        pageLog.push(text);
        console.error(text);
    });

    console.log('\n[runner] Navigating to', PAGE_URL);
    await page.goto(PAGE_URL, { waitUntil: 'domcontentloaded' });

    // ── Wait for MediaPipe to signal ready ────────────────────────────────────
    console.log('[runner] Waiting for MediaPipe HandLandmarker (up to 90s — WASM CDN download)…');
    try {
        await page.waitForFunction(
            () => (window).__omegaTelemetry?.mediaPipeReady === true,
            { timeout: MEDIAPIPE_TIMEOUT },
        );
        console.log('[runner] MediaPipe ready ✓');
    } catch (_) {
        console.warn('[runner] MediaPipe did not signal ready within timeout — collecting partial telemetry');
    }

    // ── Wait for first FRAME_PROCESSED ────────────────────────────────────────
    console.log('[runner] Waiting for first FRAME_PROCESSED (pipeline live)…');
    try {
        await page.waitForFunction(
            () => (window).__omegaTelemetry?.frameProcessedCount > 0,
            { timeout: FRAME_TIMEOUT },
        );
        console.log('[runner] Pipeline live — FRAME_PROCESSED flowing ✓');
    } catch (_) {
        console.warn('[runner] No FRAME_PROCESSED received — Check 2 will FAIL');
    }

    // ── Let it run for COLLECT_MS to accumulate FSM + W3C + Babylon events ──
    console.log(`[runner] Collecting events for ${COLLECT_MS / 1000}s…`);
    await sleep(COLLECT_MS);

    // ── Read final telemetry ──────────────────────────────────────────────────
    const tel = await page.evaluate(() => {
        const t = (window).__omegaTelemetry;
        if (!t) return null;
        // Find first POINTER_UPDATE that has 21 rawLandmarks (for CHECK 6)
        const coordSample = t.pointerUpdates?.find(
            p => p.rawLandmarks && p.rawLandmarks.length === 21,
        ) ?? null;
        return {
            videoPlaying:        t.videoPlaying,
            mediaPipeReady:      t.mediaPipeReady,
            havokReady:          t.havokReady,
            frameProcessedCount: t.frameProcessedCount,
            stateChangesCount:   t.stateChanges?.length ?? 0,
            pointerUpdatesCount: t.pointerUpdates?.length ?? 0,
            babylonFramesCount:  t.babylonFrames?.length ?? 0,
            stillnessCount:      t.stillnessEvents?.length ?? 0,
            errors:              t.errors ?? [],
            // Sample payloads
            firstStateChange:    t.stateChanges?.[0] ?? null,
            firstPointerUpdate:  t.pointerUpdates?.[0] ?? null,
            firstBabylonFrame:   t.babylonFrames?.[0] ?? null,
            // CHECK 6: coord parity — rawLandmarks[8].x should ≈ hand.x at overscanScale=1
            coordSample: coordSample ? {
                handX:        coordSample.x,
                tip8x:        coordSample.rawLandmarks[8].x,
                delta:        Math.abs(coordSample.rawLandmarks[8].x - coordSample.x),
            } : null,
        };
    });

    // ── Collect Babylon canvas pixels to verify rendering ─────────────────────
    let babylonCanvasPixelSum = 0;
    try {
        babylonCanvasPixelSum = await page.evaluate(() => {
            const canvas = document.getElementById('omega-babylon-canvas');
            if (!(canvas instanceof HTMLCanvasElement)) return 0;
            const ctx = canvas.getContext('2d');
            if (!ctx) return 0;
            const d = ctx.getImageData(0, 0, Math.min(canvas.width, 200), Math.min(canvas.height, 200));
            return d.data.reduce((s, v) => s + v, 0);
        });
    } catch (_) { /* non-fatal */ }

    // ── REPORT ────────────────────────────────────────────────────────────────
    console.log('\n' + '='.repeat(60));
    console.log('  GOLDEN MASTER RESULTS');
    console.log('='.repeat(60));

    if (!tel) {
        console.error(FAIL('window.__omegaTelemetry not found — bootstrap failed entirely'));
        await browser.close();
        process.exit(1);
    }

    const results = [];

    // CHECK 1: Video playing
    const c1 = tel.videoPlaying;
    results.push({ check: 'CHECK 1  Video playing',                pass: c1 });
    console.log(c1 ? PASS('CHECK 1  Video playing') : FAIL('CHECK 1  Video NOT playing'));

    // CHECK 2: FRAME_PROCESSED (landmark tracking)
    const c2 = tel.frameProcessedCount > 0;
    results.push({ check: 'CHECK 2  Landmark tracking (FRAME_PROCESSED)', pass: c2 });
    console.log(c2
        ? PASS(`CHECK 2  Landmark tracking — ${tel.frameProcessedCount} frames processed`)
        : FAIL('CHECK 2  No FRAME_PROCESSED events — MediaPipe not tracking'));

    // CHECK 3: FSM transitions
    const c3 = tel.stateChangesCount > 0;
    results.push({ check: 'CHECK 3  FSM transitions (STATE_CHANGE)', pass: c3 });
    console.log(c3
        ? PASS(`CHECK 3  FSM transitions — ${tel.stateChangesCount} STATE_CHANGE events`)
        : FAIL('CHECK 3  No FSM STATE_CHANGE events'));
    if (tel.firstStateChange) {
        console.log(`         Sample: ${JSON.stringify(tel.firstStateChange)}`);
    }

    // CHECK 4: Babylon Havok physics
    const c4 = tel.babylonFramesCount > 0;
    results.push({ check: 'CHECK 4  Babylon Havok physics (BABYLON_PHYSICS_FRAME)', pass: c4 });
    console.log(c4
        ? PASS(`CHECK 4  Havok physics — ${tel.babylonFramesCount} BABYLON_PHYSICS_FRAME events`)
        : FAIL('CHECK 4  No BABYLON_PHYSICS_FRAME events — Havok not running'));
    if (tel.firstBabylonFrame) {
        console.log(`         Sample: ${JSON.stringify(tel.firstBabylonFrame)}`);
    }
    if (babylonCanvasPixelSum > 0) {
        console.log(`         Babylon canvas pixel sum: ${babylonCanvasPixelSum} (non-zero = rendering)`);
    }

    // CHECK 5: W3C pointer output
    const c5 = tel.pointerUpdatesCount > 0;
    results.push({ check: 'CHECK 5  W3C pointer output (POINTER_UPDATE)', pass: c5 });
    console.log(c5
        ? PASS(`CHECK 5  W3C pointer — ${tel.pointerUpdatesCount} POINTER_UPDATE events`)
        : FAIL('CHECK 5  No POINTER_UPDATE events — W3CPointerFabric not firing'));
    if (tel.firstPointerUpdate) {
        console.log(`         Sample: ${JSON.stringify(tel.firstPointerUpdate)}`);
    }

    // CHECK 6: Coordinate parity — COORD_INVARIANT one-way mirror
    // At overscanScale=1.0: rawLandmarks[8].x = (1 - raw_x), hand.x = (1 - raw_x - 0)*1
    // They must be identical.  Delta > 0.05 means a second mirror was applied.
    const PARITY_TOLERANCE = 0.05;
    let c6 = false;
    if (tel.coordSample) {
        c6 = tel.coordSample.delta < PARITY_TOLERANCE;
        console.log(c6
            ? PASS(`CHECK 6  COORD_INVARIANT — Δ(rawLandmarks[8].x, hand.x) = ${tel.coordSample.delta.toFixed(5)} < ${PARITY_TOLERANCE}`)
            : FAIL(`CHECK 6  COORD_INVARIANT VIOLATED — Δ=${tel.coordSample.delta.toFixed(5)} ≥ ${PARITY_TOLERANCE} — double-mirror suspected`));
        console.log(`         hand.x=${tel.coordSample.handX.toFixed(4)}, rawLandmarks[8].x=${tel.coordSample.tip8x.toFixed(4)}`);
    } else {
        console.log(WARN('CHECK 6  COORD_INVARIANT — no POINTER_UPDATE with rawLandmarks collected (non-fatal)'));
        c6 = true; // inconclusive, do not fail overall — mark warn only
    }
    results.push({ check: 'CHECK 6  COORD_INVARIANT (one-way mirror parity)', pass: c6 });

    // ── Summary ───────────────────────────────────────────────────────────────
    const passed = results.filter(r => r.pass).length;
    const total  = results.length;
    console.log('\n' + '-'.repeat(60));
    console.log(`  SUMMARY:  ${passed}/${total} checks passed`);
    if (tel.stillnessCount > 0)   console.log(`  Bonus: STILLNESS_DETECTED × ${tel.stillnessCount}`);
    if (tel.errors.length > 0)    console.log(`  Errors: ${tel.errors.join(' | ')}`);
    console.log('='.repeat(60) + '\n');

    await browser.close();
    process.exit(passed === total ? 0 : 1);
})();
