#!/usr/bin/env node
/**
 * build_demo2.mjs — Omega v13 Layered Compositor build helper
 *
 * Usage:
 *   node build_demo2.mjs           # build once
 *   node build_demo2.mjs --watch   # watch mode
 *
 * Delegates to npx esbuild (no local esbuild install required).
 * Serve: python -m http.server 8090  then open localhost:8090/index_demo2.html
 */
import { spawnSync, spawn } from 'child_process';

const COMMON = [
  'demo_2026-02-20.ts',
  '--bundle',
  '--outfile=dist/demo2.js',
  '--sourcemap',
  '--format=esm',
  '--platform=browser',
  '--target=chrome120',
  '--external:./babylon_physics',
  '--log-level=info',
];

const watch = process.argv.includes('--watch');

if (watch) {
  const child = spawn('npx', ['esbuild', ...COMMON, '--watch'], {
    shell: true, stdio: 'inherit',
  });
  process.on('SIGINT', () => child.kill());
} else {
  const res = spawnSync('npx', ['esbuild', ...COMMON], {
    shell: true, stdio: 'inherit',
  });
  if (res.status !== 0) process.exit(res.status ?? 1);
  console.log('[build_demo2] Done → dist/demo2.js');
}
