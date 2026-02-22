import { Plugin, PluginContext } from './plugin_supervisor';

export class SymbioteInjectorPlugin implements Plugin {
    public name = 'SymbioteInjectorPlugin';
    public version = '1.0.0';
    private context!: PluginContext;

    // Track previous pinch state to emit pointerdown/pointerup
    private isPinchingMap: Map<number, boolean> = new Map();

    /** Bound once in constructor — stable reference for subscribe() and unsubscribe(). */
    private readonly boundOnPointerUpdate: (data: { handId: number; x: number; y: number; isPinching: boolean; }) => void;

    constructor() {
        this.boundOnPointerUpdate = this.onPointerUpdate.bind(this);
    }

    public init(context: PluginContext): void {
        this.context = context;
        // ARCH-ZOMBIE guard: use pre-bound ref — NOT inline .bind(this) here
        this.context.eventBus.subscribe('POINTER_UPDATE', this.boundOnPointerUpdate);
    }

    public start(): void {
        console.log('[SymbioteInjectorPlugin] Started');
    }

    public stop(): void {
        // Unsubscribe when paused — re-subscribes on next init() if reused
        this.context.eventBus.unsubscribe('POINTER_UPDATE', this.boundOnPointerUpdate);
        console.log('[SymbioteInjectorPlugin] Stopped');
    }

    public destroy(): void {
        this.context.eventBus.unsubscribe('POINTER_UPDATE', this.boundOnPointerUpdate);
        this.isPinchingMap.clear();
    }

    private onPointerUpdate(rawData: unknown): void {
        const data = rawData as { handId: number, x: number, y: number, isPinching: boolean };
        const { handId, x, y, isPinching } = data;

        // Resolve screen dimensions through PAL — never touch window directly
        const getWidth  = this.context.pal.resolve<(() => number) | number>('ScreenWidth');
        const getHeight = this.context.pal.resolve<(() => number) | number>('ScreenHeight');
        const screenWidth  = typeof getWidth  === 'function' ? getWidth()  : (getWidth  ?? 1);
        const screenHeight = typeof getHeight === 'function' ? getHeight() : (getHeight ?? 1);

        const screenX = x * screenWidth;
        const screenY = y * screenHeight;
        
        const wasPinching = this.isPinchingMap.get(handId) || false;
        
        let eventType = 'pointermove';
        if (isPinching && !wasPinching) {
            eventType = 'pointerdown';
        } else if (!isPinching && wasPinching) {
            eventType = 'pointerup';
        }
        
        this.isPinchingMap.set(handId, isPinching);
        
        // Dispatch custom event — routed through PAL so the plugin is testable in Node
        // without a browser global.  Register PAL key 'DispatchEvent' in bootstrap to
        // provide a real window.dispatchEvent; in tests, omit it for a safe no-op.
        // (ATDD-ARCH-005: PAL Dom Leaks fix)
        const event = new CustomEvent('omega-pointer-event', {
            detail: {
                type: eventType,
                x: screenX,
                y: screenY,
                handId: handId
            }
        });
        const dispatch = this.context.pal.resolve<((e: Event) => void)>('DispatchEvent');
        dispatch?.(event);
    }
}
