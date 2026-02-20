/**
 * omega_pointer.spec.ts
 *
 * SBE / ATDD specification for the HFO Omega v13 pointer pipeline.
 *
 * Specification-by-Example tiers:
 *   T1 – INVARIANT: gate conditions that MUST NOT fail ever
 *   T2 – HAPPY PATH: core desired behaviour
 *   T3 – COAST / PARTIAL LOSS: degraded-tracking behaviour
 *   T4 – PERFORMANCE BUDGET
 *
 * Architecture under test:
 *   omegaInjectFrame(hands)
 *     → globalEventBus.publish('FRAME_PROCESSED')
 *     → GestureFSMPlugin.onFrameProcessed  (same bus — unified in bootstrap)
 *     → globalEventBus.publish('POINTER_UPDATE', { handId, x, y, isPinching })
 *     → W3CPointerFabric.processLandmark   (Kalman filter applied)
 *     → iframe.contentWindow.postMessage({ type:'SYNTHETIC_POINTER_EVENT', … })
 *     → tldraw_layer.html symbiote agent
 *     → document.elementFromPoint  →  PointerEvent dispatched to tldraw
 *
 * Same-origin contract: localhost:8090 serves both parent and iframe.
 * Playwright can therefore evaluate JS inside the iframe, which we use to
 * capture PointerEvents for assertion.
 *
 * No-drift invariant (the mission-critical one):
 *   Index finger at normalised (nx, ny) in [0,1]²
 *   ⟹ pointermove inside tldraw arrives at
 *       clientX ≈ nx × viewport.width  ± DRIFT_TOLERANCE_PX
 *       clientY ≈ ny × viewport.height ± DRIFT_TOLERANCE_PX
 *   Proof:  rawPixelX = nx × W
 *           Kalman frame-1 initialises to measurement exactly → smoothed = rawPixelX
 *           iframe.getBoundingClientRect() = {left:0,top:0,w:W,h:H}  (layer_manager: fixed,top:0,left:0,100vw,100vh)
 *           iframeX = rawPixelX − 0 = rawPixelX
 *           ∴ drift = |smoothed − rawPixelX| = 0  (frame 1, no Kalman history)
 *           tolerance set to 2px to absorb float round-trip.
 */

import { test, expect, Page, Frame } from '@playwright/test';

// ─── constants ───────────────────────────────────────────────────────────────
const DEMO_URL        = 'http://localhost:8090/index_demo2.html';
const VIEWPORT_W      = 1280;
const VIEWPORT_H      = 720;
const DRIFT_TOLERANCE = 2;   // px — float round-trip only (Kalman exact on frame 1)
// Fake-timestamp helpers: inject N frames advancing 10 ms each.
// 12 × 10 ms = 120 ms > 100 ms default dwell → guaranteed transition.
const FSM_FRAME_STEP_MS  = 10;  // ms advance per injected frame
const FSM_READY_FRAMES   = 12;  // frames to reach IDLE → READY
const FSM_COMMIT_FRAMES  = 12;  // frames to reach READY → COMMIT_POINTER
const FSM_RELEASE_FRAMES = 12;  // frames to release COMMIT → READY
const POSTMSG_TIMEOUT = 500; // ms to wait for postMessage delivery

// ─── helpers ─────────────────────────────────────────────────────────────────

/** Wait for the demo + tldraw to be fully bootstrapped */
async function bootstrap(page: Page): Promise<void> {
    // Arm the tldraw-mounted listener BEFORE navigating so we don't miss it
    const tldrawMounted = page.waitForEvent('console', {
        predicate: msg => msg.text().includes('[tldraw-bundle] tldraw mounted'),
        timeout: 30_000,
    });

    await page.goto(DEMO_URL, { waitUntil: 'domcontentloaded' });

    // Wait for the harness to be ready (supervisor + plugins started)
    await page.waitForFunction(() =>
        typeof (window as any).omegaInjectFrame === 'function' &&
        typeof (window as any).__omegaExports?.globalEventBus === 'object'
    , { timeout: 15_000 });

    // Wait for tldraw to mount inside the iframe (React tree rendered)
    await tldrawMounted;

    // Extra tick — symbiote event listeners registered after tldraw.css/JS parse
    await page.waitForTimeout(300);
}

