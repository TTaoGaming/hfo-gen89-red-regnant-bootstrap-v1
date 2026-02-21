import * as fc from 'fast-check';
import { Microkernel, Plugin, PluginManifest } from '../src/microkernel';

describe('Omega v14 Microkernel Properties', () => {
  it('should always maintain exactly the registered plugins', () => {
    fc.assert(
      fc.property(
        fc.array(fc.string({ minLength: 1 }).map(id => ({ id, version: '1.0.0' }))),
        (manifests) => {
          const kernel = new Microkernel();
          const uniqueManifests = Array.from(new Map(manifests.map(m => [m.id, m])).values());
          
          uniqueManifests.forEach(manifest => {
            kernel.register({ manifest });
          });

          const registeredPlugins = kernel.getPlugins();
          return registeredPlugins.length === uniqueManifests.length &&
                 uniqueManifests.every(m => kernel.getPlugin(m.id) !== undefined);
        }
      )
    );
  });
});
