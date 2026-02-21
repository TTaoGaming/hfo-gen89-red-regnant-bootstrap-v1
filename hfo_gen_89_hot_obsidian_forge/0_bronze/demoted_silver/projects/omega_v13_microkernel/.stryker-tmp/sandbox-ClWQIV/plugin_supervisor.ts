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
    if (stryMutAct_9fa48("0")) {
      {}
    } else {
      stryCov_9fa48("0");
      if (stryMutAct_9fa48("2") ? false : stryMutAct_9fa48("1") ? true : (stryCov_9fa48("1", "2"), this.registry.has(key))) {
        if (stryMutAct_9fa48("3")) {
          {}
        } else {
          stryCov_9fa48("3");
          console.warn(stryMutAct_9fa48("4") ? `` : (stryCov_9fa48("4"), `[PAL] Overwriting existing key: ${key}`));
        }
      }
      this.registry.set(key, value);
    }
  }
  public resolve<T>(key: string): T | undefined {
    if (stryMutAct_9fa48("5")) {
      {}
    } else {
      stryCov_9fa48("5");
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
    if (stryMutAct_9fa48("6")) {
      {}
    } else {
      stryCov_9fa48("6");
      super((stryMutAct_9fa48("7") ? `` : (stryCov_9fa48("7"), `[Supervisor] LIFECYCLE GATE: ${method}() requires state ${allowed.join(stryMutAct_9fa48("8") ? "" : (stryCov_9fa48("8"), ' or '))},`)) + (stryMutAct_9fa48("9") ? `` : (stryCov_9fa48("9"), ` but supervisor is in state ${current}.\n`)) + (stryMutAct_9fa48("10") ? `` : (stryCov_9fa48("10"), `  Correct call order: registerPlugin() → initAll() → startAll() → stopAll() → destroyAll().\n`)) + (stryMutAct_9fa48("11") ? `` : (stryCov_9fa48("11"), `  Current state: ${current}  |  Allowed: ${allowed.join(stryMutAct_9fa48("12") ? "" : (stryCov_9fa48("12"), ', '))}`)));
      this.name = stryMutAct_9fa48("13") ? "" : (stryCov_9fa48("13"), 'LifecycleGateError');
    }
  }
}
export class PluginSupervisor {
  private plugins: Map<string, Plugin> = new Map();
  private context: PluginContext;
  private state: SupervisorState = stryMutAct_9fa48("14") ? "" : (stryCov_9fa48("14"), 'CREATED');
  constructor(eventBus?: EventBus) {
    if (stryMutAct_9fa48("15")) {
      {}
    } else {
      stryCov_9fa48("15");
      this.context = stryMutAct_9fa48("16") ? {} : (stryCov_9fa48("16"), {
        eventBus: stryMutAct_9fa48("17") ? eventBus && new EventBus() : (stryCov_9fa48("17"), eventBus ?? new EventBus()),
        pal: new PathAbstractionLayer()
      });
    }
  }

  /** Return this supervisor's isolated EventBus (for bootstrapper wiring and testing). */
  public getEventBus(): EventBus {
    if (stryMutAct_9fa48("18")) {
      {}
    } else {
      stryCov_9fa48("18");
      return this.context.eventBus;
    }
  }
  public getPal(): PathAbstractionLayer {
    if (stryMutAct_9fa48("19")) {
      {}
    } else {
      stryCov_9fa48("19");
      return this.context.pal;
    }
  }

