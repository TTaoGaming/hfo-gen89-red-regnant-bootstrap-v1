// @ts-nocheck
function stryNS_9fa48() {
  var g = typeof globalThis === 'object' && globalThis && globalThis.Math === Math && globalThis || new Function("return this")();
  var ns = g.__stryker__ || (g.__stryker__ = {});
  if (ns.activeMutant === undefined && g.process && g.process.env && g.process.env.__STRYKER_ACTIVE_MUTANT__) {
    ns.activeMutant = g.process.env.__STRYKER_ACTIVE_MUTANT__;
  }
  function retrieveNS() {
    return ns;
  }
  stryNS_9fa48 = retrieveNS;
  return retrieveNS();
}
stryNS_9fa48();
function stryCov_9fa48() {
  var ns = stryNS_9fa48();
  var cov = ns.mutantCoverage || (ns.mutantCoverage = {
    static: {},
    perTest: {}
  });
  function cover() {
    var c = cov.static;
    if (ns.currentTestId) {
      c = cov.perTest[ns.currentTestId] = cov.perTest[ns.currentTestId] || {};
    }
    var a = arguments;
    for (var i = 0; i < a.length; i++) {
      c[a[i]] = (c[a[i]] || 0) + 1;
    }
  }
  stryCov_9fa48 = cover;
  cover.apply(null, arguments);
}
function stryMutAct_9fa48(id) {
  var ns = stryNS_9fa48();
  function isActive(id) {
    if (ns.activeMutant === id) {
      if (ns.hitCount !== void 0 && ++ns.hitCount > ns.hitLimit) {
        throw new Error('Stryker: Hit count limit reached (' + ns.hitCount + ')');
      }
      return true;
    }
    return false;
  }
  stryMutAct_9fa48 = isActive;
  return isActive(id);
}
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
    if (stryMutAct_9fa48("829")) {
      {}
    } else {
      stryCov_9fa48("829");
      if (stryMutAct_9fa48("831") ? false : stryMutAct_9fa48("830") ? true : (stryCov_9fa48("830", "831"), this.registry.has(key))) {
        if (stryMutAct_9fa48("832")) {
          {}
        } else {
          stryCov_9fa48("832");
          console.warn(stryMutAct_9fa48("833") ? `` : (stryCov_9fa48("833"), `[PAL] Overwriting existing key: ${key}`));
        }
      }
      this.registry.set(key, value);
    }
  }
  public resolve<T>(key: string): T | undefined {
    if (stryMutAct_9fa48("834")) {
      {}
    } else {
      stryCov_9fa48("834");
      return this.registry.get(key) as T;
    }
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
    if (stryMutAct_9fa48("835")) {
      {}
    } else {
      stryCov_9fa48("835");
      super((stryMutAct_9fa48("836") ? `` : (stryCov_9fa48("836"), `[Supervisor] LIFECYCLE GATE: ${method}() requires state ${allowed.join(stryMutAct_9fa48("837") ? "" : (stryCov_9fa48("837"), ' or '))},`)) + (stryMutAct_9fa48("838") ? `` : (stryCov_9fa48("838"), ` but supervisor is in state ${current}.\n`)) + (stryMutAct_9fa48("839") ? `` : (stryCov_9fa48("839"), `  Correct call order: registerPlugin() → initAll() → startAll() → stopAll() → destroyAll().\n`)) + (stryMutAct_9fa48("840") ? `` : (stryCov_9fa48("840"), `  Current state: ${current}  |  Allowed: ${allowed.join(stryMutAct_9fa48("841") ? "" : (stryCov_9fa48("841"), ', '))}`)));
      this.name = stryMutAct_9fa48("842") ? "" : (stryCov_9fa48("842"), 'LifecycleGateError');
    }
  }
}
export class PluginSupervisor {
  private plugins: Map<string, Plugin> = new Map();
  private context: PluginContext;
  private state: SupervisorState = stryMutAct_9fa48("843") ? "" : (stryCov_9fa48("843"), 'CREATED');
  constructor(eventBus?: EventBus) {
    if (stryMutAct_9fa48("844")) {
      {}
    } else {
      stryCov_9fa48("844");
      this.context = stryMutAct_9fa48("845") ? {} : (stryCov_9fa48("845"), {
        eventBus: stryMutAct_9fa48("846") ? eventBus && new EventBus() : (stryCov_9fa48("846"), eventBus ?? new EventBus()),
        pal: new PathAbstractionLayer()
      });
    }
  }

