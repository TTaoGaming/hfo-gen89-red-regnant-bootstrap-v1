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
    private registry: Map<string, unknown> = new Map();

    public register(key: string, value: unknown): void {
        if (this.registry.has(key)) {
            console.warn(`[PAL] Overwriting existing key: ${key}`);
        }
        this.registry.set(key, value);
    }

    public resolve<T>(key: string): T | undefined {
        return this.registry.get(key) as T;
    }
}

// ── Lifecycle FSM ──────────────────────────────────────────────────────────────
//
// Valid transitions:
//   CREATED     → initAll()    → INITIALIZED
//   INITIALIZED → startAll()   → RUNNING
//   RUNNING     → stopAll()    → STOPPED
//   STOPPED     → startAll()   → RUNNING      (restart without re-init)
//   STOPPED     → destroyAll() → DESTROYED
//   any state   → destroyAll() → DESTROYED    (emergency teardown always works)
//   DESTROYED   → (nothing — terminal)
//
// Calling a method in the wrong state throws LifecycleGateError immediately
// with a message that names the current state, the required state, and the
// correct call order.  No silent no-ops.

type SupervisorState = 'CREATED' | 'INITIALIZED' | 'RUNNING' | 'STOPPED' | 'DESTROYED';

/** Thrown when a PluginSupervisor lifecycle method is called in the wrong state. */
export class LifecycleGateError extends Error {
    constructor(method: string, current: SupervisorState, allowed: SupervisorState[]) {
        super(
            `[Supervisor] LIFECYCLE GATE: ${method}() requires state ${allowed.join(' or ')},` +
            ` but supervisor is in state ${current}.\n` +
            `  Correct call order: registerPlugin() → initAll() → startAll() → stopAll() → destroyAll().\n` +
            `  Current state: ${current}  |  Allowed: ${allowed.join(', ')}`
        );
        this.name = 'LifecycleGateError';
    }
}

export class PluginSupervisor {
    private plugins: Map<string, Plugin> = new Map();
    private context: PluginContext;
    private state: SupervisorState = 'CREATED';

    constructor(eventBus?: EventBus) {
        this.context = {
            eventBus: eventBus ?? new EventBus(),
            pal: new PathAbstractionLayer()
        };
    }

    /** Return this supervisor's isolated EventBus (for bootstrapper wiring and testing). */
    public getEventBus(): EventBus {
        return this.context.eventBus;
    }

    public getPal(): PathAbstractionLayer {
        return this.context.pal;
    }

    /** Current lifecycle state (read-only for external callers). */
    public getState(): SupervisorState {
        return this.state;
    }

    public registerPlugin(plugin: Plugin): void {
        if (this.state !== 'CREATED') {
            throw new LifecycleGateError(
                `registerPlugin('${plugin.name}')`,
                this.state,
                ['CREATED']
            );
        }
        if (this.plugins.has(plugin.name)) {
            throw new Error(
                `[Supervisor] DUPLICATE PLUGIN: '${plugin.name}' is already registered.\n` +
                `  If you intend to replace it, call destroyAll() first.`
            );
        }
        this.plugins.set(plugin.name, plugin);
        console.log(`[Supervisor] Registered plugin: ${plugin.name} v${plugin.version}`);
    }

    public async initAll(): Promise<void> {
        if (this.state !== 'CREATED') {
            throw new LifecycleGateError('initAll', this.state, ['CREATED']);
        }
        console.log(`[Supervisor] Initializing ${this.plugins.size} plugins...`);
        for (const plugin of Array.from(this.plugins.values())) {
            try {
                await plugin.init(this.context);
                console.log(`[Supervisor] Initialized: ${plugin.name}`);
            } catch (error) {
                console.error(`[Supervisor] Failed to initialize plugin: ${plugin.name}`, error);
                // Fail-closed: one broken plugin halts the whole system rather than
                // leaving it in a partially-initialized limbo state.
                throw error;
            }
        }
        this.state = 'INITIALIZED';
    }

    public async startAll(): Promise<void> {
        if (this.state !== 'INITIALIZED' && this.state !== 'STOPPED') {
            throw new LifecycleGateError('startAll', this.state, ['INITIALIZED', 'STOPPED']);
        }
        console.log(`[Supervisor] Starting ${this.plugins.size} plugins...`);
        for (const plugin of Array.from(this.plugins.values())) {
            try {
                await plugin.start();
                console.log(`[Supervisor] Started: ${plugin.name}`);
            } catch (error) {
                console.error(`[Supervisor] Failed to start plugin: ${plugin.name}`, error);
                throw error;
            }
        }
        this.state = 'RUNNING';
    }

    public async stopAll(): Promise<void> {
        if (this.state !== 'RUNNING') {
            throw new LifecycleGateError('stopAll', this.state, ['RUNNING']);
        }
        console.log(`[Supervisor] Stopping ${this.plugins.size} plugins...`);
        const reversed = Array.from(this.plugins.values()).reverse();
        for (const plugin of reversed) {
            try {
                await plugin.stop();
                console.log(`[Supervisor] Stopped: ${plugin.name}`);
            } catch (error) {
                console.error(`[Supervisor] Failed to stop plugin: ${plugin.name}`, error);
                // Non-fatal: continue stopping remaining plugins
            }
        }
        this.state = 'STOPPED';
    }

    public async destroyAll(): Promise<void> {
        if (this.state === 'DESTROYED') {
            console.warn(`[Supervisor] destroyAll() called on an already-DESTROYED supervisor — no-op.`);
            return;
        }
        console.log(`[Supervisor] Destroying ${this.plugins.size} plugins...`);
        const reversed = Array.from(this.plugins.values()).reverse();
        for (const plugin of reversed) {
            try {
                await plugin.destroy();
                console.log(`[Supervisor] Destroyed: ${plugin.name}`);
            } catch (error) {
                console.error(`[Supervisor] Failed to destroy plugin: ${plugin.name}`, error);
            }
        }
        this.plugins.clear();
        this.state = 'DESTROYED';
    }
}
