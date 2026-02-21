/**
 * highlander_mutex_adapter.ts
 * 
 * "There can be only one."
 * 
 * This adapter sits in front of the GestureBridge and enforces single-touch
 * semantics on a multi-touch substrate. It acts as a mutex, locking onto the
 * first hand that appears (or the first hand to commit, depending on config)
 * and ignoring all other hands until the active hand is lost or released.
 */
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
import { RawHandData } from './gesture_bridge';
export interface HighlanderConfig {
  /**
   * If true, the mutex only locks when a hand actually commits (pinches).
   * If false, the mutex locks as soon as any hand appears (hovers).
   */
  lockOnCommitOnly: boolean;

  /**
   * If true, hover events (moving without pinching) are completely dropped.
   * The app will only see the pointer when it is actively clicking/dragging.
   */
  dropHoverEvents: boolean;
}
export class HighlanderMutexAdapter {
  private activeHandId: number | null = null;
  private config: HighlanderConfig;
  constructor(config: Partial<HighlanderConfig> = {}) {
    if (stryMutAct_9fa48("401")) {
      {}
    } else {
      stryCov_9fa48("401");
      this.config = stryMutAct_9fa48("402") ? {} : (stryCov_9fa48("402"), {
        lockOnCommitOnly: stryMutAct_9fa48("403") ? config.lockOnCommitOnly && false : (stryCov_9fa48("403"), config.lockOnCommitOnly ?? (stryMutAct_9fa48("404") ? true : (stryCov_9fa48("404"), false))),
        dropHoverEvents: stryMutAct_9fa48("405") ? config.dropHoverEvents && false : (stryCov_9fa48("405"), config.dropHoverEvents ?? (stryMutAct_9fa48("406") ? true : (stryCov_9fa48("406"), false)))
      });
    }
  }

  /**
   * Filters an array of raw hand data, returning only the data for the active hand.
   * Manages the mutex state internally.
   * 
   * @param hands The raw multi-touch frame data
   * @returns An array containing at most one hand (the active one)
   */
  public filterFrame(hands: RawHandData[]): RawHandData[] {
    if (stryMutAct_9fa48("407")) {
      {}
    } else {
      stryCov_9fa48("407");
      if (stryMutAct_9fa48("410") ? hands.length !== 0 : stryMutAct_9fa48("409") ? false : stryMutAct_9fa48("408") ? true : (stryCov_9fa48("408", "409", "410"), hands.length === 0)) {
        if (stryMutAct_9fa48("411")) {
          {}
        } else {
          stryCov_9fa48("411");
          // No hands visible. Release the mutex.
          this.activeHandId = null;
          return stryMutAct_9fa48("412") ? ["Stryker was here"] : (stryCov_9fa48("412"), []);
        }
      }

      // 1. Check if our currently active hand is still present
      if (stryMutAct_9fa48("415") ? this.activeHandId === null : stryMutAct_9fa48("414") ? false : stryMutAct_9fa48("413") ? true : (stryCov_9fa48("413", "414", "415"), this.activeHandId !== null)) {
        if (stryMutAct_9fa48("416")) {
          {}
        } else {
          stryCov_9fa48("416");
          const activeHand = hands.find(stryMutAct_9fa48("417") ? () => undefined : (stryCov_9fa48("417"), h => stryMutAct_9fa48("420") ? h.handId !== this.activeHandId : stryMutAct_9fa48("419") ? false : stryMutAct_9fa48("418") ? true : (stryCov_9fa48("418", "419", "420"), h.handId === this.activeHandId)));
          if (stryMutAct_9fa48("422") ? false : stryMutAct_9fa48("421") ? true : (stryCov_9fa48("421", "422"), activeHand)) {
            if (stryMutAct_9fa48("423")) {
              {}
            } else {
              stryCov_9fa48("423");
              // The active hand is still here. Keep the lock.
              return this.processActiveHand(activeHand);
            }
          } else {
            if (stryMutAct_9fa48("424")) {
              {}
            } else {
              stryCov_9fa48("424");
              // The active hand disappeared. Release the lock.
              this.activeHandId = null;
            }
          }
        }
      }

      // 2. We don't have an active hand. Try to acquire the lock.
      // Sort by handId to ensure deterministic behavior if multiple hands appear simultaneously
      const sortedHands = stryMutAct_9fa48("425") ? [...hands] : (stryCov_9fa48("425"), (stryMutAct_9fa48("426") ? [] : (stryCov_9fa48("426"), [...hands])).sort(stryMutAct_9fa48("427") ? () => undefined : (stryCov_9fa48("427"), (a, b) => stryMutAct_9fa48("428") ? a.handId + b.handId : (stryCov_9fa48("428"), a.handId - b.handId))));
      for (const hand of sortedHands) {
        if (stryMutAct_9fa48("429")) {
          {}
        } else {
          stryCov_9fa48("429");
          const isCommitting = stryMutAct_9fa48("432") ? hand.gesture === 'pointer_up' || hand.confidence > 0.8 : stryMutAct_9fa48("431") ? false : stryMutAct_9fa48("430") ? true : (stryCov_9fa48("430", "431", "432"), (stryMutAct_9fa48("434") ? hand.gesture !== 'pointer_up' : stryMutAct_9fa48("433") ? true : (stryCov_9fa48("433", "434"), hand.gesture === (stryMutAct_9fa48("435") ? "" : (stryCov_9fa48("435"), 'pointer_up')))) && (stryMutAct_9fa48("438") ? hand.confidence <= 0.8 : stryMutAct_9fa48("437") ? hand.confidence >= 0.8 : stryMutAct_9fa48("436") ? true : (stryCov_9fa48("436", "437", "438"), hand.confidence > 0.8))); // Simple heuristic for commit

          if (stryMutAct_9fa48("440") ? false : stryMutAct_9fa48("439") ? true : (stryCov_9fa48("439", "440"), this.config.lockOnCommitOnly)) {
            if (stryMutAct_9fa48("441")) {
              {}
            } else {
              stryCov_9fa48("441");
              if (stryMutAct_9fa48("443") ? false : stryMutAct_9fa48("442") ? true : (stryCov_9fa48("442", "443"), isCommitting)) {
                if (stryMutAct_9fa48("444")) {
                  {}
                } else {
                  stryCov_9fa48("444");
                  this.activeHandId = hand.handId;
                  return this.processActiveHand(hand);
                }
              }
            }
          } else {
            if (stryMutAct_9fa48("445")) {
              {}
            } else {
              stryCov_9fa48("445");
              // Lock on first sight
              this.activeHandId = hand.handId;
              return this.processActiveHand(hand);
            }
          }
        }
      }

      // No hand acquired the lock (e.g., lockOnCommitOnly is true and no one is pinching)
      return stryMutAct_9fa48("446") ? ["Stryker was here"] : (stryCov_9fa48("446"), []);
    }
  }

