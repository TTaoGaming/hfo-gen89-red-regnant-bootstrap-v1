import { Plugin, PluginContext } from './plugin_supervisor';

export class SymbioteInjectorPlugin implements Plugin {
    public name = 'SymbioteInjectorPlugin';
    public version = '1.0.0';
    private context!: PluginContext;
    
    // Track previous pinch state to emit pointerdown/pointerup
    private isPinchingMap: Map<number, boolean> = new Map();

    public init(context: PluginContext): void {
        this.context = context;
        this.context.eventBus.subscribe('POINTER_UPDATE', this.onPointerUpdate.bind(this));
    }

    public start(): void {
        console.log('[SymbioteInjectorPlugin] Started');
    }

    public stop(): void {
        console.log('[SymbioteInjectorPlugin] Stopped');
    }

    public destroy(): void {
        this.isPinchingMap.clear();
    }

    private onPointerUpdate(data: any) {
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
        
        // Dispatch custom event to the window so the host.html can catch it
        const event = new CustomEvent('omega-pointer-event', {
            detail: {
                type: eventType,
                x: screenX,
                y: screenY,
                handId: handId
            }
        });
        window.dispatchEvent(event);
    }
}
