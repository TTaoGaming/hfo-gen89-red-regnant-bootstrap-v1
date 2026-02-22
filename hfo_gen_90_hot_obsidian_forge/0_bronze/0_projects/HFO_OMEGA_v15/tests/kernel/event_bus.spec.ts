import * as fs from 'fs';
import * as path from 'path';
import { EventBus } from '../../src/kernel/event_bus';

describe('EventBus Microkernel', () => {
    it('Subscribers successfully receive published typed messages', () => {
        const bus = new EventBus();
        const mockFn = jest.fn();
        bus.subscribe('TEST_EVENT', mockFn);
        bus.publish('TEST_EVENT', { payload: 'data' });
        expect(mockFn).toHaveBeenCalledWith({ payload: 'data' });
    });

    it('GRUDGE GUARD: Multiple subscribers to the same channel should all receive the event', () => {
        const bus = new EventBus();
        const mockFn1 = jest.fn();
        const mockFn2 = jest.fn();
        bus.subscribe('TEST_EVENT', mockFn1);
        bus.subscribe('TEST_EVENT', mockFn2);
        bus.publish('TEST_EVENT', { payload: 'data' });
        expect(mockFn1).toHaveBeenCalledWith({ payload: 'data' });
        expect(mockFn2).toHaveBeenCalledWith({ payload: 'data' });
    });

    it('GRUDGE GUARD (Rule 5): An unsubscribed listener MUST NOT fire', () => {
        const bus = new EventBus();
        const mockFn = jest.fn();
        const unsubscribe = bus.subscribe('TEST_EVENT', mockFn);
        unsubscribe();
        const result = bus.publish('TEST_EVENT', { payload: 'data' });
        expect(mockFn).not.toHaveBeenCalled();
        expect(result).toBe(false);
    });

    it('GRUDGE GUARD: Unsubscribing a non-existent listener or channel should not throw', () => {
        const bus = new EventBus();
        const mockFn = jest.fn();
        const unsubscribe = bus.subscribe('TEST_EVENT', mockFn);
        
        // Unsubscribe twice
        expect(() => unsubscribe()).not.toThrow();
        expect(() => unsubscribe()).not.toThrow();

        // Unsubscribe from a channel that was never subscribed to
        const bus2 = new EventBus();
        const mockFn2 = jest.fn();
        const unsubscribe2 = bus2.subscribe('TEST_EVENT', mockFn2);
        // Manually clear the map to simulate missing channel
        (bus2 as any).subscribers.clear();
        expect(() => unsubscribe2()).not.toThrow();
    });

    it('GRUDGE GUARD: Publishing to a channel with no subscribers should return false', () => {
        const bus = new EventBus();
        expect(bus.publish('TEST_EVENT', { payload: 'data' })).toBe(false);
    });

    it('SPEC 4 GUARD: src/kernel/event_bus.ts DOES NOT contain zod imports', () => {
        const filePath = path.resolve(__dirname, '../../src/kernel/event_bus.ts');
        const content = fs.readFileSync(filePath, 'utf-8');
        expect(content).not.toMatch(/import\s+\{\s*z\s*\}\s+from\s+['"]zod['"]/);
        expect(content).not.toMatch(/import\s+.*zod.*/);
    });
});
