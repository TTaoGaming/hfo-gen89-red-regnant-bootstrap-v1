import { Plugin, PluginContext } from './plugin_supervisor';

export class VisualizationPlugin implements Plugin {
    public name = 'VisualizationPlugin';
    public version = '1.0.0';
    private context!: PluginContext;
    private container: HTMLElement | null = null;
    private handElements: Map<number, HTMLElement> = new Map();

    public init(context: PluginContext): void {
        this.context = context;
        
        this.container = document.createElement('div');
        this.container.id = 'omega-visualization-container';
        this.container.style.position = 'fixed';
        this.container.style.top = '0';
        this.container.style.left = '0';
        this.container.style.width = '100vw';
        this.container.style.height = '100vh';
        this.container.style.pointerEvents = 'none';
        this.container.style.zIndex = '9999';
        document.body.appendChild(this.container);

        this.context.eventBus.subscribe('POINTER_UPDATE', this.onPointerUpdate.bind(this));
        this.context.eventBus.subscribe('STATE_CHANGE', this.onStateChange.bind(this));
        this.context.eventBus.subscribe('POINTER_COAST', this.onPointerCoast.bind(this));
    }

    private getOrCreateHandElement(handId: number): HTMLElement {
        if (!this.handElements.has(handId)) {
            const el = document.createElement('div');
            el.className = `omega-hand-viz hand-${handId}`;
            el.style.position = 'absolute';
            el.style.width = '40px';
            el.style.height = '40px';
            el.style.borderRadius = '50%';
            el.style.border = '2px solid rgba(255, 255, 255, 0.5)';
            el.style.transform = 'translate(-50%, -50%)';
            el.style.transition = 'all 0.1s ease-out';
            el.style.display = 'flex';
            el.style.alignItems = 'center';
            el.style.justifyContent = 'center';
            el.style.boxShadow = '0 0 10px rgba(0,0,0,0.3)';
            
            const innerDot = document.createElement('div');
            innerDot.className = 'inner-dot';
            innerDot.style.width = '10px';
            innerDot.style.height = '10px';
            innerDot.style.borderRadius = '50%';
            innerDot.style.backgroundColor = 'rgba(255, 255, 255, 0.5)';
            innerDot.style.transition = 'all 0.1s ease-out';
            
            el.appendChild(innerDot);
            this.container?.appendChild(el);
            this.handElements.set(handId, el);
        }
        return this.handElements.get(handId)!;
    }