  /** Return this supervisor's isolated EventBus (for bootstrapper wiring and testing). */
  public getEventBus(): EventBus {
    if (stryMutAct_9fa48("847")) {
      {}
    } else {
      stryCov_9fa48("847");
      return this.context.eventBus;
    }
  }
  public getPal(): PathAbstractionLayer {
    if (stryMutAct_9fa48("848")) {
      {}
    } else {
      stryCov_9fa48("848");
      return this.context.pal;
    }
  }

  /** Current lifecycle state (read-only for external callers). */
  public getState(): SupervisorState {
    if (stryMutAct_9fa48("849")) {
      {}
    } else {
      stryCov_9fa48("849");
      return this.state;
    }
  }
  public registerPlugin(plugin: Plugin): void {
    if (stryMutAct_9fa48("850")) {
      {}
    } else {
      stryCov_9fa48("850");
      if (stryMutAct_9fa48("853") ? this.state === 'CREATED' : stryMutAct_9fa48("852") ? false : stryMutAct_9fa48("851") ? true : (stryCov_9fa48("851", "852", "853"), this.state !== (stryMutAct_9fa48("854") ? "" : (stryCov_9fa48("854"), 'CREATED')))) {
        if (stryMutAct_9fa48("855")) {
          {}
        } else {
          stryCov_9fa48("855");
          throw new LifecycleGateError(stryMutAct_9fa48("856") ? `` : (stryCov_9fa48("856"), `registerPlugin('${plugin.name}')`), this.state, stryMutAct_9fa48("857") ? [] : (stryCov_9fa48("857"), [stryMutAct_9fa48("858") ? "" : (stryCov_9fa48("858"), 'CREATED')]));
        }
      }
      if (stryMutAct_9fa48("860") ? false : stryMutAct_9fa48("859") ? true : (stryCov_9fa48("859", "860"), this.plugins.has(plugin.name))) {
        if (stryMutAct_9fa48("861")) {
          {}
        } else {
          stryCov_9fa48("861");
          throw new Error((stryMutAct_9fa48("862") ? `` : (stryCov_9fa48("862"), `[Supervisor] DUPLICATE PLUGIN: '${plugin.name}' is already registered.\n`)) + (stryMutAct_9fa48("863") ? `` : (stryCov_9fa48("863"), `  If you intend to replace it, call destroyAll() first.`)));
        }
      }
      this.plugins.set(plugin.name, plugin);
      console.log(stryMutAct_9fa48("864") ? `` : (stryCov_9fa48("864"), `[Supervisor] Registered plugin: ${plugin.name} v${plugin.version}`));
    }
  }
  public async initAll(): Promise<void> {
    if (stryMutAct_9fa48("865")) {
      {}
    } else {
      stryCov_9fa48("865");
      if (stryMutAct_9fa48("868") ? this.state === 'CREATED' : stryMutAct_9fa48("867") ? false : stryMutAct_9fa48("866") ? true : (stryCov_9fa48("866", "867", "868"), this.state !== (stryMutAct_9fa48("869") ? "" : (stryCov_9fa48("869"), 'CREATED')))) {
        if (stryMutAct_9fa48("870")) {
          {}
        } else {
          stryCov_9fa48("870");
          throw new LifecycleGateError(stryMutAct_9fa48("871") ? "" : (stryCov_9fa48("871"), 'initAll'), this.state, stryMutAct_9fa48("872") ? [] : (stryCov_9fa48("872"), [stryMutAct_9fa48("873") ? "" : (stryCov_9fa48("873"), 'CREATED')]));
        }
      }
      console.log(stryMutAct_9fa48("874") ? `` : (stryCov_9fa48("874"), `[Supervisor] Initializing ${this.plugins.size} plugins...`));
      for (const plugin of Array.from(this.plugins.values())) {
        if (stryMutAct_9fa48("875")) {
          {}
        } else {
          stryCov_9fa48("875");
          try {
            if (stryMutAct_9fa48("876")) {
              {}
            } else {
              stryCov_9fa48("876");
              await plugin.init(this.context);
              console.log(stryMutAct_9fa48("877") ? `` : (stryCov_9fa48("877"), `[Supervisor] Initialized: ${plugin.name}`));
            }
          } catch (error) {
            if (stryMutAct_9fa48("878")) {
              {}
            } else {
              stryCov_9fa48("878");
              console.error(stryMutAct_9fa48("879") ? `` : (stryCov_9fa48("879"), `[Supervisor] Failed to initialize plugin: ${plugin.name}`), error);
              // Fail-closed: one broken plugin halts the whole system rather than
              // leaving it in a partially-initialized limbo state.
              throw error;
            }
          }
        }
      }
      this.state = stryMutAct_9fa48("880") ? "" : (stryCov_9fa48("880"), 'INITIALIZED');
    }
  }
  public async startAll(): Promise<void> {
    if (stryMutAct_9fa48("881")) {
      {}
    } else {
      stryCov_9fa48("881");
      if (stryMutAct_9fa48("884") ? this.state !== 'INITIALIZED' || this.state !== 'STOPPED' : stryMutAct_9fa48("883") ? false : stryMutAct_9fa48("882") ? true : (stryCov_9fa48("882", "883", "884"), (stryMutAct_9fa48("886") ? this.state === 'INITIALIZED' : stryMutAct_9fa48("885") ? true : (stryCov_9fa48("885", "886"), this.state !== (stryMutAct_9fa48("887") ? "" : (stryCov_9fa48("887"), 'INITIALIZED')))) && (stryMutAct_9fa48("889") ? this.state === 'STOPPED' : stryMutAct_9fa48("888") ? true : (stryCov_9fa48("888", "889"), this.state !== (stryMutAct_9fa48("890") ? "" : (stryCov_9fa48("890"), 'STOPPED')))))) {
        if (stryMutAct_9fa48("891")) {
          {}
        } else {
          stryCov_9fa48("891");
          throw new LifecycleGateError(stryMutAct_9fa48("892") ? "" : (stryCov_9fa48("892"), 'startAll'), this.state, stryMutAct_9fa48("893") ? [] : (stryCov_9fa48("893"), [stryMutAct_9fa48("894") ? "" : (stryCov_9fa48("894"), 'INITIALIZED'), stryMutAct_9fa48("895") ? "" : (stryCov_9fa48("895"), 'STOPPED')]));
        }
      }
      console.log(stryMutAct_9fa48("896") ? `` : (stryCov_9fa48("896"), `[Supervisor] Starting ${this.plugins.size} plugins...`));
      for (const plugin of Array.from(this.plugins.values())) {
        if (stryMutAct_9fa48("897")) {
          {}
        } else {
          stryCov_9fa48("897");
          try {
            if (stryMutAct_9fa48("898")) {
              {}
            } else {
              stryCov_9fa48("898");
              await plugin.start();
              console.log(stryMutAct_9fa48("899") ? `` : (stryCov_9fa48("899"), `[Supervisor] Started: ${plugin.name}`));
            }
          } catch (error) {
            if (stryMutAct_9fa48("900")) {
              {}
            } else {
              stryCov_9fa48("900");
              console.error(stryMutAct_9fa48("901") ? `` : (stryCov_9fa48("901"), `[Supervisor] Failed to start plugin: ${plugin.name}`), error);
              throw error;
            }
          }
        }
      }
      this.state = stryMutAct_9fa48("902") ? "" : (stryCov_9fa48("902"), 'RUNNING');
    }
  }
  public async stopAll(): Promise<void> {
    if (stryMutAct_9fa48("903")) {
      {}
    } else {
      stryCov_9fa48("903");
      if (stryMutAct_9fa48("906") ? this.state === 'RUNNING' : stryMutAct_9fa48("905") ? false : stryMutAct_9fa48("904") ? true : (stryCov_9fa48("904", "905", "906"), this.state !== (stryMutAct_9fa48("907") ? "" : (stryCov_9fa48("907"), 'RUNNING')))) {
        if (stryMutAct_9fa48("908")) {
          {}
        } else {
          stryCov_9fa48("908");
          throw new LifecycleGateError(stryMutAct_9fa48("909") ? "" : (stryCov_9fa48("909"), 'stopAll'), this.state, stryMutAct_9fa48("910") ? [] : (stryCov_9fa48("910"), [stryMutAct_9fa48("911") ? "" : (stryCov_9fa48("911"), 'RUNNING')]));
        }
      }
      console.log(stryMutAct_9fa48("912") ? `` : (stryCov_9fa48("912"), `[Supervisor] Stopping ${this.plugins.size} plugins...`));
      const reversed = stryMutAct_9fa48("913") ? Array.from(this.plugins.values()) : (stryCov_9fa48("913"), Array.from(this.plugins.values()).reverse());
      for (const plugin of reversed) {
        if (stryMutAct_9fa48("914")) {
          {}
        } else {
          stryCov_9fa48("914");
          try {
            if (stryMutAct_9fa48("915")) {
              {}
            } else {
              stryCov_9fa48("915");
              await plugin.stop();
              console.log(stryMutAct_9fa48("916") ? `` : (stryCov_9fa48("916"), `[Supervisor] Stopped: ${plugin.name}`));
            }
          } catch (error) {
            if (stryMutAct_9fa48("917")) {
              {}
            } else {
              stryCov_9fa48("917");
              console.error(stryMutAct_9fa48("918") ? `` : (stryCov_9fa48("918"), `[Supervisor] Failed to stop plugin: ${plugin.name}`), error);
              // Non-fatal: continue stopping remaining plugins
            }
          }
        }
      }
      this.state = stryMutAct_9fa48("919") ? "" : (stryCov_9fa48("919"), 'STOPPED');
    }
  }
  public async destroyAll(): Promise<void> {
    if (stryMutAct_9fa48("920")) {
      {}
    } else {
      stryCov_9fa48("920");
      if (stryMutAct_9fa48("923") ? this.state !== 'DESTROYED' : stryMutAct_9fa48("922") ? false : stryMutAct_9fa48("921") ? true : (stryCov_9fa48("921", "922", "923"), this.state === (stryMutAct_9fa48("924") ? "" : (stryCov_9fa48("924"), 'DESTROYED')))) {
        if (stryMutAct_9fa48("925")) {
          {}
        } else {
          stryCov_9fa48("925");
          console.warn(stryMutAct_9fa48("926") ? `` : (stryCov_9fa48("926"), `[Supervisor] destroyAll() called on an already-DESTROYED supervisor — no-op.`));
          return;
        }
      }
      console.log(stryMutAct_9fa48("927") ? `` : (stryCov_9fa48("927"), `[Supervisor] Destroying ${this.plugins.size} plugins...`));
      const reversed = stryMutAct_9fa48("928") ? Array.from(this.plugins.values()) : (stryCov_9fa48("928"), Array.from(this.plugins.values()).reverse());
      for (const plugin of reversed) {
        if (stryMutAct_9fa48("929")) {
          {}
        } else {
          stryCov_9fa48("929");
          try {
            if (stryMutAct_9fa48("930")) {
              {}
            } else {
              stryCov_9fa48("930");
              await plugin.destroy();
              console.log(stryMutAct_9fa48("931") ? `` : (stryCov_9fa48("931"), `[Supervisor] Destroyed: ${plugin.name}`));
            }
          } catch (error) {
            if (stryMutAct_9fa48("932")) {
              {}
            } else {
              stryCov_9fa48("932");
              console.error(stryMutAct_9fa48("933") ? `` : (stryCov_9fa48("933"), `[Supervisor] Failed to destroy plugin: ${plugin.name}`), error);
            }
          }
        }
      }
      this.plugins.clear();
      this.state = stryMutAct_9fa48("934") ? "" : (stryCov_9fa48("934"), 'DESTROYED');
    }
  }
}