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
    if (stryMutAct_9fa48("818")) {
      {}
    } else {
      stryCov_9fa48("818");
      if (stryMutAct_9fa48("820") ? false : stryMutAct_9fa48("819") ? true : (stryCov_9fa48("819", "820"), this.registry.has(key))) {
        if (stryMutAct_9fa48("821")) {
          {}
        } else {
          stryCov_9fa48("821");
          console.warn(stryMutAct_9fa48("822") ? `` : (stryCov_9fa48("822"), `[PAL] Overwriting existing key: ${key}`));
        }
      }
      this.registry.set(key, value);
    }
  }
  public resolve<T>(key: string): T | undefined {
    if (stryMutAct_9fa48("823")) {
      {}
    } else {
      stryCov_9fa48("823");
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
    if (stryMutAct_9fa48("824")) {
      {}
    } else {
      stryCov_9fa48("824");
      super((stryMutAct_9fa48("825") ? `` : (stryCov_9fa48("825"), `[Supervisor] LIFECYCLE GATE: ${method}() requires state ${allowed.join(stryMutAct_9fa48("826") ? "" : (stryCov_9fa48("826"), ' or '))},`)) + (stryMutAct_9fa48("827") ? `` : (stryCov_9fa48("827"), ` but supervisor is in state ${current}.\n`)) + (stryMutAct_9fa48("828") ? `` : (stryCov_9fa48("828"), `  Correct call order: registerPlugin() → initAll() → startAll() → stopAll() → destroyAll().\n`)) + (stryMutAct_9fa48("829") ? `` : (stryCov_9fa48("829"), `  Current state: ${current}  |  Allowed: ${allowed.join(stryMutAct_9fa48("830") ? "" : (stryCov_9fa48("830"), ', '))}`)));
      this.name = stryMutAct_9fa48("831") ? "" : (stryCov_9fa48("831"), 'LifecycleGateError');
    }
  }
}
export class PluginSupervisor {
  private plugins: Map<string, Plugin> = new Map();
  private context: PluginContext;
  private state: SupervisorState = stryMutAct_9fa48("832") ? "" : (stryCov_9fa48("832"), 'CREATED');
  constructor(eventBus?: EventBus) {
    if (stryMutAct_9fa48("833")) {
      {}
    } else {
      stryCov_9fa48("833");
      this.context = stryMutAct_9fa48("834") ? {} : (stryCov_9fa48("834"), {
        eventBus: stryMutAct_9fa48("835") ? eventBus && new EventBus() : (stryCov_9fa48("835"), eventBus ?? new EventBus()),
        pal: new PathAbstractionLayer()
      });
    }
  }

  /** Return this supervisor's isolated EventBus (for bootstrapper wiring and testing). */
  public getEventBus(): EventBus {
    if (stryMutAct_9fa48("836")) {
      {}
    } else {
      stryCov_9fa48("836");
      return this.context.eventBus;
    }
  }
  public getPal(): PathAbstractionLayer {
    if (stryMutAct_9fa48("837")) {
      {}
    } else {
      stryCov_9fa48("837");
      return this.context.pal;
    }
  }

