import { Microkernel, Plugin, PluginManifest } from '../src/microkernel';

describe('Omega v14 Microkernel', () => {
  let kernel: Microkernel;

  beforeEach(() => {
    kernel = new Microkernel();
  });

  describe('Initialization', () => {
    it('should start in IDLE state', () => {
      expect(kernel.getState()).toBe('IDLE');
    });
  });

  describe('Registering a valid plugin', () => {
    it('should add the plugin to the registry and call init', () => {
      // Given
      const manifest: PluginManifest = { id: 'test-plugin', version: '1.0.0' };
      const plugin: Plugin = {
        manifest,
        init: jest.fn(),
        start: jest.fn(),
        stop: jest.fn()
      };

      // When
      kernel.register(plugin);

      // Then
      expect(kernel.getPlugin('test-plugin')).toBe(plugin);
      expect(plugin.init).toHaveBeenCalledWith(kernel);
    });
  });

  describe('Registering an invalid plugin', () => {
    it('should throw an error and not add to registry', () => {
      // Given
      const plugin: any = {
        init: jest.fn(),
        start: jest.fn(),
        stop: jest.fn()
      };

      // When / Then
      expect(() => kernel.register(plugin)).toThrow('Invalid plugin manifest');
      expect(kernel.getPlugins().length).toBe(0);
    });
  });

  describe('Registering a plugin with dependencies', () => {
    it('should throw an error if dependencies are missing', () => {
      // Given
      const plugin: Plugin = {
        manifest: { id: 'p1', version: '1.0.0', dependencies: ['missing-dep'] },
        init: jest.fn(),
        start: jest.fn(),
        stop: jest.fn()
      };

      // When / Then
      expect(() => kernel.register(plugin)).toThrow('Missing dependency: missing-dep');
    });

    it('should register successfully if dependencies are present', () => {
      // Given
      const depPlugin: Plugin = {
        manifest: { id: 'dep1', version: '1.0.0' },
        init: jest.fn(),
        start: jest.fn(),
        stop: jest.fn()
      };
      const plugin: Plugin = {
        manifest: { id: 'p1', version: '1.0.0', dependencies: ['dep1'] },
        init: jest.fn(),
        start: jest.fn(),
        stop: jest.fn()
      };

      // When
      kernel.register(depPlugin);
      kernel.register(plugin);

      // Then
      expect(kernel.getPlugin('p1')).toBe(plugin);
    });
  });

  describe('Registering an untested plugin', () => {
    it('should set the state to ERROR', () => {
      // Given
      const plugin: Plugin = {
        manifest: { id: 'untested-plugin', version: '1.0.0' },
        init: jest.fn(),
        start: jest.fn(),
        stop: jest.fn()
      };

      // When
      kernel.register(plugin);

      // Then
      expect(kernel.getState()).toBe('ERROR');
    });
  });

  describe('Starting the microkernel', () => {
    it('should call start on all registered plugins and set state to RUNNING', () => {
      // Given
      const plugin1: Plugin = {
        manifest: { id: 'p1', version: '1.0.0' },
        init: jest.fn(),
        start: jest.fn(),
        stop: jest.fn()
      };
      const plugin2: Plugin = {
        manifest: { id: 'p2', version: '1.0.0' },
        init: jest.fn(),
        start: jest.fn(),
        stop: jest.fn()
      };
      kernel.register(plugin1);
      kernel.register(plugin2);

      // When
      kernel.start();

      // Then
      expect(plugin1.start).toHaveBeenCalled();
      expect(plugin2.start).toHaveBeenCalled();
      expect(kernel.getState()).toBe('RUNNING');
    });
  });
});