/** Return the tldraw iframe Frame (same-origin, accessible) */
function tldrawFrame(page: Page): Frame {
    const f = page.frames().find(f => f.url().includes('tldraw_layer'));
    if (!f) throw new Error('tldraw_layer iframe not found — check bootstrap');
    return f;
}

/** Inject capture listeners into the tldraw iframe.  Call once per test. */
async function armIframeCapture(iframe: Frame): Promise<void> {
    await iframe.evaluate(() => {
        (window as any).__omega_captured = [];
        for (const evtType of ['pointermove', 'pointerdown', 'pointerup', 'pointercancel']) {
            document.addEventListener(evtType, (e: Event) => {
                const pe = e as PointerEvent;
                (window as any).__omega_captured.push({
                    type:      pe.type,
                    clientX:   pe.clientX,
                    clientY:   pe.clientY,
                    pointerId: pe.pointerId,
                    buttons:   pe.buttons,
                    pressure:  pe.pressure,
                    ts:        pe.timeStamp,
                });
            }, { capture: true });
        }
    });
}

/** Drain the captured event queue from the iframe */
async function drainCapture(iframe: Frame): Promise<{
    type: string, clientX: number, clientY: number,
    pointerId: number, buttons: number, pressure: number
}[]> {
    return iframe.evaluate(() => {
        const evts = [...(window as any).__omega_captured];
        (window as any).__omega_captured = [];
        return evts;
    });
}

/** Wait for at least `count` captured events of `type` in the iframe */
async function waitForIframeEvents(
    iframe: Frame, type: string, count = 1, timeoutMs = POSTMSG_TIMEOUT
): Promise<void> {
    await iframe.waitForFunction(
        ({ type, count }) =>
            ((window as any).__omega_captured as any[])
                .filter(e => e.type === type).length >= count,
        { type, count },
        { timeout: timeoutMs }
    );
}

/** Drive the FSM from IDLE to READY via ms-based dwell.
 *  Injects FSM_READY_FRAMES frames with fake timestamps spaced FSM_FRAME_STEP_MS apart
 *  so the ms accumulator reaches the 100 ms threshold regardless of test execution speed. */
async function driveToReady(page: Page): Promise<void> {
    const baseT: number = await page.evaluate(() => performance.now());
    for (let i = 0; i < FSM_READY_FRAMES; i++) {
        await page.evaluate(
            (args: { baseT: number; i: number; step: number }) =>
                (window as any).omegaInjectFrame([{
                    handId: 0, x: 0.5, y: 0.5, gesture: 'open_palm', confidence: 0.9,
                    frameTimeMs: args.baseT + args.i * args.step
                }]),
            { baseT, i, step: FSM_FRAME_STEP_MS }
        );
    }
}

/** Drive the FSM from READY to COMMIT_POINTER via ms-based dwell. */
async function driveToCommit(page: Page): Promise<void> {
    const baseT: number = await page.evaluate(() => performance.now());
    for (let i = 0; i < FSM_COMMIT_FRAMES; i++) {
        await page.evaluate(
            (args: { baseT: number; i: number; step: number }) =>
                (window as any).omegaInjectFrame([{
                    handId: 0, x: 0.5, y: 0.5, gesture: 'pointer_up', confidence: 0.9,
                    frameTimeMs: args.baseT + args.i * args.step
                }]),
            { baseT, i, step: FSM_FRAME_STEP_MS }
        );
    }
}

