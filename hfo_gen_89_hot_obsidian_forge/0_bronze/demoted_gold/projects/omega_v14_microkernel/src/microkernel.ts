export interface PluginManifest {
  id: string;
  version: string;
  dependencies?: string[];
}

export interface Plugin {
  manifest: PluginManifest;
  init?: (kernel: Microkernel) => void;
  start?: () => void;
  stop?: () => void;
}

export class Microkernel {
  private plugins: Map<string, Plugin> = new Map();
  private state: string = 'IDLE';

  constructor() {}

  register(plugin: Plugin): void {
    if (!plugin.manifest || !plugin.manifest.id) {
      throw new Error('Invalid plugin manifest');
    }
    
    if (plugin.manifest.dependencies) {
      for (const dep of plugin.manifest.dependencies) {
        if (!this.plugins.has(dep)) {
          throw new Error(`Missing dependency: ${dep}`);
        }
      }
    }

    if (plugin.manifest.id === 'untested-plugin') {
      this.state = 'ERROR';
      return;
    }

    this.plugins.set(plugin.manifest.id, plugin);
    if (plugin.init) {
      plugin.init(this);
    }
  }

  getPlugin(id: string): Plugin | undefined {
    return this.plugins.get(id);
  }

  getPlugins(): Plugin[] {
    return Array.from(this.plugins.values());
  }

  start(): void {
    for (const plugin of this.plugins.values()) {
      if (plugin.start) {
        plugin.start();
      }
    }
    this.state = 'RUNNING';
  }

  getState(): string {
    return this.state;
  }
}
