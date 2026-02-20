export type EventCallback = (data: any) => void;

export class EventBus {
    private listeners: Map<string, EventCallback[]> = new Map();

    public subscribe(event: string, callback: EventCallback): void {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, []);
        }
        this.listeners.get(event)!.push(callback);
    }

    public unsubscribe(event: string, callback: EventCallback): void {
        if (!this.listeners.has(event)) return;
        const callbacks = this.listeners.get(event)!;
        const index = callbacks.indexOf(callback);
        if (index !== -1) {
            callbacks.splice(index, 1);
        }
    }

    public publish(event: string, data?: any): void {
        if (!this.listeners.has(event)) return;
        for (const callback of this.listeners.get(event)!) {
            callback(data);
        }
    }
}

// ── ATDD-ARCH-001 compliance ──────────────────────────────────────────────────
// globalEventBus singleton DELETED. All consumers must receive an EventBus
// instance through PluginContext.eventBus (injected by PluginSupervisor).
//
// Scenario: Given globalEventBus export removed
//           When a plugin is initialised via PluginSupervisor.initAll()
//           Then it receives an isolated bus via context.eventBus, never a global.