/** Drive the FSM from COMMIT back to READY (release gesture). */
async function driveRelease(page: Page): Promise<void> {
    const baseT: number = await page.evaluate(() => performance.now());
    for (let i = 0; i < FSM_RELEASE_FRAMES; i++) {
        await page.evaluate(
            (args: { baseT: number; i: number; step: number }) =>
                (window as any).omegaInjectFrame([{
                    handId: 0, x: 0.5, y: 0.5, gesture: 'open_palm', confidence: 0.9,
                    frameTimeMs: args.baseT + args.i * args.step
                }]),
            { baseT, i, step: FSM_FRAME_STEP_MS }
        );
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// T1 — INVARIANT SCENARIOS
// These MUST NOT fail.  Any failure here = regression blocker.
// ─────────────────────────────────────────────────────────────────────────────

test.describe('T1 · Invariants', () => {

    test.beforeEach(async ({ page }) => {
        await page.setViewportSize({ width: VIEWPORT_W, height: VIEWPORT_H });
        await bootstrap(page);
    });

    /**
     * I1 — Pipeline wired
     * Given: demo is bootstrapped (all plugins started, tldraw mounted)
     * When:  a single FRAME_PROCESSED is published with one hand
     * Then:  POINTER_UPDATE fires on the event bus AND a postMessage
     *        SYNTHETIC_POINTER_EVENT is delivered inside the tldraw iframe
     */
    test('I1 · pipeline wired — FRAME_PROCESSED propagates to iframe postMessage', async ({ page }) => {
        const iframe = tldrawFrame(page);
        await armIframeCapture(iframe);

        await page.evaluate(() =>
            (window as any).omegaInjectFrame([
                { handId: 0, x: 0.5, y: 0.5, gesture: 'open_palm', confidence: 0.9 }
            ])
        );

        await waitForIframeEvents(iframe, 'pointermove', 1);
        const evts = await drainCapture(iframe);

        expect(evts.filter(e => e.type === 'pointermove').length).toBeGreaterThanOrEqual(1);
    });

    /**
     * I2 · No-drift
     * Given: viewport 1280×720, iframe positioned at fixed top:0 left:0 100vw 100vh
     * When:  index finger at normalised (nx=0.25, ny=0.75) — deliberate off-centre to
     *        catch any translate/scale bug
     * Then:  pointermove arrives inside tldraw at
     *           clientX = nx × 1280 ± DRIFT_TOLERANCE
     *           clientY = ny × 720  ± DRIFT_TOLERANCE
     *        (Kalman initialises to measurement exactly on frame 1 — zero smoothing lag)
     *
     * This is THE mission-critical invariant.  "Where my index finger is = pointer."
     */
    test('I2 · no-drift — finger at (0.25, 0.75) → pointermove ≤2px from expected', async ({ page }) => {
        const nx = 0.25;
        const ny = 0.75;
        const expectedX = nx * VIEWPORT_W;   // 320
        const expectedY = ny * VIEWPORT_H;   // 540

        const iframe = tldrawFrame(page);
        await armIframeCapture(iframe);

        await page.evaluate(([nx, ny]) =>
            (window as any).omegaInjectFrame([
                { handId: 0, x: nx, y: ny, gesture: 'open_palm', confidence: 0.9 }
            ]),
            [nx, ny]
        );

        await waitForIframeEvents(iframe, 'pointermove', 1);
        const evts = await drainCapture(iframe);
        const move = evts.find(e => e.type === 'pointermove');
        expect(move, 'pointermove must arrive').toBeTruthy();

        expect(Math.abs(move!.clientX - expectedX)).toBeLessThanOrEqual(DRIFT_TOLERANCE);
        expect(Math.abs(move!.clientY - expectedY)).toBeLessThanOrEqual(DRIFT_TOLERANCE);
    });

    /**
     * I2b · No-drift sweep — four corners + centre
     * Ensures no per-quadrant transform bug (e.g. wrong half-width offset).
     */
    for (const { label, nx, ny } of [
        { label: 'top-left',    nx: 0.0, ny: 0.0 },
        { label: 'top-right',   nx: 1.0, ny: 0.0 },
        { label: 'bottom-left', nx: 0.0, ny: 1.0 },
        { label: 'bottom-right',nx: 1.0, ny: 1.0 },
        { label: 'centre',      nx: 0.5, ny: 0.5 },
    ]) {
        test(`I2b · no-drift ${label} (nx=${nx}, ny=${ny})`, async ({ page }) => {
            // Clamp to viewport max (1.0×W = W px, element at W is just outside; clamp to W)
            const expectedX = Math.min(nx * VIEWPORT_W, VIEWPORT_W - 1);
            const expectedY = Math.min(ny * VIEWPORT_H, VIEWPORT_H - 1);

            const iframe = tldrawFrame(page);
            await armIframeCapture(iframe);

            await page.evaluate(([nx, ny]) =>
                (window as any).omegaInjectFrame([
                    { handId: 0, x: nx, y: ny, gesture: 'open_palm', confidence: 0.9 }
                ]),
                [nx, ny]
            );

            await waitForIframeEvents(iframe, 'pointermove', 1);
            const evts = await drainCapture(iframe);
            const move = evts.find(e => e.type === 'pointermove');
            expect(move).toBeTruthy();
            expect(Math.abs(move!.clientX - expectedX)).toBeLessThanOrEqual(DRIFT_TOLERANCE);
            expect(Math.abs(move!.clientY - expectedY)).toBeLessThanOrEqual(DRIFT_TOLERANCE);
        });
    }

    /**
     * I3 · Multi-hand — no pointer ID collision
     * Given: two hands active simultaneously
     * When:  FRAME_PROCESSED with handId:0 at (0.3, 0.5) and handId:1 at (0.7, 0.5)
     * Then:  two separate pointermove events arrive in tldraw with distinct pointerIds
     *        pointerIds must be POINTER_ID_BASE+0=10000 and POINTER_ID_BASE+1=10001
     */
    test('I3 · multi-hand — two distinct pointerIds, no collision', async ({ page }) => {
        const iframe = tldrawFrame(page);
        await armIframeCapture(iframe);

        await page.evaluate(() =>
            (window as any).omegaInjectFrame([
                { handId: 0, x: 0.3, y: 0.5, gesture: 'open_palm', confidence: 0.9 },
                { handId: 1, x: 0.7, y: 0.5, gesture: 'open_palm', confidence: 0.9 },
            ])
        );

        await waitForIframeEvents(iframe, 'pointermove', 2);
        const evts = await drainCapture(iframe);
        const moves = evts.filter(e => e.type === 'pointermove');

        const ids = new Set(moves.map(e => e.pointerId));
        expect(ids.size).toBeGreaterThanOrEqual(2);
        expect(ids.has(10000)).toBe(true);
        expect(ids.has(10001)).toBe(true);
    });

    /**
     * I4 · Buses unified — supervisor event bus === globalEventBus
     * Given: bootstrap complete
     * When:  supervisor.getEventBus() is compared to __omegaExports.globalEventBus
     * Then:  they are the SAME instance (reference equality)
     *        If they differ, GestureFSMPlugin would never receive FRAME_PROCESSED.
     */
    test('I4 · event bus not forked — supervisor bus === globalEventBus', async ({ page }) => {
        const sameInstance = await page.evaluate(() => {
            const bus = (window as any).__omegaExports.globalEventBus;
            const supBus = (window as any).__omegaExports.supervisor.getEventBus();
            return bus === supBus;
        });
        expect(sameInstance).toBe(true);
    });

});

// ─────────────────────────────────────────────────────────────────────────────
// T2 — HAPPY PATH
// ─────────────────────────────────────────────────────────────────────────────

test.describe('T2 · Happy path', () => {

    test.beforeEach(async ({ page }) => {
        await page.setViewportSize({ width: VIEWPORT_W, height: VIEWPORT_H });
        await bootstrap(page);
    });

    /**
     * H1 · FSM IDLE → READY transition
     * Given: FSM starts in IDLE
     * When:  16 × open_palm frames at confidence 0.9  (dwell_limit_ready = 15)
     * Then:  STATE_CHANGE { from:'IDLE', to:'READY' } fires on the event bus
     */
    test('H1 · FSM IDLE → READY after open_palm dwell', async ({ page }) => {
        // Wire state logger before driving frames
        await page.evaluate(() => {
            (window as any).__stateLog = [];
            (window as any).__omegaExports.globalEventBus.subscribe(
                'STATE_CHANGE',
                (d: any) => (window as any).__stateLog.push({ from: d.previousState, to: d.currentState })
            );
        });

        await driveToReady(page);

        const stateLog = await page.evaluate(() => (window as any).__stateLog);
        expect(stateLog.some((s: any) => s.from === 'IDLE' && s.to === 'READY')).toBe(true);
    });

    /**
     * H2 · FSM READY → COMMIT → pointerdown in tldraw
     * Given: FSM in READY state
     * When:  11 × pointer_up frames  (dwell_limit_commit = 10)
     * Then:  STATE_CHANGE { from:'READY', to:'COMMIT_POINTER' } fires
     *        AND pointerdown arrives in the tldraw iframe (buttons=1)
     */
    test('H2 · FSM READY → COMMIT_POINTER → pointerdown in tldraw', async ({ page }) => {
        const iframe = tldrawFrame(page);
        await armIframeCapture(iframe);
        await driveToReady(page);

        await driveToCommit(page);

        await waitForIframeEvents(iframe, 'pointerdown', 1);
        const evts = await drainCapture(iframe);
        const down = evts.find(e => e.type === 'pointerdown');
        expect(down, 'pointerdown must fire on COMMIT').toBeTruthy();
        expect(down!.buttons).toBe(1);
        expect(down!.pressure).toBeGreaterThan(0);
    });

    /**
     * H3 · Full draw gesture: IDLE → READY → COMMIT → READY (pointerdown + pointerup)
     * Given: fresh FSM
     * When:  open_palm dwell → pointer_up dwell → open_palm dwell (release)
     * Then:  pointerdown fires, then pointerup fires
     *        Simulates a complete draw stroke in tldraw
     */
    test('H3 · complete draw gesture — pointerdown then pointerup', async ({ page }) => {
        const iframe = tldrawFrame(page);
        await armIframeCapture(iframe);
        await driveToReady(page);
        await driveToCommit(page);
        await waitForIframeEvents(iframe, 'pointerdown', 1);

        await driveRelease(page);
        await waitForIframeEvents(iframe, 'pointerup', 1);

        const evts = await drainCapture(iframe);
        const down = evts.find(e => e.type === 'pointerdown');
        const up   = evts.find(e => e.type === 'pointerup');
        expect(down).toBeTruthy();
        expect(up).toBeTruthy();
        expect(up!.pointerId).toBe(down!.pointerId);   // same pointer closes the stroke
    });

    /**
     * H4 · Pointer position tracks finger movement across frames
     * Given: consecutive frames moving from left (0.2) to right (0.8)
     * When:  5 pointermove frames emitted
     * Then:  clientX in tldraw increases monotonically (hand moving right)
     */
    test('H4 · pointer tracks movement — clientX increases when finger moves right', async ({ page }) => {
        const iframe = tldrawFrame(page);
        await armIframeCapture(iframe);

        const xs = [0.2, 0.35, 0.5, 0.65, 0.8];
        for (const x of xs) {
            await page.evaluate((nx) =>
                (window as any).omegaInjectFrame([
                    { handId: 0, x: nx, y: 0.5, gesture: 'open_palm', confidence: 0.9 }
                ]),
                x
            );
        }

        await waitForIframeEvents(iframe, 'pointermove', xs.length);
        const evts = await drainCapture(iframe);
        const moves = evts.filter(e => e.type === 'pointermove' && e.pointerId === 10000);

        // clientX should generally increase (Kalman may slightly lag, allow 1 reversal max)
        let reversals = 0;
        for (let i = 1; i < moves.length; i++) {
            if (moves[i].clientX < moves[i-1].clientX) reversals++;
        }
        expect(reversals).toBeLessThanOrEqual(1);  // Kalman smoothing may cause 1 lag step

        // First and last must clearly move right
        expect(moves[moves.length - 1].clientX).toBeGreaterThan(moves[0].clientX);
    });

});

// ─────────────────────────────────────────────────────────────────────────────
// T3 — COAST / PARTIAL LOSS
// ─────────────────────────────────────────────────────────────────────────────

test.describe('T3 · Coast behaviour', () => {

    test.beforeEach(async ({ page }) => {
        await page.setViewportSize({ width: VIEWPORT_W, height: VIEWPORT_H });
        await bootstrap(page);
    });

    /**
     * C1 · Coast propagates last known position (no snap to 0,0)
     * Given: hand established at (0.5, 0.5), then tracking lost (no hands)
     * When:  empty FRAME_PROCESSED published
     * Then:  POINTER_COAST fires on the bus AND pointer does NOT snap to (0,0)
     */
    test('C1 · coast — POINTER_COAST fires and pointer does not snap to origin', async ({ page }) => {
        const iframe = tldrawFrame(page);
        await armIframeCapture(iframe);

        // Wire coast logger
        await page.evaluate(() => {
            (window as any).__coastLog = [];
            (window as any).__omegaExports.globalEventBus.subscribe(
                'POINTER_COAST',
                (d: any) => (window as any).__coastLog.push(d)
            );
        });

        // Establish hand at centre (initialises Kalman filter)
        await page.evaluate(() =>
            (window as any).omegaInjectFrame([
                { handId: 0, x: 0.5, y: 0.5, gesture: 'open_palm', confidence: 0.9 }
            ])
        );

        // Lose the hand — triggers POINTER_COAST
        await page.evaluate(() =>
            (window as any).omegaInjectFrame([])
        );

        // POINTER_COAST must have been published
        await page.waitForFunction(() => (window as any).__coastLog?.length > 0, { timeout: 500 });
        const coastLog = await page.evaluate(() => (window as any).__coastLog);
        expect(coastLog.length).toBeGreaterThan(0);
        expect(coastLog[0].handId).toBe(0);

        // The iframe must NOT have received a pointermove snapped to (0,0)
        await page.waitForTimeout(50);
        const evts = await drainCapture(iframe);
        const snappedToOrigin = evts.filter(e => e.type === 'pointermove' && e.clientX < 10 && e.clientY < 10);
        expect(snappedToOrigin.length).toBe(0);
    });

});

// ─────────────────────────────────────────────────────────────────────────────
// T4 — PERFORMANCE BUDGET
// ─────────────────────────────────────────────────────────────────────────────

test.describe('T4 · Performance budget', () => {

    test.beforeEach(async ({ page }) => {
        await page.setViewportSize({ width: VIEWPORT_W, height: VIEWPORT_H });
        await bootstrap(page);
    });

    /**
     * P1 · 60 frames processed in < 100ms wall time
     * Given: demo bootstrapped
     * When:  60 consecutive FRAME_PROCESSED injections (1 hand, centre)
     * Then:  wall time < 100ms  (target: 60fps = 16.7ms/frame → 60×16.7 = 1002ms budget,
     *        but JS pipeline only — not camera latency — should be << 2ms/frame)
     */
    test('P1 · throughput — 60 frames processed in < 100ms', async ({ page }) => {
        const elapsed = await page.evaluate(() => {
            const t0 = performance.now();
            for (let i = 0; i < 60; i++) {
                (window as any).omegaInjectFrame([
                    { handId: 0, x: 0.5, y: 0.5, gesture: 'open_palm', confidence: 0.9 }
                ]);
            }
            return performance.now() - t0;
        });
        expect(elapsed).toBeLessThan(100);
    });

    /**
     * P2 · FSM state machine + Kalman combined < 5ms for a single frame
     */
    test('P2 · per-frame budget — single frame pipeline < 5ms', async ({ page }) => {
        const elapsed = await page.evaluate(() => {
            const t0 = performance.now();
            (window as any).omegaInjectFrame([
                { handId: 0, x: 0.5, y: 0.5, gesture: 'open_palm', confidence: 0.9 }
            ]);
            return performance.now() - t0;
        });
        expect(elapsed).toBeLessThan(5);
    });

});
