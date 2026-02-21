/**
 * tldraw_entrypoint.tsx
 * Self-contained tldraw mount — bundled by esbuild → dist/tldraw_bundle.js
 * This bundle includes react + react-dom + tldraw in ONE file so there is
 * no dual-instance issue.  The iframe loads only this one script.
 */
// @ts-nocheck

import { createRoot } from 'react-dom/client';
import { createElement } from 'react';
import { Tldraw } from '@tldraw/tldraw';
import '@tldraw/tldraw/tldraw.css';

const container = document.getElementById('tldraw-root')!;
const root = createRoot(container);
root.render(createElement(Tldraw, {
    hideUi: false,
    inferDarkMode: true,
}));

console.log('[tldraw-bundle] tldraw mounted from local build');