  /**
   * Applies the dropHoverEvents configuration to the active hand.
   */
  private processActiveHand(hand: RawHandData): RawHandData[] {
    if (stryMutAct_9fa48("447")) {
      {}
    } else {
      stryCov_9fa48("447");
      if (stryMutAct_9fa48("449") ? false : stryMutAct_9fa48("448") ? true : (stryCov_9fa48("448", "449"), this.config.dropHoverEvents)) {
        if (stryMutAct_9fa48("450")) {
          {}
        } else {
          stryCov_9fa48("450");
          const isCommitting = stryMutAct_9fa48("453") ? hand.gesture === 'pointer_up' || hand.confidence > 0.8 : stryMutAct_9fa48("452") ? false : stryMutAct_9fa48("451") ? true : (stryCov_9fa48("451", "452", "453"), (stryMutAct_9fa48("455") ? hand.gesture !== 'pointer_up' : stryMutAct_9fa48("454") ? true : (stryCov_9fa48("454", "455"), hand.gesture === (stryMutAct_9fa48("456") ? "" : (stryCov_9fa48("456"), 'pointer_up')))) && (stryMutAct_9fa48("459") ? hand.confidence <= 0.8 : stryMutAct_9fa48("458") ? hand.confidence >= 0.8 : stryMutAct_9fa48("457") ? true : (stryCov_9fa48("457", "458", "459"), hand.confidence > 0.8)));
          if (stryMutAct_9fa48("462") ? false : stryMutAct_9fa48("461") ? true : stryMutAct_9fa48("460") ? isCommitting : (stryCov_9fa48("460", "461", "462"), !isCommitting)) {
            if (stryMutAct_9fa48("463")) {
              {}
            } else {
              stryCov_9fa48("463");
              // Drop the event, but keep the lock (we return an empty array so the bridge sees 'none')
              return stryMutAct_9fa48("464") ? ["Stryker was here"] : (stryCov_9fa48("464"), []);
            }
          }
        }
      }
      return stryMutAct_9fa48("465") ? [] : (stryCov_9fa48("465"), [hand]);
    }
  }

  /**
   * Force release the mutex (useful for programmatic resets)
   */
  public release() {
    if (stryMutAct_9fa48("466")) {
      {}
    } else {
      stryCov_9fa48("466");
      this.activeHandId = null;
    }
  }
  public getActiveHandId(): number | null {
    if (stryMutAct_9fa48("467")) {
      {}
    } else {
      stryCov_9fa48("467");
      return this.activeHandId;
    }
  }
}