export class PAL {
    private registry: Map<string, any> = new Map();
    private resizeListener: () => void;

    constructor() {
        this.resizeListener = () => this.updateScreenDimensions();
        
        if (typeof window !== 'undefined') {
            window.addEventListener('resize', this.resizeListener);
            this.updateScreenDimensions();
        }
    }

    public register<T>(key: string, value: T): void {
        this.registry.set(key, value);
    }

    public resolve<T>(key: string): T {
        if (!this.registry.has(key)) {
            throw new Error(`Key "${key}" not found in PAL registry.`);
        }
        return this.registry.get(key) as T;
    }

    private updateScreenDimensions(): void {
        if (typeof window !== 'undefined') {
            this.register<number>('ScreenWidth', window.innerWidth);
            this.register<number>('ScreenHeight', window.innerHeight);
        }
    }

    public destroy(): void {
        if (typeof window !== 'undefined') {
            window.removeEventListener('resize', this.resizeListener);
        }
        this.registry.clear();
    }
}
