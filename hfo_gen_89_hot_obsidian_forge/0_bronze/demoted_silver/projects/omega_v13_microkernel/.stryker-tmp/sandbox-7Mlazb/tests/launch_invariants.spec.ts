// @ts-nocheck
import * as fs from 'fs';
import * as path from 'path';
import { GestureFSM } from '../gesture_fsm';
import { SYMBIOTE_CONTRACT } from '../event_channel_manifest';

describe('Omega v13 Launch Invariants (ATDD Enforcement)', () => {
  const projectRoot = path.resolve(__dirname, '..');

  const readFile = (filename: string) => {
    const filePath = path.join(projectRoot, filename);
    if (!fs.existsSync(filePath)) {
      throw new Error(`File not found: ${filename}`);
    }
    return fs.readFileSync(filePath, 'utf-8');
  };

  describe('SPEC 1: The Viewport Geometry Constraint (Anti-Drift)', () => {
    it('PAL resolves true CSS Viewport, not physical screen', () => {
      const source = readFile('demo_2026-02-20.ts');
      
      expect(source).not.toMatch(/window\.screen\.width/);
      expect(source).not.toMatch(/window\.screen\.height/);
      
      expect(source).toMatch(/window\.innerWidth/);
      expect(source).toMatch(/window\.innerHeight/);
      
      expect(source).toMatch(/addEventListener\(['"]resize['"]/);
    });
  });

  describe('SPEC 2: The Z-Stack Penetration Constraint (Anti-Invisible Wall)', () => {
    it('UI layers default to pointer-events none', () => {
      const source = readFile('layer_manager.ts');
      
      // Look for LAYER.SETTINGS or similar default descriptor having pointerEvents: 'none'
      // We can use a regex to find pointerEvents: 'none' or pointerEvents: "none"
      const hasPointerEventsNone = /pointerEvents:\s*['"]none['"]/.test(source);
      expect(hasPointerEventsNone).toBe(true);
    });
  });

  describe('SPEC 3: The Synthetic Pointer Compatibility Constraint (React Survival)', () => {
    it('Symbiote polyfills capture and maps button state', () => {
      const source = readFile('tldraw_layer.html');
      
      // MUST map eventInit.buttons > 0 to button: 0
      expect(source).toMatch(/button:\s*.*buttons\s*>\s*0\s*\?\s*0\s*:/);
      
      // Element.prototype.setPointerCapture MUST be polyfilled
      expect(source).toMatch(/Element\.prototype\.setPointerCapture\s*=\s*function/);
      
      // Element.prototype.releasePointerCapture MUST be polyfilled
      expect(source).toMatch(/Element\.prototype\.releasePointerCapture\s*=\s*function/);
    });
  });

  describe('SPEC 4: The GC Zero-Allocation Constraint (Anti-Meltdown)', () => {
    it('W3CPointerFabric skips heavy reflection validation in hot loops', () => {
      const source = readFile('w3c_pointer_fabric.ts');
      
      expect(source).not.toMatch(/import.*zod/);
      expect(source).not.toMatch(/PointerUpdateSchema/);
      
      // Check that onPointerUpdate and onPointerCoast don't contain .parse()
      // A simple check is that the file doesn't contain .parse() at all, or at least not in those methods.
      expect(source).not.toMatch(/\.parse\(/);
    });
  });

  describe('SPEC 5: The Orthogonal Intent Constraint (Anti-Thrash FSM)', () => {
    it('Strict State Routing (No Teleportation)', () => {
      const fsm = new GestureFSM();
      expect(fsm.state).toBe('IDLE');
      
      // Try to transition directly to COMMIT
      fsm.processFrame('pointer_up', 0.9, 0, 0, 100);
      
      // It should remain in IDLE or READY, but NOT COMMIT
      expect(fsm.state).not.toBe('COMMIT_POINTER');
    });

    it('Independent Leaky Buckets (Anti-Thrash)', () => {
      const fsm = new GestureFSM() as any; // Cast to any to access new properties
      
      // Force to COMMIT state for the test
      fsm.state = 'COMMIT_POINTER';
      
      // Receive open_palm frames
      fsm.processFrame('open_palm', 0.9, 0, 0, 100);
      fsm.processFrame('open_palm', 0.9, 0, 0, 150);
      
      // Check buckets
      expect(fsm.ready_bucket_ms).toBeGreaterThan(0);
      expect(fsm.idle_bucket_ms).toBe(0);
      
      // Returning to pointer_up drains opposing buckets
      const prevReady = fsm.ready_bucket_ms;
      fsm.processFrame('pointer_up', 0.9, 0, 0, 200);
      expect(fsm.ready_bucket_ms).toBeLessThan(prevReady);
    });
  });

  describe('SPEC 6: Thermal Physics Activation (The Battery Melter — B2 Complete)', () => {
    it('BabylonPhysicsPlugin is registered via the plugin interface, not startBabylon()', () => {
      const source = readFile('demo_2026-02-20.ts');

      // B2 complete: Havok physics IS active in the demo via proper plugin interface
      expect(source).toMatch(/registerPlugin\(new BabylonPhysicsPlugin/);

      // Anti-regression: startBabylon() is the old monolithic pattern — must never return
      expect(source).not.toMatch(/startBabylon\(\)/);
    });
  });

  // ───────────────────────────────────────────────────────────────────────────
  // SPEC 7: Symbiote Contract Gate (Anti-Touch-Deadzone)
  // The pointerType:'touch' 10px deadzone bug is permanently banished.
  // tldraw_layer.html must use pen type, pointer capture polyfill, and
  // activeCaptures bookkeeping. w3c_pointer_fabric.ts must use pen type and
  // the Highlander V13 mutex. Both files must NEVER contain 'touch' type.
  // ───────────────────────────────────────────────────────────────────────────
  describe('SPEC 7: Symbiote Contract Gate (Anti-Touch-Deadzone)', () => {
    it('tldraw_layer.html satisfies the symbiote contract: pen type, capture polyfill, click synth, no touch', () => {
      const src = readFile('tldraw_layer.html');
      SYMBIOTE_CONTRACT.tldraw_layer_html.mustContain.forEach(p => {
        expect(src).toMatch(p);
      });
      SYMBIOTE_CONTRACT.tldraw_layer_html.mustNotContain.forEach(p => {
        expect(src).not.toMatch(p);
      });
    });

    it('w3c_pointer_fabric.ts satisfies the symbiote contract: pen type, Highlander mutex, no touch', () => {
      const src = readFile('w3c_pointer_fabric.ts');
      SYMBIOTE_CONTRACT.w3c_pointer_fabric_ts.mustContain.forEach(p => {
        expect(src).toMatch(p);
      });
      SYMBIOTE_CONTRACT.w3c_pointer_fabric_ts.mustNotContain.forEach(p => {
        expect(src).not.toMatch(p);
      });
    });
  });

  // ───────────────────────────────────────────────────────────────────────────
  // SPEC 8: Bootstrap PAL-Before-Plugins Order Gate (L8 Initialization Order)
  // Every PAL.register() call for critical services (ScreenWidth, AudioContext, etc.)
  // must textually precede the first registerPlugin() call in the bootstrap.
  //
  // If a plugin is registered before PAL is populated, its init() receives a PAL
  // with null/undefined resolves and fails silently — no tsc error, no throw,
  // just wrong runtime values for the duration of the session.
  // ───────────────────────────────────────────────────────────────────────────
  describe('SPEC 8: Bootstrap PAL-Before-Plugins Order Gate', () => {
    it('pal.register calls for critical services appear before any registerPlugin call', () => {
      const src = readFile('demo_2026-02-20.ts');

      // Critical PAL keys that must be available before any plugin initialises
      const criticalKeys = ['ScreenWidth', 'ScreenHeight', 'AudioContext', 'ElementFromPoint'];

      const firstPlugin = src.indexOf('registerPlugin(');
      expect(firstPlugin).toBeGreaterThan(0); // sanity: bootstrap actually registers plugins

      for (const key of criticalKeys) {
        const palRegisterPos = src.indexOf(`pal.register('${key}'`);
        expect(palRegisterPos).toBeGreaterThan(0); // sanity: key is registered
        expect(palRegisterPos).toBeLessThan(firstPlugin);
      }
    });

    it('no registerPlugin call appears before the ScreenWidth PAL registration', () => {
      const src = readFile('demo_2026-02-20.ts');
      const firstPalRegister  = src.indexOf("pal.register('ScreenWidth'");
      const firstPlugin       = src.indexOf('registerPlugin(');
      expect(firstPalRegister).toBeLessThan(firstPlugin);
    });
  });
});
