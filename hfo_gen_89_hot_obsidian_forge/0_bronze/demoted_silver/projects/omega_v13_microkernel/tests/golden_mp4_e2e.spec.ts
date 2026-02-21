import { test, expect } from '@playwright/test';

test('Golden MP4 triggers tldraw via W3C Pointer Events', async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'Fake video capture only works in Chromium');
    test.setTimeout(60000); // 60 seconds

    page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));

    // Navigate to the demo
    await page.goto('http://localhost:8090/demo_2026-02-20_1619.html');

    // Wait for the CTA button to appear
    console.log('Waiting for START CAMERA button...');
    await page.waitForSelector('#omega-cta-btn', { timeout: 10000 });

    // Inject the video and start MediaPipe directly
    console.log('Injecting golden MP4 and starting MediaPipe...');
    await page.evaluate(async () => {
        // Remove the CTA overlay
        const overlay = document.getElementById('omega-cta-overlay');
        if (overlay) overlay.remove();

        // Setup the video element
        const video = document.getElementById('omega-video-bg') as HTMLVideoElement;
        video.src = 'WIN_20260220_14_09_04_Pro.mp4';
        video.loop = true;
        video.muted = true;
        await video.play();

        // Start MediaPipe Vision Plugin
        const supervisor = (window as any).__omegaExports.supervisor;
        const vision = supervisor.plugins.get('MediaPipeVisionPlugin');
        await vision.startVideoFile();
    });

    // Wait for the video to start playing
    await page.waitForSelector('#omega-video-bg', { timeout: 10000 });

    // Log video time periodically
    const interval = setInterval(async () => {
        try {
            const time = await page.evaluate(() => {
                const v = document.getElementById('omega-video-bg') as HTMLVideoElement;
                return v ? v.currentTime : -1;
            });
            console.log('Video time:', time);
        } catch (e) {}
    }, 2000);

    // Wait for the state to change from IDLE to COMMIT (meaning a pinch gesture was recognized)
    console.log('Waiting for gesture COMMIT state...');
    await page.waitForFunction(() => {
        const hud = document.getElementById('hud-state');
        return hud && hud.textContent && hud.textContent.includes('COMMIT');
    }, { timeout: 45000 });
    console.log('Gesture COMMIT state reached!');

    clearInterval(interval);

    // Wait a bit for the stroke to be drawn
    await page.waitForTimeout(2000);

    // Take a screenshot
    await page.screenshot({ path: 'test-results/gesture_screenshot.png' });

    // Check if tldraw received any strokes
    const iframe = page.frameLocator('#omega-tldraw');
    const paths = await iframe.locator('path').count();
    console.log('Number of SVG paths in tldraw:', paths);
    
    expect(paths).toBeGreaterThan(0);
});
