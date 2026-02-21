import { PluginSupervisor, Plugin, PluginContext } from './plugin_supervisor';

class MockPluginA implements Plugin {
    name = 'MockPluginA';
    version = '1.0.0';
    private context?: PluginContext;

    async init(context: PluginContext): Promise<void> {
        this.context = context;
        console.log(`[${this.name}] Initialized.`);
        // Register something in PAL
        this.context.pal.register('pluginA.data', { secret: 42 });
    }

    async start(): Promise<void> {
        console.log(`[${this.name}] Started.`);
        // Subscribe to an event
        this.context?.eventBus.subscribe('TEST_EVENT', this.onTestEvent.bind(this));
    }

    private onTestEvent(data: any) {
        console.log(`[${this.name}] Received TEST_EVENT:`, data);
    }

    async stop(): Promise<void> {
        console.log(`[${this.name}] Stopped.`);
        // Unsubscribe (in a real plugin, you'd keep track of the bound function)
    }

    async destroy(): Promise<void> {
        console.log(`[${this.name}] Destroyed.`);
    }
}

class MockPluginB implements Plugin {
    name = 'MockPluginB';
    version = '2.1.0';
    private context?: PluginContext;

    async init(context: PluginContext): Promise<void> {
        this.context = context;
        console.log(`[${this.name}] Initialized.`);
    }

    async start(): Promise<void> {
        console.log(`[${this.name}] Started.`);
        // Read from PAL
        const data = this.context?.pal.resolve<{ secret: number }>('pluginA.data');
        console.log(`[${this.name}] Read from PAL:`, data);

        // Publish an event
        console.log(`[${this.name}] Publishing TEST_EVENT...`);
        this.context?.eventBus.publish('TEST_EVENT', { message: 'Hello from B!' });
    }

    async stop(): Promise<void> {
        console.log(`[${this.name}] Stopped.`);
    }

    async destroy(): Promise<void> {
        console.log(`[${this.name}] Destroyed.`);
    }
}

async function runTests() {
    console.log("--- TEST: Plugin Supervisor Lifecycle ---");
    const supervisor = new PluginSupervisor();

    // 1. Registration
    supervisor.registerPlugin(new MockPluginA());
    supervisor.registerPlugin(new MockPluginB());

    try {
        // 2. Initialization
        await supervisor.initAll();

        // 3. Start
        await supervisor.startAll();

        // 4. Stop
        await supervisor.stopAll();

        // 5. Destroy
        await supervisor.destroyAll();

        console.log("\n--- TEST PASSED ---");
    } catch (error) {
        console.error("\n--- TEST FAILED ---", error);
        process.exit(1);
    }
}

runTests();
