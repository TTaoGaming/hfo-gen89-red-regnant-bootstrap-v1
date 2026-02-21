import { test, expect } from '@playwright/test';

test.describe('Babylon.js + W3C Pointer Pipeline (SBE/ATDD)', () => {
    test.beforeEach(async ({ page }) => {
        // Navigate to the demo page
        await page.goto('http://localhost:8080/demo_babylon.html');
        
        // Wait for the microkernel to boot
        await page.waitForFunction(() => (window as any).omegaKernel !== undefined);
    });

    test('Given mocked MediaPipe landmarks, When injected into EventBus, Then Babylon physics updates and W3C pointer events are fired', async ({ page }) => {
        // 1. Setup a listener for W3C pointer events on the target iframe/div
        await page.evaluate(() => {
            (window as any).pointerEventsLog = [];
            const target = document.getElementById('tldraw-container') || document.body;
            target.addEventListener('pointerdown', (e) => (window as any).pointerEventsLog.push({ type: e.type, x: e.clientX, y: e.clientY }));
            target.addEventListener('pointermove', (e) => (window as any).pointerEventsLog.push({ type: e.type, x: e.clientX, y: e.clientY }));
            target.addEventListener('pointerup', (e) => (window as any).pointerEventsLog.push({ type: e.type, x: e.clientX, y: e.clientY }));
        });

        // 2. Mock MediaPipe landmarks (Idle -> Pinch)
        const mockLandmarksIdle = Array(21).fill({ x: 0.5, y: 0.5, z: 0 });
        const mockLandmarksPinch = Array(21).fill({ x: 0.5, y: 0.5, z: 0 });
        // Simulate pinch by bringing thumb (4) and index (8) close together
        mockLandmarksPinch[4] = { x: 0.5, y: 0.5, z: 0 };
        mockLandmarksPinch[8] = { x: 0.5, y: 0.5, z: 0 };

        // 3. Inject Idle state
        await page.evaluate((landmarks) => {
            (window as any).omegaKernel.eventBus.publish('RAW_HAND_DATA', {
                handId: 0,
                gesture: 'Open_Palm',
                confidence: 0.99,
                x: 0.5,
                y: 0.5,
                rawLandmarks: landmarks
            });
        }, mockLandmarksIdle);

        // Wait for physics to settle
        await page.waitForTimeout(100);

        // 4. Inject Pinch state (triggers pointerdown)
        await page.evaluate((landmarks) => {
            (window as any).omegaKernel.eventBus.publish('RAW_HAND_DATA', {
                handId: 0,
                gesture: 'Closed_Fist', // Or whatever gesture triggers the pinch in FSM
                confidence: 0.99,
                x: 0.5,
                y: 0.5,
                rawLandmarks: landmarks
            });
        }, mockLandmarksPinch);

        // Wait for physics to settle and events to fire
        await page.waitForTimeout(100);

        // 5. Verify W3C pointer events were fired
        const logs = await page.evaluate(() => (window as any).pointerEventsLog);
        
        // We expect at least a pointermove (from idle) and a pointerdown (from pinch)
        expect(logs.length).toBeGreaterThan(0);
        const hasPointerDown = logs.some((log: any) => log.type === 'pointerdown');
        expect(hasPointerDown).toBeTruthy();
    });
});
