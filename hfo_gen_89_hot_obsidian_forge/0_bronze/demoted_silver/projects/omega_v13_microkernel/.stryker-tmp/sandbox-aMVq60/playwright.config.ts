// @ts-nocheck
import { defineConfig } from '@playwright/test';

export default defineConfig({
    testDir: './tests',
    testIgnore: ['**/launch_invariants.spec.ts'],
    timeout: 30_000,
    expect: { timeout: 5_000 },
    fullyParallel: false,  // iframe pointer state is shared — run sequentially
    use: {
        baseURL: 'http://localhost:8090',
        headless: true,
        viewport: { width: 1280, height: 720 },
        // Same-origin: no CORS headaches, iframe accessible via page.frames()
        bypassCSP: false,
    },
    webServer: {
        command: 'python -m http.server 8090',
        url: 'http://localhost:8090',
        reuseExistingServer: true,
        cwd: 'C:/hfoDev/hfo_gen_89_hot_obsidian_forge/1_silver/projects/omega_v13_microkernel',
    },
    projects: [
        { name: 'chromium', use: { channel: 'chromium' } },
    ],
    reporter: [['list'], ['html', { open: 'never', outputFolder: 'test-results/html' }]],
});
