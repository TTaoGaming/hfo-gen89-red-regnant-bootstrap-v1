import { chromium } from '@playwright/test';
import fs from 'fs';

const BASE_URL = 'http://localhost:8090/hfo_gen_89_hot_obsidian_forge/1_silver/projects/omega_v13_microkernel';
const PAGE_URL = `${BASE_URL}/demo_2026-02-20_1619.html`;

(async () => {
    console.log('='.repeat(60));
    console.log('  OMEGA v13 DEMO GOLDEN MASTER TEST');
    console.log('  Input: WIN_20260220_14_09_04_Pro.mp4');
    console.log('  Server:', BASE_URL);
    console.log('='.repeat(60));

    const browser = await chromium.launch({
        channel: 'chrome',
        headless: false, // Headful so video + WebGL render correctly
        args: [
            '--autoplay-policy=no-user-gesture-required',
            '--no-sandbox',
            '--disable-setuid-sandbox',
        ],
    });

    const page = await browser.newPage();

    // Capture console output from the page
    page.on('console', msg => {
        console.log(`[page][${msg.type()}] ${msg.text()}`);
    });
    page.on('pageerror', err => {
        console.error(`[page][ERROR] ${err.message}`);
    });
    page.on('requestfailed', request => {
        console.log(`[page][requestfailed] ${request.url()} ${request.failure()?.errorText}`);
    });
    page.on('response', response => {
        if (response.status() === 404) {
            console.log(`[page][404] ${response.url()}`);
        }
    });

    // Inject script to mock getUserMedia and feed the MP4
    await page.addInitScript(() => {
        const video = document.createElement('video');
        video.src = './WIN_20260220_14_09_04_Pro.mp4';
        video.loop = true;
        video.muted = true;
        video.crossOrigin = 'anonymous';
        video.style.display = 'none';
        document.addEventListener('DOMContentLoaded', () => document.body.appendChild(video));
        video.play().catch(e => console.error('Video play failed:', e));
        
        // Mock getUserMedia
        if (!navigator.mediaDevices) navigator.mediaDevices = {};
        Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {
            value: async () => {
                console.log('[mock] getUserMedia called, returning MP4 stream');
                if (video.readyState < 3) {
                    await new Promise(r => video.oncanplay = r);
                }
                // captureStream() is available on HTMLMediaElement
                return video.captureStream();
            },
            writable: true
        });
    });

    console.log('\n[runner] Navigating to', PAGE_URL);
    await page.goto(PAGE_URL, { waitUntil: 'domcontentloaded' });

    // Wait for the user to click "START CAMERA" or simulate it
    // The demo has a Shell UI. Let's wait for the button and click it.
    console.log('[runner] Waiting for START CAMERA button...');
    try {
        const startBtn = await page.waitForSelector('button:has-text("START CAMERA")', { timeout: 5000 });
        if (startBtn) {
            console.log('[runner] Clicking START CAMERA...');
            await startBtn.click();
        }
    } catch (e) {
        console.log('[runner] No START CAMERA button found, assuming auto-start or already started.');
    }

    // Wait for MediaPipe to start tracking (HUD fps > 0 or pos updates)
    console.log('[runner] Waiting for MediaPipe tracking (HUD pos update)...');
    try {
        await page.waitForFunction(() => {
            const pos = document.getElementById('hud-pos');
            return pos && pos.textContent && pos.textContent !== 'pos: –';
        }, { timeout: 90000 });
        console.log('[runner] Tracking active!');
    } catch (e) {
        console.error('[runner] Tracking failed to start within 90s.');
        await page.screenshot({ path: 'test-results/demo_golden_timeout.png' });
        await browser.close();
        process.exit(1);
    }

    // Wait for a gesture (e.g., COMMIT state)
    console.log('[runner] Waiting for COMMIT gesture...');
    try {
        await page.waitForFunction(() => {
            const state = document.getElementById('hud-state');
            return state && state.textContent && state.textContent.includes('COMMIT');
        }, { timeout: 30000 });
        console.log('[runner] COMMIT gesture detected!');
    } catch (e) {
        console.error('[runner] COMMIT gesture not detected within 30s.');
    }

    // Take a screenshot during the gesture
    console.log('[runner] Taking screenshot...');
    if (!fs.existsSync('test-results')) fs.mkdirSync('test-results');
    await page.screenshot({ path: 'test-results/demo_golden_interaction.png', fullPage: true });
    console.log('[runner] Screenshot saved to test-results/demo_golden_interaction.png');

    // Wait a bit more to capture drawing
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'test-results/demo_golden_interaction_after.png', fullPage: true });
    console.log('[runner] Second screenshot saved to test-results/demo_golden_interaction_after.png');

    await browser.close();
    console.log('[runner] Test complete.');
})();
