import { SymbioteInjector } from './symbiote_injector';

describe('Cross-Origin DOM Piercing with Level 3 Prediction (Compatibility Pareto)', () => {
    let injector: SymbioteInjector;

    beforeEach(() => {
        injector = new SymbioteInjector();
    });

    it('Given a cross-origin iframe (e.g., Excalidraw) is loaded with the Symbiote Adapter', () => {
        expect(injector.isAdapterLoaded()).toBe(true);
    });

    it('When the TV Host posts a "pointermove" message containing Havok-smoothed arrays', () => {
        injector.receiveHostMessage({
            type: 'pointermove',
            clientX: 500,
            clientY: 500,
            predictedEvents: [{ x: 510, y: 510 }, { x: 520, y: 520 }]
        });
        expect(injector.getLastReceivedMessage()).toBeDefined();
    });

    it('Then the Symbiote MUST translate the global coordinates into local iframe coordinates', () => {
        const localCoords = injector.translateToLocal({ x: 500, y: 500 }, { left: 100, top: 100 });
        expect(localCoords).toEqual({ x: 400, y: 400 });
    });

    it('And it MUST synthesize a perfectly formed W3C PointerEvent', () => {
        injector.receiveHostMessage({
            type: 'pointermove',
            clientX: 500,
            clientY: 500,
            predictedEvents: [{ x: 510, y: 510 }, { x: 520, y: 520 }]
        });
        const event = injector.synthesizeEvent();
        expect(event.type).toBe('pointermove');
        expect(event.composed).toBe(true);
    });

    it('And the Excalidraw canvas MUST successfully draw a line that includes the `getPredictedEvents()` array', () => {
        injector.receiveHostMessage({
            type: 'pointermove',
            clientX: 500,
            clientY: 500,
            predictedEvents: [{ x: 510, y: 510 }, { x: 520, y: 520 }]
        });
        const event = injector.synthesizeEvent();
        expect(typeof event.getPredictedEvents).toBe('function');
        expect(event.getPredictedEvents().length).toBe(2);
    });
});
