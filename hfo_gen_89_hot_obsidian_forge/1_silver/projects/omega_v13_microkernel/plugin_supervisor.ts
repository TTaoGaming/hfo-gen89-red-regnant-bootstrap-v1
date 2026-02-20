import { EventBus } from './event_bus';

export interface PluginContext {
    eventBus: EventBus;
    pal: PathAbstractionLayer;
}

export interface Plugin {
    name: string;
    version: string;
    
    // Lifecycle methods
    init(context: PluginContext): Promise<void> | void;
    start(): Promise<void> | void;
    stop(): Promise<void> | void;
    destroy(): Promise<void> | void;
}

export class PathAbstractionLayer {
    private registry: Map<string, any> = new Map();

    public register(key: string, value: any): void {
        if (this.registry.has(key)) {
            console.warn(`[PAL] Overwriting existing key: ${key}`);
        }
        this.registry.set(key, value);
    }

    public resolve<T>(key: string): T | undefined {
        return this.registry.get(key) as T;
    }
}

export class PluginSupervisor {
    private plugins: Map<string, Plugin> = new Map();
    private context: PluginContext;

    constructor(eventBus?: EventBus) {
        this.context = {
            eventBus: eventBus ?? new EventBus(),
            pal: new PathAbstractionLayer()
        };
    }

    /** Return this supervisor's isolated EventBus (for testing and bootstrapper use). */
    public getEventBus(): EventBus {
        return this.context.eventBus;
    }

    public getPal(): PathAbstractionLayer {
        return this.context.pal;
    }

    public registerPlugin(plugin: Plugin): void {
        if (this.plugins.has(plugin.name)) {
            throw new Error(`[Supervisor] Plugin already registered: ${plugin.name}`);
        }
        this.plugins.set(plugin.name, plugin);
        console.log(`[Supervisor] Registered plugin: ${plugin.name} v${plugin.version}`);
    }

    public async initAll(): Promise<void> {
        console.log(`[Supervisor] Initializing ${this.plugins.size} plugins...`);
        for (const plugin of this.plugins.values()) {
            try {
                await plugin.init(this.context);
                console.log(`[Supervisor] Initialized: ${plugin.name}`);
            } catch (error) {
                console.error(`[Supervisor] Failed to initialize plugin: ${plugin.name}`, error);
                // Fail-closed: If a plugin fails to init, we should probably halt or quarantine it.
                // For now, we throw to prevent starting a broken system.
                throw error;
            }
        }
    }

    public async startAll(): Promise<void> {
        console.log(`[Supervisor] Starting ${this.plugins.size} plugins...`);
        for (const plugin of this.plugins.values()) {
            try {
                await plugin.start();
                console.log(`[Supervisor] Started: ${plugin.name}`);
            } catch (error) {
                console.error(`[Supervisor] Failed to start plugin: ${plugin.name}`, error);
                throw error;
            }
        }
    }

    public async stopAll(): Promise<void> {
        console.log(`[Supervisor] Stopping ${this.plugins.size} plugins...`);
        // Stop in reverse order of registration (often a good practice)
        const reversedPlugins = Array.from(this.plugins.values()).reverse();
        for (const plugin of reversedPlugins) {
            try {
                await plugin.stop();
                console.log(`[Supervisor] Stopped: ${plugin.name}`);
            } catch (error) {
                console.error(`[Supervisor] Failed to stop plugin: ${plugin.name}`, error);
            }
        }
    }

    public async destroyAll(): Promise<void> {
        console.log(`[Supervisor] Destroying ${this.plugins.size} plugins...`);
        const reversedPlugins = Array.from(this.plugins.values()).reverse();
        for (const plugin of reversedPlugins) {
            try {
                await plugin.destroy();
                console.log(`[Supervisor] Destroyed: ${plugin.name}`);
            } catch (error) {
                console.error(`[Supervisor] Failed to destroy plugin: ${plugin.name}`, error);
            }
        }
        this.plugins.clear();
    }
}
