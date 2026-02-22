import * as fs from 'fs';
import * as path from 'path';
import { PAL } from '../../src/kernel/pal';

describe('Platform Abstraction Layer (PAL)', () => {
    let pal: PAL;

    beforeEach(() => {
        // Reset window properties and event listeners before each test
        (global as any).window = {
            innerWidth: 1920,
            innerHeight: 1080,
            addEventListener: jest.fn(),
            removeEventListener: jest.fn(),
        };
        pal = new PAL();
    });

    afterEach(() => {
        pal.destroy();
    });

    it('should register and resolve strongly-typed values', () => {
        pal.register<string>('testKey', 'testValue');
        expect(pal.resolve<string>('testKey')).toBe('testValue');

        pal.register<number>('testNumber', 42);
        expect(pal.resolve<number>('testNumber')).toBe(42);
    });

    it('should throw an error when resolving an unregistered key', () => {
        expect(() => pal.resolve<string>('nonExistentKey')).toThrow('Key "nonExistentKey" not found in PAL registry.');
    });

    it('should bind a resize event listener to window and update ScreenWidth and ScreenHeight', () => {
        // Verify initial values
        expect(pal.resolve<number>('ScreenWidth')).toBe(1920);
        expect(pal.resolve<number>('ScreenHeight')).toBe(1080);

        // Verify event listener was added
        expect(global.window.addEventListener).toHaveBeenCalledWith('resize', expect.any(Function));

        // Simulate resize
        const resizeCallback = (global.window.addEventListener as jest.Mock).mock.calls[0][1];
        global.window.innerWidth = 1280;
        global.window.innerHeight = 720;
        resizeCallback();

        // Verify updated values
        expect(pal.resolve<number>('ScreenWidth')).toBe(1280);
        expect(pal.resolve<number>('ScreenHeight')).toBe(720);
    });

    it('should remove the resize event listener and clear registry on destroy', () => {
        const resizeCallback = (global.window.addEventListener as jest.Mock).mock.calls[0][1];
        pal.register('test', 123);
        pal.destroy();
        expect(global.window.removeEventListener).toHaveBeenCalledWith('resize', resizeCallback);
        expect(() => pal.resolve('test')).toThrow();
    });

    it('should handle environments where window is undefined gracefully', () => {
        const originalWindow = (global as any).window;
        delete (global as any).window;
        
        const headlessPal = new PAL();
        expect(() => headlessPal.resolve('ScreenWidth')).toThrow();
        
        headlessPal.destroy(); // Should not throw
        
        (global as any).window = originalWindow;
    });

    it('SPEC 1 GUARD: src/kernel/pal.ts DOES NOT contain window.screen.width or window.screen.height', () => {
        const filePath = path.resolve(__dirname, '../../src/kernel/pal.ts');
        const content = fs.readFileSync(filePath, 'utf-8');
        expect(content).not.toMatch(/window\.screen\.width/);
        expect(content).not.toMatch(/window\.screen\.height/);
    });
});