  /** Current lifecycle state (read-only for external callers). */
  public getState(): SupervisorState {
    if (stryMutAct_9fa48("20")) {
      {}
    } else {
      stryCov_9fa48("20");
      return this.state;
    }
  }
  public registerPlugin(plugin: Plugin): void {
    if (stryMutAct_9fa48("21")) {
      {}
    } else {
      stryCov_9fa48("21");
      if (stryMutAct_9fa48("24") ? this.state === 'CREATED' : stryMutAct_9fa48("23") ? false : stryMutAct_9fa48("22") ? true : (stryCov_9fa48("22", "23", "24"), this.state !== (stryMutAct_9fa48("25") ? "" : (stryCov_9fa48("25"), 'CREATED')))) {
        if (stryMutAct_9fa48("26")) {
          {}
        } else {
          stryCov_9fa48("26");
          throw new LifecycleGateError(stryMutAct_9fa48("27") ? `` : (stryCov_9fa48("27"), `registerPlugin('${plugin.name}')`), this.state, stryMutAct_9fa48("28") ? [] : (stryCov_9fa48("28"), [stryMutAct_9fa48("29") ? "" : (stryCov_9fa48("29"), 'CREATED')]));
        }
      }
      if (stryMutAct_9fa48("31") ? false : stryMutAct_9fa48("30") ? true : (stryCov_9fa48("30", "31"), this.plugins.has(plugin.name))) {
        if (stryMutAct_9fa48("32")) {
          {}
        } else {
          stryCov_9fa48("32");
          throw new Error((stryMutAct_9fa48("33") ? `` : (stryCov_9fa48("33"), `[Supervisor] DUPLICATE PLUGIN: '${plugin.name}' is already registered.\n`)) + (stryMutAct_9fa48("34") ? `` : (stryCov_9fa48("34"), `  If you intend to replace it, call destroyAll() first.`)));
        }
      }
      this.plugins.set(plugin.name, plugin);
      console.log(stryMutAct_9fa48("35") ? `` : (stryCov_9fa48("35"), `[Supervisor] Registered plugin: ${plugin.name} v${plugin.version}`));
    }
  }
  public async initAll(): Promise<void> {
    if (stryMutAct_9fa48("36")) {
      {}
    } else {
      stryCov_9fa48("36");
      if (stryMutAct_9fa48("39") ? this.state === 'CREATED' : stryMutAct_9fa48("38") ? false : stryMutAct_9fa48("37") ? true : (stryCov_9fa48("37", "38", "39"), this.state !== (stryMutAct_9fa48("40") ? "" : (stryCov_9fa48("40"), 'CREATED')))) {
        if (stryMutAct_9fa48("41")) {
          {}
        } else {
          stryCov_9fa48("41");
          throw new LifecycleGateError(stryMutAct_9fa48("42") ? "" : (stryCov_9fa48("42"), 'initAll'), this.state, stryMutAct_9fa48("43") ? [] : (stryCov_9fa48("43"), [stryMutAct_9fa48("44") ? "" : (stryCov_9fa48("44"), 'CREATED')]));
        }
      }
      console.log(stryMutAct_9fa48("45") ? `` : (stryCov_9fa48("45"), `[Supervisor] Initializing ${this.plugins.size} plugins...`));
      for (const plugin of Array.from(this.plugins.values())) {
        if (stryMutAct_9fa48("46")) {
          {}
        } else {
          stryCov_9fa48("46");
          try {
            if (stryMutAct_9fa48("47")) {
              {}
            } else {
              stryCov_9fa48("47");
              await plugin.init(this.context);
              console.log(stryMutAct_9fa48("48") ? `` : (stryCov_9fa48("48"), `[Supervisor] Initialized: ${plugin.name}`));
            }
          } catch (error) {
            if (stryMutAct_9fa48("49")) {
              {}
            } else {
              stryCov_9fa48("49");
              console.error(stryMutAct_9fa48("50") ? `` : (stryCov_9fa48("50"), `[Supervisor] Failed to initialize plugin: ${plugin.name}`), error);
              // Fail-closed: one broken plugin halts the whole system rather than
              // leaving it in a partially-initialized limbo state.
              throw error;
            }
          }
        }
      }
      this.state = stryMutAct_9fa48("51") ? "" : (stryCov_9fa48("51"), 'INITIALIZED');
    }
  }
  public async startAll(): Promise<void> {
    if (stryMutAct_9fa48("52")) {
      {}
    } else {
      stryCov_9fa48("52");
      if (stryMutAct_9fa48("55") ? this.state !== 'INITIALIZED' || this.state !== 'STOPPED' : stryMutAct_9fa48("54") ? false : stryMutAct_9fa48("53") ? true : (stryCov_9fa48("53", "54", "55"), (stryMutAct_9fa48("57") ? this.state === 'INITIALIZED' : stryMutAct_9fa48("56") ? true : (stryCov_9fa48("56", "57"), this.state !== (stryMutAct_9fa48("58") ? "" : (stryCov_9fa48("58"), 'INITIALIZED')))) && (stryMutAct_9fa48("60") ? this.state === 'STOPPED' : stryMutAct_9fa48("59") ? true : (stryCov_9fa48("59", "60"), this.state !== (stryMutAct_9fa48("61") ? "" : (stryCov_9fa48("61"), 'STOPPED')))))) {
        if (stryMutAct_9fa48("62")) {
          {}
        } else {
          stryCov_9fa48("62");
          throw new LifecycleGateError(stryMutAct_9fa48("63") ? "" : (stryCov_9fa48("63"), 'startAll'), this.state, stryMutAct_9fa48("64") ? [] : (stryCov_9fa48("64"), [stryMutAct_9fa48("65") ? "" : (stryCov_9fa48("65"), 'INITIALIZED'), stryMutAct_9fa48("66") ? "" : (stryCov_9fa48("66"), 'STOPPED')]));
        }
      }
      console.log(stryMutAct_9fa48("67") ? `` : (stryCov_9fa48("67"), `[Supervisor] Starting ${this.plugins.size} plugins...`));
      for (const plugin of Array.from(this.plugins.values())) {
        if (stryMutAct_9fa48("68")) {
          {}
        } else {
          stryCov_9fa48("68");
          try {
            if (stryMutAct_9fa48("69")) {
              {}
            } else {
              stryCov_9fa48("69");
              await plugin.start();
              console.log(stryMutAct_9fa48("70") ? `` : (stryCov_9fa48("70"), `[Supervisor] Started: ${plugin.name}`));
            }
          } catch (error) {
            if (stryMutAct_9fa48("71")) {
              {}
            } else {
              stryCov_9fa48("71");
              console.error(stryMutAct_9fa48("72") ? `` : (stryCov_9fa48("72"), `[Supervisor] Failed to start plugin: ${plugin.name}`), error);
              throw error;
            }
          }
        }
      }
      this.state = stryMutAct_9fa48("73") ? "" : (stryCov_9fa48("73"), 'RUNNING');
    }
  }
  public async stopAll(): Promise<void> {
    if (stryMutAct_9fa48("74")) {
      {}
    } else {
      stryCov_9fa48("74");
      if (stryMutAct_9fa48("77") ? this.state === 'RUNNING' : stryMutAct_9fa48("76") ? false : stryMutAct_9fa48("75") ? true : (stryCov_9fa48("75", "76", "77"), this.state !== (stryMutAct_9fa48("78") ? "" : (stryCov_9fa48("78"), 'RUNNING')))) {
        if (stryMutAct_9fa48("79")) {
          {}
        } else {
          stryCov_9fa48("79");
          throw new LifecycleGateError(stryMutAct_9fa48("80") ? "" : (stryCov_9fa48("80"), 'stopAll'), this.state, stryMutAct_9fa48("81") ? [] : (stryCov_9fa48("81"), [stryMutAct_9fa48("82") ? "" : (stryCov_9fa48("82"), 'RUNNING')]));
        }
      }
      console.log(stryMutAct_9fa48("83") ? `` : (stryCov_9fa48("83"), `[Supervisor] Stopping ${this.plugins.size} plugins...`));
      const reversed = stryMutAct_9fa48("84") ? Array.from(this.plugins.values()) : (stryCov_9fa48("84"), Array.from(this.plugins.values()).reverse());
      for (const plugin of reversed) {
        if (stryMutAct_9fa48("85")) {
          {}
        } else {
          stryCov_9fa48("85");
          try {
            if (stryMutAct_9fa48("86")) {
              {}
            } else {
              stryCov_9fa48("86");
              await plugin.stop();
              console.log(stryMutAct_9fa48("87") ? `` : (stryCov_9fa48("87"), `[Supervisor] Stopped: ${plugin.name}`));
            }
          } catch (error) {
            if (stryMutAct_9fa48("88")) {
              {}
            } else {
              stryCov_9fa48("88");
              console.error(stryMutAct_9fa48("89") ? `` : (stryCov_9fa48("89"), `[Supervisor] Failed to stop plugin: ${plugin.name}`), error);
              // Non-fatal: continue stopping remaining plugins
            }
          }
        }
      }
      this.state = stryMutAct_9fa48("90") ? "" : (stryCov_9fa48("90"), 'STOPPED');
    }
  }
  public async destroyAll(): Promise<void> {
    if (stryMutAct_9fa48("91")) {
      {}
    } else {
      stryCov_9fa48("91");
      if (stryMutAct_9fa48("94") ? this.state !== 'DESTROYED' : stryMutAct_9fa48("93") ? false : stryMutAct_9fa48("92") ? true : (stryCov_9fa48("92", "93", "94"), this.state === (stryMutAct_9fa48("95") ? "" : (stryCov_9fa48("95"), 'DESTROYED')))) {
        if (stryMutAct_9fa48("96")) {
          {}
        } else {
          stryCov_9fa48("96");
          console.warn(stryMutAct_9fa48("97") ? `` : (stryCov_9fa48("97"), `[Supervisor] destroyAll() called on an already-DESTROYED supervisor — no-op.`));
          return;
        }
      }
      console.log(stryMutAct_9fa48("98") ? `` : (stryCov_9fa48("98"), `[Supervisor] Destroying ${this.plugins.size} plugins...`));
      const reversed = stryMutAct_9fa48("99") ? Array.from(this.plugins.values()) : (stryCov_9fa48("99"), Array.from(this.plugins.values()).reverse());
      for (const plugin of reversed) {
        if (stryMutAct_9fa48("100")) {
          {}
        } else {
          stryCov_9fa48("100");
          try {
            if (stryMutAct_9fa48("101")) {
              {}
            } else {
              stryCov_9fa48("101");
              await plugin.destroy();
              console.log(stryMutAct_9fa48("102") ? `` : (stryCov_9fa48("102"), `[Supervisor] Destroyed: ${plugin.name}`));
            }
          } catch (error) {
            if (stryMutAct_9fa48("103")) {
              {}
            } else {
              stryCov_9fa48("103");
              console.error(stryMutAct_9fa48("104") ? `` : (stryCov_9fa48("104"), `[Supervisor] Failed to destroy plugin: ${plugin.name}`), error);
            }
          }
        }
      }
      this.plugins.clear();
      this.state = stryMutAct_9fa48("105") ? "" : (stryCov_9fa48("105"), 'DESTROYED');
    }
  }
}