    private onPointerUpdate(data: { handId: number, x: number, y: number, isPinching: boolean, rawLandmarks?: any[], gesture?: string, confidence?: number }) {
        const el = this.getOrCreateHandElement(data.handId);
        
        // Convert normalized coordinates to screen coordinates
        const screenX = data.x * window.innerWidth;
        const screenY = data.y * window.innerHeight;
        
        el.style.left = `${screenX}px`;
        el.style.top = `${screenY}px`;

        // Render 21 landmarks if available
        if (data.rawLandmarks && this.container) {
            let landmarksContainer = document.getElementById(`landmarks-${data.handId}`);
            if (!landmarksContainer) {
                landmarksContainer = document.createElement('div');
                landmarksContainer.id = `landmarks-${data.handId}`;
                this.container.appendChild(landmarksContainer);
            }
            
            // Clear previous landmarks
            landmarksContainer.innerHTML = '';
            
            // Draw skeleton lines
            const connections = [
                [0, 1], [1, 2], [2, 3], [3, 4], // Thumb
                [0, 5], [5, 6], [6, 7], [7, 8], // Index
                [0, 9], [9, 10], [10, 11], [11, 12], // Middle
                [0, 13], [13, 14], [14, 15], [15, 16], // Ring
                [0, 17], [17, 18], [18, 19], [19, 20], // Pinky
                [5, 9], [9, 13], [13, 17] // Palm
            ];

            const scale = (window as any).omegaOverscanScale || 1.0;
            const offset = (1 - 1/scale) / 2;

            connections.forEach(([startIdx, endIdx]) => {
                const startLm = data.rawLandmarks![startIdx];
                const endLm = data.rawLandmarks![endIdx];

                const startX = (startLm.x - offset) * scale * window.innerWidth;
                const startY = (startLm.y - offset) * scale * window.innerHeight;
                const endX = (endLm.x - offset) * scale * window.innerWidth;
                const endY = (endLm.y - offset) * scale * window.innerHeight;

                const length = Math.sqrt(Math.pow(endX - startX, 2) + Math.pow(endY - startY, 2));
                const angle = Math.atan2(endY - startY, endX - startX) * 180 / Math.PI;

                const line = document.createElement('div');
                line.style.position = 'absolute';
                line.style.width = `${length}px`;
                line.style.height = '2px';
                line.style.backgroundColor = 'rgba(255, 255, 255, 0.8)';
                line.style.transformOrigin = '0 50%';
                line.style.transform = `translate(${startX}px, ${startY}px) rotate(${angle}deg)`;
                landmarksContainer!.appendChild(line);
            });

            data.rawLandmarks.forEach((lm, index) => {
                // Skip index finger tip (8) as it's rendered by the main element
                if (index === 8) return;
                
                const mappedX = (lm.x - offset) * scale;
                const mappedY = (lm.y - offset) * scale;

                const dot = document.createElement('div');
                dot.style.position = 'absolute';
                dot.style.width = '8px';
                dot.style.height = '8px';
                dot.style.backgroundColor = 'rgba(255, 255, 255, 1)';
                dot.style.borderRadius = '50%';
                dot.style.transform = 'translate(-50%, -50%)';
                dot.style.left = `${mappedX * window.innerWidth}px`;
                dot.style.top = `${mappedY * window.innerHeight}px`;
                landmarksContainer!.appendChild(dot);
            });

            // Add text overlay for gesture and confidence
            let textOverlay = document.getElementById(`text-overlay-${data.handId}`);
            if (!textOverlay) {
                textOverlay = document.createElement('div');
                textOverlay.id = `text-overlay-${data.handId}`;
                textOverlay.style.position = 'absolute';
                textOverlay.style.color = 'white';
                textOverlay.style.fontFamily = 'monospace';
                textOverlay.style.fontSize = '14px';
                textOverlay.style.backgroundColor = 'rgba(0,0,0,0.5)';
                textOverlay.style.padding = '4px 8px';
                textOverlay.style.borderRadius = '4px';
                textOverlay.style.pointerEvents = 'none';
                this.container.appendChild(textOverlay);
            }
            
            textOverlay.style.left = `${screenX + 20}px`;
            textOverlay.style.top = `${screenY - 20}px`;
            
            const gestureName = data.gesture || 'unknown';
            const confScore = data.confidence !== undefined ? data.confidence.toFixed(2) : 'N/A';
            textOverlay.innerText = `${gestureName} (${confScore})`;
        }
    }

    private onStateChange(data: { handId: number, previousState: string, currentState: string }) {
        const el = this.getOrCreateHandElement(data.handId);
        const innerDot = el.querySelector('.inner-dot') as HTMLElement;
        
        // Update visual style based on state
        switch (data.currentState) {
            case 'IDLE':
            case 'IDLE_COAST':
                el.style.borderColor = 'rgba(150, 150, 150, 0.5)';
                el.style.transform = 'translate(-50%, -50%) scale(1)';
                innerDot.style.backgroundColor = 'rgba(150, 150, 150, 0.5)';
                innerDot.style.transform = 'scale(1)';
                break;
            case 'READY':
            case 'READY_COAST':
                el.style.borderColor = 'rgba(50, 150, 255, 0.8)';
                el.style.transform = 'translate(-50%, -50%) scale(1.2)';
                innerDot.style.backgroundColor = 'rgba(50, 150, 255, 0.8)';
                innerDot.style.transform = 'scale(1.5)';
                break;
            case 'COMMIT_POINTER':
            case 'COMMIT_COAST':
                el.style.borderColor = 'rgba(50, 255, 50, 1)';
                el.style.transform = 'translate(-50%, -50%) scale(0.8)';
                el.style.backgroundColor = 'rgba(50, 255, 50, 0.2)';
                innerDot.style.backgroundColor = 'rgba(50, 255, 50, 1)';
                innerDot.style.transform = 'scale(2)';
                break;
        }
    }

    private onPointerCoast(data: { handId: number, isPinching: boolean, destroy: boolean }) {
        if (data.destroy) {
            const el = this.handElements.get(data.handId);
            if (el) {
                el.remove();
                this.handElements.delete(data.handId);
            }
        }
    }

    public start(): void {
        console.log('[VisualizationPlugin] Started');
    }

    public stop(): void {
        console.log('[VisualizationPlugin] Stopped');
    }

    public destroy(): void {
        if (this.container) {
            this.container.remove();
            this.container = null;
        }
        this.handElements.clear();
    }
}