  /** Current lifecycle state (read-only for external callers). */
  public getState(): SupervisorState {
    if (stryMutAct_9fa48("838")) {
      {}
    } else {
      stryCov_9fa48("838");
      return this.state;
    }
  }
  public registerPlugin(plugin: Plugin): void {
    if (stryMutAct_9fa48("839")) {
      {}
    } else {
      stryCov_9fa48("839");
      if (stryMutAct_9fa48("842") ? this.state === 'CREATED' : stryMutAct_9fa48("841") ? false : stryMutAct_9fa48("840") ? true : (stryCov_9fa48("840", "841", "842"), this.state !== (stryMutAct_9fa48("843") ? "" : (stryCov_9fa48("843"), 'CREATED')))) {
        if (stryMutAct_9fa48("844")) {
          {}
        } else {
          stryCov_9fa48("844");
          throw new LifecycleGateError(stryMutAct_9fa48("845") ? `` : (stryCov_9fa48("845"), `registerPlugin('${plugin.name}')`), this.state, stryMutAct_9fa48("846") ? [] : (stryCov_9fa48("846"), [stryMutAct_9fa48("847") ? "" : (stryCov_9fa48("847"), 'CREATED')]));
        }
      }
      if (stryMutAct_9fa48("849") ? false : stryMutAct_9fa48("848") ? true : (stryCov_9fa48("848", "849"), this.plugins.has(plugin.name))) {
        if (stryMutAct_9fa48("850")) {
          {}
        } else {
          stryCov_9fa48("850");
          throw new Error((stryMutAct_9fa48("851") ? `` : (stryCov_9fa48("851"), `[Supervisor] DUPLICATE PLUGIN: '${plugin.name}' is already registered.\n`)) + (stryMutAct_9fa48("852") ? `` : (stryCov_9fa48("852"), `  If you intend to replace it, call destroyAll() first.`)));
        }
      }
      this.plugins.set(plugin.name, plugin);
      console.log(stryMutAct_9fa48("853") ? `` : (stryCov_9fa48("853"), `[Supervisor] Registered plugin: ${plugin.name} v${plugin.version}`));
    }
  }
  public async initAll(): Promise<void> {
    if (stryMutAct_9fa48("854")) {
      {}
    } else {
      stryCov_9fa48("854");
      if (stryMutAct_9fa48("857") ? this.state === 'CREATED' : stryMutAct_9fa48("856") ? false : stryMutAct_9fa48("855") ? true : (stryCov_9fa48("855", "856", "857"), this.state !== (stryMutAct_9fa48("858") ? "" : (stryCov_9fa48("858"), 'CREATED')))) {
        if (stryMutAct_9fa48("859")) {
          {}
        } else {
          stryCov_9fa48("859");
          throw new LifecycleGateError(stryMutAct_9fa48("860") ? "" : (stryCov_9fa48("860"), 'initAll'), this.state, stryMutAct_9fa48("861") ? [] : (stryCov_9fa48("861"), [stryMutAct_9fa48("862") ? "" : (stryCov_9fa48("862"), 'CREATED')]));
        }
      }
      console.log(stryMutAct_9fa48("863") ? `` : (stryCov_9fa48("863"), `[Supervisor] Initializing ${this.plugins.size} plugins...`));
      for (const plugin of Array.from(this.plugins.values())) {
        if (stryMutAct_9fa48("864")) {
          {}
        } else {
          stryCov_9fa48("864");
          try {
            if (stryMutAct_9fa48("865")) {
              {}
            } else {
              stryCov_9fa48("865");
              await plugin.init(this.context);
              console.log(stryMutAct_9fa48("866") ? `` : (stryCov_9fa48("866"), `[Supervisor] Initialized: ${plugin.name}`));
            }
          } catch (error) {
            if (stryMutAct_9fa48("867")) {
              {}
            } else {
              stryCov_9fa48("867");
              console.error(stryMutAct_9fa48("868") ? `` : (stryCov_9fa48("868"), `[Supervisor] Failed to initialize plugin: ${plugin.name}`), error);
              // Fail-closed: one broken plugin halts the whole system rather than
              // leaving it in a partially-initialized limbo state.
              throw error;
            }
          }
        }
      }
      this.state = stryMutAct_9fa48("869") ? "" : (stryCov_9fa48("869"), 'INITIALIZED');
    }
  }
  public async startAll(): Promise<void> {
    if (stryMutAct_9fa48("870")) {
      {}
    } else {
      stryCov_9fa48("870");
      if (stryMutAct_9fa48("873") ? this.state !== 'INITIALIZED' || this.state !== 'STOPPED' : stryMutAct_9fa48("872") ? false : stryMutAct_9fa48("871") ? true : (stryCov_9fa48("871", "872", "873"), (stryMutAct_9fa48("875") ? this.state === 'INITIALIZED' : stryMutAct_9fa48("874") ? true : (stryCov_9fa48("874", "875"), this.state !== (stryMutAct_9fa48("876") ? "" : (stryCov_9fa48("876"), 'INITIALIZED')))) && (stryMutAct_9fa48("878") ? this.state === 'STOPPED' : stryMutAct_9fa48("877") ? true : (stryCov_9fa48("877", "878"), this.state !== (stryMutAct_9fa48("879") ? "" : (stryCov_9fa48("879"), 'STOPPED')))))) {
        if (stryMutAct_9fa48("880")) {
          {}
        } else {
          stryCov_9fa48("880");
          throw new LifecycleGateError(stryMutAct_9fa48("881") ? "" : (stryCov_9fa48("881"), 'startAll'), this.state, stryMutAct_9fa48("882") ? [] : (stryCov_9fa48("882"), [stryMutAct_9fa48("883") ? "" : (stryCov_9fa48("883"), 'INITIALIZED'), stryMutAct_9fa48("884") ? "" : (stryCov_9fa48("884"), 'STOPPED')]));
        }
      }
      console.log(stryMutAct_9fa48("885") ? `` : (stryCov_9fa48("885"), `[Supervisor] Starting ${this.plugins.size} plugins...`));
      for (const plugin of Array.from(this.plugins.values())) {
        if (stryMutAct_9fa48("886")) {
          {}
        } else {
          stryCov_9fa48("886");
          try {
            if (stryMutAct_9fa48("887")) {
              {}
            } else {
              stryCov_9fa48("887");
              await plugin.start();
              console.log(stryMutAct_9fa48("888") ? `` : (stryCov_9fa48("888"), `[Supervisor] Started: ${plugin.name}`));
            }
          } catch (error) {
            if (stryMutAct_9fa48("889")) {
              {}
            } else {
              stryCov_9fa48("889");
              console.error(stryMutAct_9fa48("890") ? `` : (stryCov_9fa48("890"), `[Supervisor] Failed to start plugin: ${plugin.name}`), error);
              throw error;
            }
          }
        }
      }
      this.state = stryMutAct_9fa48("891") ? "" : (stryCov_9fa48("891"), 'RUNNING');
    }
  }
  public async stopAll(): Promise<void> {
    if (stryMutAct_9fa48("892")) {
      {}
    } else {
      stryCov_9fa48("892");
      if (stryMutAct_9fa48("895") ? this.state === 'RUNNING' : stryMutAct_9fa48("894") ? false : stryMutAct_9fa48("893") ? true : (stryCov_9fa48("893", "894", "895"), this.state !== (stryMutAct_9fa48("896") ? "" : (stryCov_9fa48("896"), 'RUNNING')))) {
        if (stryMutAct_9fa48("897")) {
          {}
        } else {
          stryCov_9fa48("897");
          throw new LifecycleGateError(stryMutAct_9fa48("898") ? "" : (stryCov_9fa48("898"), 'stopAll'), this.state, stryMutAct_9fa48("899") ? [] : (stryCov_9fa48("899"), [stryMutAct_9fa48("900") ? "" : (stryCov_9fa48("900"), 'RUNNING')]));
        }
      }
      console.log(stryMutAct_9fa48("901") ? `` : (stryCov_9fa48("901"), `[Supervisor] Stopping ${this.plugins.size} plugins...`));
      const reversed = stryMutAct_9fa48("902") ? Array.from(this.plugins.values()) : (stryCov_9fa48("902"), Array.from(this.plugins.values()).reverse());
      for (const plugin of reversed) {
        if (stryMutAct_9fa48("903")) {
          {}
        } else {
          stryCov_9fa48("903");
          try {
            if (stryMutAct_9fa48("904")) {
              {}
            } else {
              stryCov_9fa48("904");
              await plugin.stop();
              console.log(stryMutAct_9fa48("905") ? `` : (stryCov_9fa48("905"), `[Supervisor] Stopped: ${plugin.name}`));
            }
          } catch (error) {
            if (stryMutAct_9fa48("906")) {
              {}
            } else {
              stryCov_9fa48("906");
              console.error(stryMutAct_9fa48("907") ? `` : (stryCov_9fa48("907"), `[Supervisor] Failed to stop plugin: ${plugin.name}`), error);
              // Non-fatal: continue stopping remaining plugins
            }
          }
        }
      }
      this.state = stryMutAct_9fa48("908") ? "" : (stryCov_9fa48("908"), 'STOPPED');
    }
  }
  public async destroyAll(): Promise<void> {
    if (stryMutAct_9fa48("909")) {
      {}
    } else {
      stryCov_9fa48("909");
      if (stryMutAct_9fa48("912") ? this.state !== 'DESTROYED' : stryMutAct_9fa48("911") ? false : stryMutAct_9fa48("910") ? true : (stryCov_9fa48("910", "911", "912"), this.state === (stryMutAct_9fa48("913") ? "" : (stryCov_9fa48("913"), 'DESTROYED')))) {
        if (stryMutAct_9fa48("914")) {
          {}
        } else {
          stryCov_9fa48("914");
          console.warn(stryMutAct_9fa48("915") ? `` : (stryCov_9fa48("915"), `[Supervisor] destroyAll() called on an already-DESTROYED supervisor — no-op.`));
          return;
        }
      }
      console.log(stryMutAct_9fa48("916") ? `` : (stryCov_9fa48("916"), `[Supervisor] Destroying ${this.plugins.size} plugins...`));
      const reversed = stryMutAct_9fa48("917") ? Array.from(this.plugins.values()) : (stryCov_9fa48("917"), Array.from(this.plugins.values()).reverse());
      for (const plugin of reversed) {
        if (stryMutAct_9fa48("918")) {
          {}
        } else {
          stryCov_9fa48("918");
          try {
            if (stryMutAct_9fa48("919")) {
              {}
            } else {
              stryCov_9fa48("919");
              await plugin.destroy();
              console.log(stryMutAct_9fa48("920") ? `` : (stryCov_9fa48("920"), `[Supervisor] Destroyed: ${plugin.name}`));
            }
          } catch (error) {
            if (stryMutAct_9fa48("921")) {
              {}
            } else {
              stryCov_9fa48("921");
              console.error(stryMutAct_9fa48("922") ? `` : (stryCov_9fa48("922"), `[Supervisor] Failed to destroy plugin: ${plugin.name}`), error);
            }
          }
        }
      }
      this.plugins.clear();
      this.state = stryMutAct_9fa48("923") ? "" : (stryCov_9fa48("923"), 'DESTROYED');
    }
  }
}