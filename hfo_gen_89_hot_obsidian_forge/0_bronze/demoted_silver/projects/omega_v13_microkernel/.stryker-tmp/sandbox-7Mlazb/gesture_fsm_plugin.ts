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
import { GestureFSM } from './gesture_fsm';
import { RawHandData } from './gesture_bridge';
import { Plugin, PluginContext } from './plugin_supervisor';
import type { ConfigManager, ConfigMosaic } from './config_ui';
export class GestureFSMPlugin implements Plugin {
  public name = stryMutAct_9fa48("297") ? "" : (stryCov_9fa48("297"), 'GestureFSMPlugin');
  public version = stryMutAct_9fa48("298") ? "" : (stryCov_9fa48("298"), '1.0.0');
  private fsmInstances: Map<number, GestureFSM> = new Map();
  private context!: PluginContext;

  // Config wiring — resolved from PAL at init()
  private configManager?: ConfigManager;
  private configListener?: (cfg: ConfigMosaic) => void;
  /** Cached FSM config applied to new instances and on config-change. */
  private fsmConfig: {
    dwellReadyMs: number;
    dwellCommitMs: number;
    coastTimeoutMs: number;
  } | null = null;

  /**
   * Last known position of each hand during COMMIT_COAST.  Used by the velocity
   * teleport gate (FSM-V5 fix) to detect coast-recovery jumps > TELEPORT_THRESHOLD.
   * Keyed by handId; cleared when the hand leaves coast state.
   */
  private coastPositions: Map<number, {
    x: number;
    y: number;
  }> = new Map();

  /** Squared distance threshold above which a coast-recovery transition is considered
   *  a teleport and a synthetic pointerup is injected before the recovery pointerdown.
   *  0.15 normalised units = 15% of viewport width.  Tunable via PAL key 'TeleportThresholdSq'. */
  private readonly TELEPORT_THRESHOLD_SQ = stryMutAct_9fa48("299") ? 0.15 / 0.15 : (stryCov_9fa48("299"), 0.15 * 0.15);

  // Stable bound references — required so unsubscribe() can remove the exact same fn object.
  // Using .bind(this) inline in subscribe() creates an anonymous fn that can never be removed.
  // Scenario: Given GestureFSMPlugin destroyed, Then FRAME_PROCESSED/STILLNESS_DETECTED listeners
  //           are removed from the bus (no zombie callbacks on a dead plugin instance).
  private readonly boundOnFrameProcessed: (data: any) => void;
  private readonly boundOnStillnessDetected: (data: any) => void;
  constructor() {
    if (stryMutAct_9fa48("300")) {
      {}
    } else {
      stryCov_9fa48("300");
      this.boundOnFrameProcessed = this.onFrameProcessed.bind(this);
      this.boundOnStillnessDetected = this.onStillnessDetected.bind(this);
    }
  }
  public init(context: PluginContext): void {
    if (stryMutAct_9fa48("301")) {
      {}
    } else {
      stryCov_9fa48("301");
      this.context = context;
      this.context.eventBus.subscribe(stryMutAct_9fa48("302") ? "" : (stryCov_9fa48("302"), 'FRAME_PROCESSED'), this.boundOnFrameProcessed);
      this.context.eventBus.subscribe(stryMutAct_9fa48("303") ? "" : (stryCov_9fa48("303"), 'STILLNESS_DETECTED'), this.boundOnStillnessDetected);

      // Wire ConfigManager from PAL so dwell thresholds are hot-swappable
      const cm = context.pal.resolve<ConfigManager>(stryMutAct_9fa48("304") ? "" : (stryCov_9fa48("304"), 'ConfigManager'));
      if (stryMutAct_9fa48("306") ? false : stryMutAct_9fa48("305") ? true : (stryCov_9fa48("305", "306"), cm)) {
        if (stryMutAct_9fa48("307")) {
          {}
        } else {
          stryCov_9fa48("307");
          this.configManager = cm;
          this.configListener = (cfg: ConfigMosaic) => {
            if (stryMutAct_9fa48("308")) {
              {}
            } else {
              stryCov_9fa48("308");
              this.fsmConfig = stryMutAct_9fa48("309") ? {} : (stryCov_9fa48("309"), {
                dwellReadyMs: cfg.fsm_dwell_ready,
                dwellCommitMs: cfg.fsm_dwell_commit,
                coastTimeoutMs: cfg.fsm_coast_timeout_ms
              });
              // Hot-update all live FSM instances
              for (const fsm of this.fsmInstances.values()) {
                if (stryMutAct_9fa48("310")) {
                  {}
                } else {
                  stryCov_9fa48("310");
                  fsm.configure(this.fsmConfig);
                }
              }
            }
          };
          // subscribe() fires immediately with the current config
          cm.subscribe(this.configListener);
        }
      }
    }
  }
  public start(): void {
    if (stryMutAct_9fa48("311")) {
      {}
    } else {
      stryCov_9fa48("311");
      console.log(stryMutAct_9fa48("312") ? "" : (stryCov_9fa48("312"), '[GestureFSMPlugin] Started'));
    }
  }
  public stop(): void {
    if (stryMutAct_9fa48("313")) {
      {}
    } else {
      stryCov_9fa48("313");
      if (stryMutAct_9fa48("316") ? this.configManager || this.configListener : stryMutAct_9fa48("315") ? false : stryMutAct_9fa48("314") ? true : (stryCov_9fa48("314", "315", "316"), this.configManager && this.configListener)) {
        if (stryMutAct_9fa48("317")) {
          {}
        } else {
          stryCov_9fa48("317");
          this.configManager.unsubscribe(this.configListener);
        }
      }
      console.log(stryMutAct_9fa48("318") ? "" : (stryCov_9fa48("318"), '[GestureFSMPlugin] Stopped'));
    }
  }
  public destroy(): void {
    if (stryMutAct_9fa48("319")) {
      {}
    } else {
      stryCov_9fa48("319");
      if (stryMutAct_9fa48("322") ? this.context.eventBus : stryMutAct_9fa48("321") ? false : stryMutAct_9fa48("320") ? true : (stryCov_9fa48("320", "321", "322"), this.context?.eventBus)) {
        if (stryMutAct_9fa48("323")) {
          {}
        } else {
          stryCov_9fa48("323");
          this.context.eventBus.unsubscribe(stryMutAct_9fa48("324") ? "" : (stryCov_9fa48("324"), 'FRAME_PROCESSED'), this.boundOnFrameProcessed);
          this.context.eventBus.unsubscribe(stryMutAct_9fa48("325") ? "" : (stryCov_9fa48("325"), 'STILLNESS_DETECTED'), this.boundOnStillnessDetected);
        }
      }
      this.fsmInstances.clear();
    }
  }
  private onStillnessDetected(data: {
    handId: number;
  }) {
    if (stryMutAct_9fa48("326")) {
      {}
    } else {
      stryCov_9fa48("326");
      const fsm = this.fsmInstances.get(data.handId);
      if (stryMutAct_9fa48("328") ? false : stryMutAct_9fa48("327") ? true : (stryCov_9fa48("327", "328"), fsm)) {
        if (stryMutAct_9fa48("329")) {
          {}
        } else {
          stryCov_9fa48("329");
          fsm.forceCoast();
        }
      }
    }
  }
  private onFrameProcessed(hands: RawHandData[]) {
    if (stryMutAct_9fa48("330")) {
      {}
    } else {
      stryCov_9fa48("330");
      const currentHandIds = new Set<number>();
      for (const hand of hands) {
        if (stryMutAct_9fa48("331")) {
          {}
        } else {
          stryCov_9fa48("331");
          currentHandIds.add(hand.handId);
          if (stryMutAct_9fa48("334") ? false : stryMutAct_9fa48("333") ? true : stryMutAct_9fa48("332") ? this.fsmInstances.has(hand.handId) : (stryCov_9fa48("332", "333", "334"), !this.fsmInstances.has(hand.handId))) {
            if (stryMutAct_9fa48("335")) {
              {}
            } else {
              stryCov_9fa48("335");
              const newFsm = new GestureFSM();
              if (stryMutAct_9fa48("337") ? false : stryMutAct_9fa48("336") ? true : (stryCov_9fa48("336", "337"), this.fsmConfig)) newFsm.configure(this.fsmConfig);
              this.fsmInstances.set(hand.handId, newFsm);
            }
          }
          const fsm = this.fsmInstances.get(hand.handId)!;
          const previousState = fsm.state;

          // Capture pre-frame coast/pinch status for FSM-V5 velocity teleport gate
          const prevIsPinching = fsm.isPinching();
          const prevIsCoasting = fsm.isCoasting();
          const prevCoastPos = this.coastPositions.get(hand.handId);

          // Use caller-supplied timestamp when available (e.g. Playwright test harness)
          // to keep dwell framerate-independent regardless of actual MediaPipe fps.
          const nowMs = stryMutAct_9fa48("338") ? hand.frameTimeMs && performance.now() : (stryCov_9fa48("338"), hand.frameTimeMs ?? performance.now());
          fsm.processFrame(hand.gesture, hand.confidence, hand.x, hand.y, nowMs);
          const currentState = fsm.state;
          if (stryMutAct_9fa48("341") ? previousState === currentState : stryMutAct_9fa48("340") ? false : stryMutAct_9fa48("339") ? true : (stryCov_9fa48("339", "340", "341"), previousState !== currentState)) {
            if (stryMutAct_9fa48("342")) {
              {}
            } else {
              stryCov_9fa48("342");
              this.context.eventBus.publish(stryMutAct_9fa48("343") ? "" : (stryCov_9fa48("343"), 'STATE_CHANGE'), stryMutAct_9fa48("344") ? {} : (stryCov_9fa48("344"), {
                handId: hand.handId,
                previousState: previousState.type,
                currentState: currentState.type
              }));
            }
          }
          const isPinching = fsm.isPinching();
          const isCoasting = fsm.isCoasting();

          // ── FSM-V5 velocity teleport gate ─────────────────────────────────────────────
          // COMMIT_COAST → COMMIT_POINTER recovery with a large position jump = ghost stroke.
          // Inject a synthetic pointerup at the *last coast position* so W3CPointerFabric
          // fires pointerup before the recovered pointerdown at the new position.
          if (stryMutAct_9fa48("347") ? prevIsPinching && prevIsCoasting && isPinching && !isCoasting || prevCoastPos : stryMutAct_9fa48("346") ? false : stryMutAct_9fa48("345") ? true : (stryCov_9fa48("345", "346", "347"), (stryMutAct_9fa48("349") ? prevIsPinching && prevIsCoasting && isPinching || !isCoasting : stryMutAct_9fa48("348") ? true : (stryCov_9fa48("348", "349"), (stryMutAct_9fa48("351") ? prevIsPinching && prevIsCoasting || isPinching : stryMutAct_9fa48("350") ? true : (stryCov_9fa48("350", "351"), (stryMutAct_9fa48("353") ? prevIsPinching || prevIsCoasting : stryMutAct_9fa48("352") ? true : (stryCov_9fa48("352", "353"), prevIsPinching && prevIsCoasting)) && isPinching)) && (stryMutAct_9fa48("354") ? isCoasting : (stryCov_9fa48("354"), !isCoasting)))) && prevCoastPos)) {
            if (stryMutAct_9fa48("355")) {
              {}
            } else {
              stryCov_9fa48("355");
              const dx = stryMutAct_9fa48("356") ? hand.x + prevCoastPos.x : (stryCov_9fa48("356"), hand.x - prevCoastPos.x);
              const dy = stryMutAct_9fa48("357") ? hand.y + prevCoastPos.y : (stryCov_9fa48("357"), hand.y - prevCoastPos.y);
              const threshold = stryMutAct_9fa48("358") ? this.context.pal.resolve<number>('TeleportThresholdSq') && this.TELEPORT_THRESHOLD_SQ : (stryCov_9fa48("358"), this.context.pal.resolve<number>(stryMutAct_9fa48("359") ? "" : (stryCov_9fa48("359"), 'TeleportThresholdSq')) ?? this.TELEPORT_THRESHOLD_SQ);
              if (stryMutAct_9fa48("363") ? dx * dx + dy * dy <= threshold : stryMutAct_9fa48("362") ? dx * dx + dy * dy >= threshold : stryMutAct_9fa48("361") ? false : stryMutAct_9fa48("360") ? true : (stryCov_9fa48("360", "361", "362", "363"), (stryMutAct_9fa48("364") ? dx * dx - dy * dy : (stryCov_9fa48("364"), (stryMutAct_9fa48("365") ? dx / dx : (stryCov_9fa48("365"), dx * dx)) + (stryMutAct_9fa48("366") ? dy / dy : (stryCov_9fa48("366"), dy * dy)))) > threshold)) {
                if (stryMutAct_9fa48("367")) {
                  {}
                } else {
                  stryCov_9fa48("367");
                  // Emit synthetic pointerup at the last safe coast position to break the stroke
                  this.context.eventBus.publish(stryMutAct_9fa48("368") ? "" : (stryCov_9fa48("368"), 'POINTER_UPDATE'), stryMutAct_9fa48("369") ? {} : (stryCov_9fa48("369"), {
                    handId: hand.handId,
                    x: prevCoastPos.x,
                    y: prevCoastPos.y,
                    isPinching: stryMutAct_9fa48("370") ? true : (stryCov_9fa48("370"), false),
                    // forces pointerup in W3CPointerFabric
                    gesture: hand.gesture,
                    confidence: hand.confidence,
                    rawLandmarks: undefined
                  }));
                }
              }
            }
          }

          // Track the hand's position while it is in COMMIT_COAST so the gate above
          // always has a valid “last safe” reference on recovery.
          if (stryMutAct_9fa48("373") ? isPinching || isCoasting : stryMutAct_9fa48("372") ? false : stryMutAct_9fa48("371") ? true : (stryCov_9fa48("371", "372", "373"), isPinching && isCoasting)) {
            if (stryMutAct_9fa48("374")) {
              {}
            } else {
              stryCov_9fa48("374");
              this.coastPositions.set(hand.handId, stryMutAct_9fa48("375") ? {} : (stryCov_9fa48("375"), {
                x: hand.x,
                y: hand.y
              }));
            }
          } else {
            if (stryMutAct_9fa48("376")) {
              {}
            } else {
              stryCov_9fa48("376");
              this.coastPositions.delete(hand.handId);
            }
          }
          this.context.eventBus.publish(stryMutAct_9fa48("377") ? "" : (stryCov_9fa48("377"), 'POINTER_UPDATE'), stryMutAct_9fa48("378") ? {} : (stryCov_9fa48("378"), {
            handId: hand.handId,
            x: hand.x,
            y: hand.y,
            isPinching,
            gesture: hand.gesture,
            confidence: hand.confidence,
            rawLandmarks: hand.rawLandmarks
          }));
        }
      }
      for (const [handId, fsm] of this.fsmInstances.entries()) {
        if (stryMutAct_9fa48("379")) {
          {}
        } else {
          stryCov_9fa48("379");
          if (stryMutAct_9fa48("382") ? false : stryMutAct_9fa48("381") ? true : stryMutAct_9fa48("380") ? currentHandIds.has(handId) : (stryCov_9fa48("380", "381", "382"), !currentHandIds.has(handId))) {
            if (stryMutAct_9fa48("383")) {
              {}
            } else {
              stryCov_9fa48("383");
              fsm.processFrame(stryMutAct_9fa48("384") ? "" : (stryCov_9fa48("384"), 'none'), 0.0, stryMutAct_9fa48("385") ? +1 : (stryCov_9fa48("385"), -1), stryMutAct_9fa48("386") ? +1 : (stryCov_9fa48("386"), -1), performance.now());
              if (stryMutAct_9fa48("389") ? fsm.state.type !== 'IDLE' : stryMutAct_9fa48("388") ? false : stryMutAct_9fa48("387") ? true : (stryCov_9fa48("387", "388", "389"), fsm.state.type === (stryMutAct_9fa48("390") ? "" : (stryCov_9fa48("390"), 'IDLE')))) {
                if (stryMutAct_9fa48("391")) {
                  {}
                } else {
                  stryCov_9fa48("391");
                  this.context.eventBus.publish(stryMutAct_9fa48("392") ? "" : (stryCov_9fa48("392"), 'POINTER_COAST'), stryMutAct_9fa48("393") ? {} : (stryCov_9fa48("393"), {
                    handId,
                    isPinching: stryMutAct_9fa48("394") ? true : (stryCov_9fa48("394"), false),
                    destroy: stryMutAct_9fa48("395") ? false : (stryCov_9fa48("395"), true)
                  }));
                  this.fsmInstances.delete(handId);
                }
              } else {
                if (stryMutAct_9fa48("396")) {
                  {}
                } else {
                  stryCov_9fa48("396");
                  const isPinching = fsm.isPinching();
                  this.context.eventBus.publish(stryMutAct_9fa48("397") ? "" : (stryCov_9fa48("397"), 'POINTER_COAST'), stryMutAct_9fa48("398") ? {} : (stryCov_9fa48("398"), {
                    handId,
                    isPinching,
                    destroy: stryMutAct_9fa48("399") ? true : (stryCov_9fa48("399"), false)
                  }));
                }
              }
            }
          }
        }
      }
    }
  }
  public getHandState(handId: number): string | null {
    if (stryMutAct_9fa48("400")) {
      {}
    } else {
      stryCov_9fa48("400");
      const fsm = this.fsmInstances.get(handId);
      return fsm ? fsm.state.type : null;
    }
  }
}