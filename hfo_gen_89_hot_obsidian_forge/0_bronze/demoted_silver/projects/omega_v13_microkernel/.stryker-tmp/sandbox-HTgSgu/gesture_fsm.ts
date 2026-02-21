/**
 * gesture_fsm.ts
 * 
 * A lightweight TypeScript implementation of the SCXML logic defined in gesture_fsm.scxml.
 * This class manages the state of a single hand, including confidence hysteresis (Schmitt trigger)
 * and asymmetrical leaky bucket (dwell) logic.
 * 
 * ARCHITECTURAL NOTE (SCXML vs TS Sync):
 * While this manual TS implementation is highly optimized for a 60fps render loop, 
 * it carries the risk of drifting out of sync with the formal `gesture_fsm.scxml` specification.
 * In a future iteration, consider a build-step compiler that generates this TS class 
 * directly from the SCXML file to guarantee "correct by construction" parity.
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
import { FsmState, StateIdle, StateIdleCoast, StateReady, StateReadyCoast, StateCommit, StateCommitCoast } from './types.js';
export class GestureFSM {
  public state: FsmState = new StateIdle();

  // Schmitt Trigger Thresholds (framerate-independent — no change needed)
  private readonly conf_high = 0.64;
  private readonly conf_low = 0.50;

  // Dwell limits — milliseconds, NOT frames (framerate-independent)
  private dwell_limit_ready_ms = 100;
  private dwell_limit_commit_ms = 100;

  // Current State Variables
  private current_confidence = 0.0;
  /** Accumulated qualifying-gesture time in ms (leaky bucket, 2:1 leak ratio). */
  private dwell_accumulator_ms = 0;
  public ready_bucket_ms = 0;
  public idle_bucket_ms = 0;

  // Coast Timeout — ms until COAST states hard-reset to IDLE
  private coast_elapsed_ms = 0;
  private coast_timeout_ms = 500;

  /** Timestamp (ms) of the previous processFrame call.  NaN = first call. */
  private lastFrameMs = NaN;

  /**
   * Hot-swap dwell and coast thresholds from the ConfigMosaic.
   * Safe to call during live tracking — takes effect on the next frame.
   */
  public configure(cfg: {
    dwellReadyMs?: number;
    dwellCommitMs?: number;
    coastTimeoutMs?: number;
  }): void {
    if (stryMutAct_9fa48("0")) {
      {}
    } else {
      stryCov_9fa48("0");
      if (stryMutAct_9fa48("3") ? cfg.dwellReadyMs === undefined : stryMutAct_9fa48("2") ? false : stryMutAct_9fa48("1") ? true : (stryCov_9fa48("1", "2", "3"), cfg.dwellReadyMs !== undefined)) this.dwell_limit_ready_ms = cfg.dwellReadyMs;
      if (stryMutAct_9fa48("6") ? cfg.dwellCommitMs === undefined : stryMutAct_9fa48("5") ? false : stryMutAct_9fa48("4") ? true : (stryCov_9fa48("4", "5", "6"), cfg.dwellCommitMs !== undefined)) this.dwell_limit_commit_ms = cfg.dwellCommitMs;
      if (stryMutAct_9fa48("9") ? cfg.coastTimeoutMs === undefined : stryMutAct_9fa48("8") ? false : stryMutAct_9fa48("7") ? true : (stryCov_9fa48("7", "8", "9"), cfg.coastTimeoutMs !== undefined)) this.coast_timeout_ms = cfg.coastTimeoutMs;
    }
  }

  /**
   * Process a frame of data for this specific hand
   * @param gesture The detected gesture name (e.g., 'open_palm', 'closed_fist', 'pointer_up')
   * @param confidence The confidence score of the gesture (0.0 to 1.0)
   * @param x The normalized X coordinate (0.0 to 1.0)
   * @param y The normalized Y coordinate (0.0 to 1.0)
   */
  /**
   * @param nowMs  Wall-clock timestamp in ms (performance.now()).
   *               Caller should supply the same timestamp used to build the
   *               RawHandData.frameTimeMs so dwell is framerate-independent.
   *               Default falls back to performance.now() at call time.
   */
  public processFrame(gesture: string, confidence: number, x: RawCoord = -1 as RawCoord, y: RawCoord = -1 as RawCoord, nowMs = performance.now()) {
    if (stryMutAct_9fa48("10")) {
      {}
    } else {
      stryCov_9fa48("10");
      // Delta-time in ms since last frame.  First call → 0 (no accumulation).
      const deltaMs = isNaN(this.lastFrameMs) ? 0 : stryMutAct_9fa48("11") ? nowMs + this.lastFrameMs : (stryCov_9fa48("11"), nowMs - this.lastFrameMs);
      this.lastFrameMs = nowMs;
      this.current_confidence = confidence;

      // 1. Handle Coast Timeouts (Total Loss)
      if (stryMutAct_9fa48("13") ? false : stryMutAct_9fa48("12") ? true : (stryCov_9fa48("12", "13"), this.state.type.includes(stryMutAct_9fa48("14") ? "" : (stryCov_9fa48("14"), 'COAST')))) {
        if (stryMutAct_9fa48("15")) {
          {}
        } else {
          stryCov_9fa48("15");
          stryMutAct_9fa48("16") ? this.coast_elapsed_ms -= deltaMs : (stryCov_9fa48("16"), this.coast_elapsed_ms += deltaMs);
          if (stryMutAct_9fa48("20") ? this.coast_elapsed_ms < this.coast_timeout_ms : stryMutAct_9fa48("19") ? this.coast_elapsed_ms > this.coast_timeout_ms : stryMutAct_9fa48("18") ? false : stryMutAct_9fa48("17") ? true : (stryCov_9fa48("17", "18", "19", "20"), this.coast_elapsed_ms >= this.coast_timeout_ms)) {
            if (stryMutAct_9fa48("21")) {
              {}
            } else {
              stryCov_9fa48("21");
              this.state = new StateIdle(); // Reset to IDLE on total loss
              this.dwell_accumulator_ms = 0;
              return;
            }
          }
        }
      } else {
        if (stryMutAct_9fa48("22")) {
          {}
        } else {
          stryCov_9fa48("22");
          this.coast_elapsed_ms = 0; // Reset coast timer when tracking is active
        }
      }

      // 2. State Machine Logic
      switch (this.state.type) {
        case stryMutAct_9fa48("24") ? "" : (stryCov_9fa48("24"), 'IDLE'):
          if (stryMutAct_9fa48("23")) {} else {
            stryCov_9fa48("23");
            this.handleIdle(gesture, deltaMs);
            break;
          }
        case stryMutAct_9fa48("26") ? "" : (stryCov_9fa48("26"), 'IDLE_COAST'):
          if (stryMutAct_9fa48("25")) {} else {
            stryCov_9fa48("25");
            this.handleIdleCoast();
            break;
          }
        case stryMutAct_9fa48("28") ? "" : (stryCov_9fa48("28"), 'READY'):
          if (stryMutAct_9fa48("27")) {} else {
            stryCov_9fa48("27");
            this.handleReady(gesture, deltaMs);
            break;
          }
        case stryMutAct_9fa48("30") ? "" : (stryCov_9fa48("30"), 'READY_COAST'):
          if (stryMutAct_9fa48("29")) {} else {
            stryCov_9fa48("29");
            this.handleReadyCoast();
            break;
          }
        case stryMutAct_9fa48("32") ? "" : (stryCov_9fa48("32"), 'COMMIT_POINTER'):
          if (stryMutAct_9fa48("31")) {} else {
            stryCov_9fa48("31");
            this.handleCommitPointer(gesture, deltaMs);
            break;
          }
        case stryMutAct_9fa48("34") ? "" : (stryCov_9fa48("34"), 'COMMIT_COAST'):
          if (stryMutAct_9fa48("33")) {} else {
            stryCov_9fa48("33");
            this.handleCommitCoast();
            break;
          }
      }
    }
  }
  private handleIdle(gesture: string, deltaMs: number) {
    if (stryMutAct_9fa48("35")) {
      {}
    } else {
      stryCov_9fa48("35");
      // Schmitt Trigger: Drop to COAST
      if (stryMutAct_9fa48("39") ? this.current_confidence >= this.conf_low : stryMutAct_9fa48("38") ? this.current_confidence <= this.conf_low : stryMutAct_9fa48("37") ? false : stryMutAct_9fa48("36") ? true : (stryCov_9fa48("36", "37", "38", "39"), this.current_confidence < this.conf_low)) {
        if (stryMutAct_9fa48("40")) {
          {}
        } else {
          stryCov_9fa48("40");
          this.state = new StateIdleCoast();
          return;
        }
      }

      // Reinforce IDLE
      if (stryMutAct_9fa48("43") ? gesture === 'closed_fist' || this.current_confidence >= this.conf_high : stryMutAct_9fa48("42") ? false : stryMutAct_9fa48("41") ? true : (stryCov_9fa48("41", "42", "43"), (stryMutAct_9fa48("45") ? gesture !== 'closed_fist' : stryMutAct_9fa48("44") ? true : (stryCov_9fa48("44", "45"), gesture === (stryMutAct_9fa48("46") ? "" : (stryCov_9fa48("46"), 'closed_fist')))) && (stryMutAct_9fa48("49") ? this.current_confidence < this.conf_high : stryMutAct_9fa48("48") ? this.current_confidence > this.conf_high : stryMutAct_9fa48("47") ? true : (stryCov_9fa48("47", "48", "49"), this.current_confidence >= this.conf_high)))) {
        if (stryMutAct_9fa48("50")) {
          {}
        } else {
          stryCov_9fa48("50");
          this.dwell_accumulator_ms = 0;
          this.ready_bucket_ms = 0;
        }
      }

      // Leaky Bucket for READY (ms-based, 2:1 leak ratio)
      if (stryMutAct_9fa48("53") ? gesture === 'open_palm' || this.current_confidence >= this.conf_high : stryMutAct_9fa48("52") ? false : stryMutAct_9fa48("51") ? true : (stryCov_9fa48("51", "52", "53"), (stryMutAct_9fa48("55") ? gesture !== 'open_palm' : stryMutAct_9fa48("54") ? true : (stryCov_9fa48("54", "55"), gesture === (stryMutAct_9fa48("56") ? "" : (stryCov_9fa48("56"), 'open_palm')))) && (stryMutAct_9fa48("59") ? this.current_confidence < this.conf_high : stryMutAct_9fa48("58") ? this.current_confidence > this.conf_high : stryMutAct_9fa48("57") ? true : (stryCov_9fa48("57", "58", "59"), this.current_confidence >= this.conf_high)))) {
        if (stryMutAct_9fa48("60")) {
          {}
        } else {
          stryCov_9fa48("60");
          stryMutAct_9fa48("61") ? this.dwell_accumulator_ms -= deltaMs : (stryCov_9fa48("61"), this.dwell_accumulator_ms += deltaMs);
          stryMutAct_9fa48("62") ? this.ready_bucket_ms -= deltaMs : (stryCov_9fa48("62"), this.ready_bucket_ms += deltaMs);
        }
      } else if (stryMutAct_9fa48("65") ? this.current_confidence >= this.conf_low || this.current_confidence < this.conf_high : stryMutAct_9fa48("64") ? false : stryMutAct_9fa48("63") ? true : (stryCov_9fa48("63", "64", "65"), (stryMutAct_9fa48("68") ? this.current_confidence < this.conf_low : stryMutAct_9fa48("67") ? this.current_confidence > this.conf_low : stryMutAct_9fa48("66") ? true : (stryCov_9fa48("66", "67", "68"), this.current_confidence >= this.conf_low)) && (stryMutAct_9fa48("71") ? this.current_confidence >= this.conf_high : stryMutAct_9fa48("70") ? this.current_confidence <= this.conf_high : stryMutAct_9fa48("69") ? true : (stryCov_9fa48("69", "70", "71"), this.current_confidence < this.conf_high)))) {
        if (stryMutAct_9fa48("72")) {
          {}
        } else {
          stryCov_9fa48("72");
          this.dwell_accumulator_ms = stryMutAct_9fa48("73") ? Math.min(0, this.dwell_accumulator_ms - 2 * deltaMs) : (stryCov_9fa48("73"), Math.max(0, stryMutAct_9fa48("74") ? this.dwell_accumulator_ms + 2 * deltaMs : (stryCov_9fa48("74"), this.dwell_accumulator_ms - (stryMutAct_9fa48("75") ? 2 / deltaMs : (stryCov_9fa48("75"), 2 * deltaMs)))));
          this.ready_bucket_ms = stryMutAct_9fa48("76") ? Math.min(0, this.ready_bucket_ms - 2 * deltaMs) : (stryCov_9fa48("76"), Math.max(0, stryMutAct_9fa48("77") ? this.ready_bucket_ms + 2 * deltaMs : (stryCov_9fa48("77"), this.ready_bucket_ms - (stryMutAct_9fa48("78") ? 2 / deltaMs : (stryCov_9fa48("78"), 2 * deltaMs)))));
        }
      } else if (stryMutAct_9fa48("81") ? gesture !== 'open_palm' || gesture !== 'closed_fist' : stryMutAct_9fa48("80") ? false : stryMutAct_9fa48("79") ? true : (stryCov_9fa48("79", "80", "81"), (stryMutAct_9fa48("83") ? gesture === 'open_palm' : stryMutAct_9fa48("82") ? true : (stryCov_9fa48("82", "83"), gesture !== (stryMutAct_9fa48("84") ? "" : (stryCov_9fa48("84"), 'open_palm')))) && (stryMutAct_9fa48("86") ? gesture === 'closed_fist' : stryMutAct_9fa48("85") ? true : (stryCov_9fa48("85", "86"), gesture !== (stryMutAct_9fa48("87") ? "" : (stryCov_9fa48("87"), 'closed_fist')))))) {
        if (stryMutAct_9fa48("88")) {
          {}
        } else {
          stryCov_9fa48("88");
          this.dwell_accumulator_ms = stryMutAct_9fa48("89") ? Math.min(0, this.dwell_accumulator_ms - 2 * deltaMs) : (stryCov_9fa48("89"), Math.max(0, stryMutAct_9fa48("90") ? this.dwell_accumulator_ms + 2 * deltaMs : (stryCov_9fa48("90"), this.dwell_accumulator_ms - (stryMutAct_9fa48("91") ? 2 / deltaMs : (stryCov_9fa48("91"), 2 * deltaMs)))));
          this.ready_bucket_ms = stryMutAct_9fa48("92") ? Math.min(0, this.ready_bucket_ms - 2 * deltaMs) : (stryCov_9fa48("92"), Math.max(0, stryMutAct_9fa48("93") ? this.ready_bucket_ms + 2 * deltaMs : (stryCov_9fa48("93"), this.ready_bucket_ms - (stryMutAct_9fa48("94") ? 2 / deltaMs : (stryCov_9fa48("94"), 2 * deltaMs)))));
        }
      }

      // Transition to READY
      if (stryMutAct_9fa48("98") ? this.dwell_accumulator_ms < this.dwell_limit_ready_ms : stryMutAct_9fa48("97") ? this.dwell_accumulator_ms > this.dwell_limit_ready_ms : stryMutAct_9fa48("96") ? false : stryMutAct_9fa48("95") ? true : (stryCov_9fa48("95", "96", "97", "98"), this.dwell_accumulator_ms >= this.dwell_limit_ready_ms)) {
        if (stryMutAct_9fa48("99")) {
          {}
        } else {
          stryCov_9fa48("99");
          this.state = new StateReady();
          this.dwell_accumulator_ms = 0;
          this.ready_bucket_ms = 0;
        }
      }
    }
  }
  private handleIdleCoast() {
    if (stryMutAct_9fa48("100")) {
      {}
    } else {
      stryCov_9fa48("100");
      // Snaplock on regain
      if (stryMutAct_9fa48("104") ? this.current_confidence < this.conf_high : stryMutAct_9fa48("103") ? this.current_confidence > this.conf_high : stryMutAct_9fa48("102") ? false : stryMutAct_9fa48("101") ? true : (stryCov_9fa48("101", "102", "103", "104"), this.current_confidence >= this.conf_high)) {
        if (stryMutAct_9fa48("105")) {
          {}
        } else {
          stryCov_9fa48("105");
          this.state = new StateIdle();
        }
      }
    }
  }
  private handleReady(gesture: string, deltaMs: number) {
    if (stryMutAct_9fa48("106")) {
      {}
    } else {
      stryCov_9fa48("106");
      // Schmitt Trigger: Drop to COAST
      if (stryMutAct_9fa48("110") ? this.current_confidence >= this.conf_low : stryMutAct_9fa48("109") ? this.current_confidence <= this.conf_low : stryMutAct_9fa48("108") ? false : stryMutAct_9fa48("107") ? true : (stryCov_9fa48("107", "108", "109", "110"), this.current_confidence < this.conf_low)) {
        if (stryMutAct_9fa48("111")) {
          {}
        } else {
          stryCov_9fa48("111");
          this.state = new StateReadyCoast();
          return;
        }
      }

      // Return to IDLE (deny by default)
      if (stryMutAct_9fa48("114") ? gesture === 'closed_fist' || this.current_confidence >= this.conf_high : stryMutAct_9fa48("113") ? false : stryMutAct_9fa48("112") ? true : (stryCov_9fa48("112", "113", "114"), (stryMutAct_9fa48("116") ? gesture !== 'closed_fist' : stryMutAct_9fa48("115") ? true : (stryCov_9fa48("115", "116"), gesture === (stryMutAct_9fa48("117") ? "" : (stryCov_9fa48("117"), 'closed_fist')))) && (stryMutAct_9fa48("120") ? this.current_confidence < this.conf_high : stryMutAct_9fa48("119") ? this.current_confidence > this.conf_high : stryMutAct_9fa48("118") ? true : (stryCov_9fa48("118", "119", "120"), this.current_confidence >= this.conf_high)))) {
        if (stryMutAct_9fa48("121")) {
          {}
        } else {
          stryCov_9fa48("121");
          this.state = new StateIdle();
          this.dwell_accumulator_ms = 0;
          return;
        }
      }

      // Leaky Bucket for COMMIT (ms-based, 2:1 leak ratio)
      if (stryMutAct_9fa48("124") ? gesture === 'pointer_up' || this.current_confidence >= this.conf_high : stryMutAct_9fa48("123") ? false : stryMutAct_9fa48("122") ? true : (stryCov_9fa48("122", "123", "124"), (stryMutAct_9fa48("126") ? gesture !== 'pointer_up' : stryMutAct_9fa48("125") ? true : (stryCov_9fa48("125", "126"), gesture === (stryMutAct_9fa48("127") ? "" : (stryCov_9fa48("127"), 'pointer_up')))) && (stryMutAct_9fa48("130") ? this.current_confidence < this.conf_high : stryMutAct_9fa48("129") ? this.current_confidence > this.conf_high : stryMutAct_9fa48("128") ? true : (stryCov_9fa48("128", "129", "130"), this.current_confidence >= this.conf_high)))) {
        if (stryMutAct_9fa48("131")) {
          {}
        } else {
          stryCov_9fa48("131");
          stryMutAct_9fa48("132") ? this.dwell_accumulator_ms -= deltaMs : (stryCov_9fa48("132"), this.dwell_accumulator_ms += deltaMs);
        }
      } else if (stryMutAct_9fa48("135") ? this.current_confidence >= this.conf_low || this.current_confidence < this.conf_high : stryMutAct_9fa48("134") ? false : stryMutAct_9fa48("133") ? true : (stryCov_9fa48("133", "134", "135"), (stryMutAct_9fa48("138") ? this.current_confidence < this.conf_low : stryMutAct_9fa48("137") ? this.current_confidence > this.conf_low : stryMutAct_9fa48("136") ? true : (stryCov_9fa48("136", "137", "138"), this.current_confidence >= this.conf_low)) && (stryMutAct_9fa48("141") ? this.current_confidence >= this.conf_high : stryMutAct_9fa48("140") ? this.current_confidence <= this.conf_high : stryMutAct_9fa48("139") ? true : (stryCov_9fa48("139", "140", "141"), this.current_confidence < this.conf_high)))) {
        if (stryMutAct_9fa48("142")) {
          {}
        } else {
          stryCov_9fa48("142");
          this.dwell_accumulator_ms = stryMutAct_9fa48("143") ? Math.min(0, this.dwell_accumulator_ms - 2 * deltaMs) : (stryCov_9fa48("143"), Math.max(0, stryMutAct_9fa48("144") ? this.dwell_accumulator_ms + 2 * deltaMs : (stryCov_9fa48("144"), this.dwell_accumulator_ms - (stryMutAct_9fa48("145") ? 2 / deltaMs : (stryCov_9fa48("145"), 2 * deltaMs)))));
        }
      } else if (stryMutAct_9fa48("148") ? gesture !== 'pointer_up' || gesture !== 'closed_fist' : stryMutAct_9fa48("147") ? false : stryMutAct_9fa48("146") ? true : (stryCov_9fa48("146", "147", "148"), (stryMutAct_9fa48("150") ? gesture === 'pointer_up' : stryMutAct_9fa48("149") ? true : (stryCov_9fa48("149", "150"), gesture !== (stryMutAct_9fa48("151") ? "" : (stryCov_9fa48("151"), 'pointer_up')))) && (stryMutAct_9fa48("153") ? gesture === 'closed_fist' : stryMutAct_9fa48("152") ? true : (stryCov_9fa48("152", "153"), gesture !== (stryMutAct_9fa48("154") ? "" : (stryCov_9fa48("154"), 'closed_fist')))))) {
        if (stryMutAct_9fa48("155")) {
          {}
        } else {
          stryCov_9fa48("155");
          this.dwell_accumulator_ms = stryMutAct_9fa48("156") ? Math.min(0, this.dwell_accumulator_ms - 2 * deltaMs) : (stryCov_9fa48("156"), Math.max(0, stryMutAct_9fa48("157") ? this.dwell_accumulator_ms + 2 * deltaMs : (stryCov_9fa48("157"), this.dwell_accumulator_ms - (stryMutAct_9fa48("158") ? 2 / deltaMs : (stryCov_9fa48("158"), 2 * deltaMs)))));
        }
      }

      // Transition to COMMIT
      if (stryMutAct_9fa48("162") ? this.dwell_accumulator_ms < this.dwell_limit_commit_ms : stryMutAct_9fa48("161") ? this.dwell_accumulator_ms > this.dwell_limit_commit_ms : stryMutAct_9fa48("160") ? false : stryMutAct_9fa48("159") ? true : (stryCov_9fa48("159", "160", "161", "162"), this.dwell_accumulator_ms >= this.dwell_limit_commit_ms)) {
        if (stryMutAct_9fa48("163")) {
          {}
        } else {
          stryCov_9fa48("163");
          this.state = new StateCommit();
          this.dwell_accumulator_ms = 0;
        }
      }
    }
  }
  private handleReadyCoast() {
    if (stryMutAct_9fa48("164")) {
      {}
    } else {
      stryCov_9fa48("164");
      // Snaplock on regain
      if (stryMutAct_9fa48("168") ? this.current_confidence < this.conf_high : stryMutAct_9fa48("167") ? this.current_confidence > this.conf_high : stryMutAct_9fa48("166") ? false : stryMutAct_9fa48("165") ? true : (stryCov_9fa48("165", "166", "167", "168"), this.current_confidence >= this.conf_high)) {
        if (stryMutAct_9fa48("169")) {
          {}
        } else {
          stryCov_9fa48("169");
          this.state = new StateReady();
        }
      }
    }
  }
  private handleCommitPointer(gesture: string, deltaMs: number) {
    if (stryMutAct_9fa48("170")) {
      {}
    } else {
      stryCov_9fa48("170");
      // Schmitt Trigger: Drop to COAST
      if (stryMutAct_9fa48("174") ? this.current_confidence >= this.conf_low : stryMutAct_9fa48("173") ? this.current_confidence <= this.conf_low : stryMutAct_9fa48("172") ? false : stryMutAct_9fa48("171") ? true : (stryCov_9fa48("171", "172", "173", "174"), this.current_confidence < this.conf_low)) {
        if (stryMutAct_9fa48("175")) {
          {}
        } else {
          stryCov_9fa48("175");
          this.state = new StateCommitCoast();
          return;
        }
      }

      // Leaky Bucket for RELEASE (ms-based, 2:1 leak ratio)
      if (stryMutAct_9fa48("178") ? gesture === 'open_palm' || gesture === 'closed_fist' || this.current_confidence >= this.conf_high : stryMutAct_9fa48("177") ? false : stryMutAct_9fa48("176") ? true : (stryCov_9fa48("176", "177", "178"), (stryMutAct_9fa48("180") ? gesture === 'open_palm' && gesture === 'closed_fist' : stryMutAct_9fa48("179") ? true : (stryCov_9fa48("179", "180"), (stryMutAct_9fa48("182") ? gesture !== 'open_palm' : stryMutAct_9fa48("181") ? false : (stryCov_9fa48("181", "182"), gesture === (stryMutAct_9fa48("183") ? "" : (stryCov_9fa48("183"), 'open_palm')))) || (stryMutAct_9fa48("185") ? gesture !== 'closed_fist' : stryMutAct_9fa48("184") ? false : (stryCov_9fa48("184", "185"), gesture === (stryMutAct_9fa48("186") ? "" : (stryCov_9fa48("186"), 'closed_fist')))))) && (stryMutAct_9fa48("189") ? this.current_confidence < this.conf_high : stryMutAct_9fa48("188") ? this.current_confidence > this.conf_high : stryMutAct_9fa48("187") ? true : (stryCov_9fa48("187", "188", "189"), this.current_confidence >= this.conf_high)))) {
        if (stryMutAct_9fa48("190")) {
          {}
        } else {
          stryCov_9fa48("190");
          stryMutAct_9fa48("191") ? this.dwell_accumulator_ms -= deltaMs : (stryCov_9fa48("191"), this.dwell_accumulator_ms += deltaMs);
          if (stryMutAct_9fa48("194") ? gesture !== 'open_palm' : stryMutAct_9fa48("193") ? false : stryMutAct_9fa48("192") ? true : (stryCov_9fa48("192", "193", "194"), gesture === (stryMutAct_9fa48("195") ? "" : (stryCov_9fa48("195"), 'open_palm')))) {
            if (stryMutAct_9fa48("196")) {
              {}
            } else {
              stryCov_9fa48("196");
              stryMutAct_9fa48("197") ? this.ready_bucket_ms -= deltaMs : (stryCov_9fa48("197"), this.ready_bucket_ms += deltaMs);
              this.idle_bucket_ms = 0;
            }
          } else {
            if (stryMutAct_9fa48("198")) {
              {}
            } else {
              stryCov_9fa48("198");
              stryMutAct_9fa48("199") ? this.idle_bucket_ms -= deltaMs : (stryCov_9fa48("199"), this.idle_bucket_ms += deltaMs);
              this.ready_bucket_ms = 0;
            }
          }
        }
      } else if (stryMutAct_9fa48("202") ? this.current_confidence >= this.conf_low || this.current_confidence < this.conf_high : stryMutAct_9fa48("201") ? false : stryMutAct_9fa48("200") ? true : (stryCov_9fa48("200", "201", "202"), (stryMutAct_9fa48("205") ? this.current_confidence < this.conf_low : stryMutAct_9fa48("204") ? this.current_confidence > this.conf_low : stryMutAct_9fa48("203") ? true : (stryCov_9fa48("203", "204", "205"), this.current_confidence >= this.conf_low)) && (stryMutAct_9fa48("208") ? this.current_confidence >= this.conf_high : stryMutAct_9fa48("207") ? this.current_confidence <= this.conf_high : stryMutAct_9fa48("206") ? true : (stryCov_9fa48("206", "207", "208"), this.current_confidence < this.conf_high)))) {
        if (stryMutAct_9fa48("209")) {
          {}
        } else {
          stryCov_9fa48("209");
          this.dwell_accumulator_ms = stryMutAct_9fa48("210") ? Math.min(0, this.dwell_accumulator_ms - 2 * deltaMs) : (stryCov_9fa48("210"), Math.max(0, stryMutAct_9fa48("211") ? this.dwell_accumulator_ms + 2 * deltaMs : (stryCov_9fa48("211"), this.dwell_accumulator_ms - (stryMutAct_9fa48("212") ? 2 / deltaMs : (stryCov_9fa48("212"), 2 * deltaMs)))));
          this.ready_bucket_ms = stryMutAct_9fa48("213") ? Math.min(0, this.ready_bucket_ms - 2 * deltaMs) : (stryCov_9fa48("213"), Math.max(0, stryMutAct_9fa48("214") ? this.ready_bucket_ms + 2 * deltaMs : (stryCov_9fa48("214"), this.ready_bucket_ms - (stryMutAct_9fa48("215") ? 2 / deltaMs : (stryCov_9fa48("215"), 2 * deltaMs)))));
          this.idle_bucket_ms = stryMutAct_9fa48("216") ? Math.min(0, this.idle_bucket_ms - 2 * deltaMs) : (stryCov_9fa48("216"), Math.max(0, stryMutAct_9fa48("217") ? this.idle_bucket_ms + 2 * deltaMs : (stryCov_9fa48("217"), this.idle_bucket_ms - (stryMutAct_9fa48("218") ? 2 / deltaMs : (stryCov_9fa48("218"), 2 * deltaMs)))));
        }
      } else if (stryMutAct_9fa48("221") ? gesture !== 'open_palm' || gesture !== 'closed_fist' : stryMutAct_9fa48("220") ? false : stryMutAct_9fa48("219") ? true : (stryCov_9fa48("219", "220", "221"), (stryMutAct_9fa48("223") ? gesture === 'open_palm' : stryMutAct_9fa48("222") ? true : (stryCov_9fa48("222", "223"), gesture !== (stryMutAct_9fa48("224") ? "" : (stryCov_9fa48("224"), 'open_palm')))) && (stryMutAct_9fa48("226") ? gesture === 'closed_fist' : stryMutAct_9fa48("225") ? true : (stryCov_9fa48("225", "226"), gesture !== (stryMutAct_9fa48("227") ? "" : (stryCov_9fa48("227"), 'closed_fist')))))) {
        if (stryMutAct_9fa48("228")) {
          {}
        } else {
          stryCov_9fa48("228");
          this.dwell_accumulator_ms = stryMutAct_9fa48("229") ? Math.min(0, this.dwell_accumulator_ms - 2 * deltaMs) : (stryCov_9fa48("229"), Math.max(0, stryMutAct_9fa48("230") ? this.dwell_accumulator_ms + 2 * deltaMs : (stryCov_9fa48("230"), this.dwell_accumulator_ms - (stryMutAct_9fa48("231") ? 2 / deltaMs : (stryCov_9fa48("231"), 2 * deltaMs)))));
          this.ready_bucket_ms = stryMutAct_9fa48("232") ? Math.min(0, this.ready_bucket_ms - 2 * deltaMs) : (stryCov_9fa48("232"), Math.max(0, stryMutAct_9fa48("233") ? this.ready_bucket_ms + 2 * deltaMs : (stryCov_9fa48("233"), this.ready_bucket_ms - (stryMutAct_9fa48("234") ? 2 / deltaMs : (stryCov_9fa48("234"), 2 * deltaMs)))));
          this.idle_bucket_ms = stryMutAct_9fa48("235") ? Math.min(0, this.idle_bucket_ms - 2 * deltaMs) : (stryCov_9fa48("235"), Math.max(0, stryMutAct_9fa48("236") ? this.idle_bucket_ms + 2 * deltaMs : (stryCov_9fa48("236"), this.idle_bucket_ms - (stryMutAct_9fa48("237") ? 2 / deltaMs : (stryCov_9fa48("237"), 2 * deltaMs)))));
        }
      }

      // Transition to READY or IDLE
      if (stryMutAct_9fa48("241") ? this.dwell_accumulator_ms < this.dwell_limit_commit_ms : stryMutAct_9fa48("240") ? this.dwell_accumulator_ms > this.dwell_limit_commit_ms : stryMutAct_9fa48("239") ? false : stryMutAct_9fa48("238") ? true : (stryCov_9fa48("238", "239", "240", "241"), this.dwell_accumulator_ms >= this.dwell_limit_commit_ms)) {
        if (stryMutAct_9fa48("242")) {
          {}
        } else {
          stryCov_9fa48("242");
          if (stryMutAct_9fa48("245") ? gesture !== 'open_palm' : stryMutAct_9fa48("244") ? false : stryMutAct_9fa48("243") ? true : (stryCov_9fa48("243", "244", "245"), gesture === (stryMutAct_9fa48("246") ? "" : (stryCov_9fa48("246"), 'open_palm')))) {
            if (stryMutAct_9fa48("247")) {
              {}
            } else {
              stryCov_9fa48("247");
              this.state = new StateReady();
            }
          } else if (stryMutAct_9fa48("250") ? gesture !== 'closed_fist' : stryMutAct_9fa48("249") ? false : stryMutAct_9fa48("248") ? true : (stryCov_9fa48("248", "249", "250"), gesture === (stryMutAct_9fa48("251") ? "" : (stryCov_9fa48("251"), 'closed_fist')))) {
            if (stryMutAct_9fa48("252")) {
              {}
            } else {
              stryCov_9fa48("252");
              this.state = new StateIdle();
            }
          }
          this.dwell_accumulator_ms = 0;
          this.ready_bucket_ms = 0;
          this.idle_bucket_ms = 0;
        }
      }
    }
  }
  private handleCommitCoast() {
    if (stryMutAct_9fa48("253")) {
      {}
    } else {
      stryCov_9fa48("253");
      // Snaplock on regain
      if (stryMutAct_9fa48("257") ? this.current_confidence < this.conf_high : stryMutAct_9fa48("256") ? this.current_confidence > this.conf_high : stryMutAct_9fa48("255") ? false : stryMutAct_9fa48("254") ? true : (stryCov_9fa48("254", "255", "256", "257"), this.current_confidence >= this.conf_high)) {
        if (stryMutAct_9fa48("258")) {
          {}
        } else {
          stryCov_9fa48("258");
          this.state = new StateCommit();
        }
      }
    }
  }

  /**
   * Returns true if the FSM is in a state that should trigger a W3C pointerdown/move (pinching)
   */
  public isPinching(): boolean {
    if (stryMutAct_9fa48("259")) {
      {}
    } else {
      stryCov_9fa48("259");
      return stryMutAct_9fa48("262") ? this.state.type === 'COMMIT_POINTER' && this.state.type === 'COMMIT_COAST' : stryMutAct_9fa48("261") ? false : stryMutAct_9fa48("260") ? true : (stryCov_9fa48("260", "261", "262"), (stryMutAct_9fa48("264") ? this.state.type !== 'COMMIT_POINTER' : stryMutAct_9fa48("263") ? false : (stryCov_9fa48("263", "264"), this.state.type === (stryMutAct_9fa48("265") ? "" : (stryCov_9fa48("265"), 'COMMIT_POINTER')))) || (stryMutAct_9fa48("267") ? this.state.type !== 'COMMIT_COAST' : stryMutAct_9fa48("266") ? false : (stryCov_9fa48("266", "267"), this.state.type === (stryMutAct_9fa48("268") ? "" : (stryCov_9fa48("268"), 'COMMIT_COAST')))));
    }
  }

  /**
   * Returns true if the FSM is currently in ANY coast state.
   * The caller can combine isPinching() && isCoasting() to detect COMMIT_COAST specifically —
   * the condition that produces ghost-draw teleport strokes on coast recovery (FSM-V5).
   */
  public isCoasting(): boolean {
    if (stryMutAct_9fa48("269")) {
      {}
    } else {
      stryCov_9fa48("269");
      return stryMutAct_9fa48("272") ? (this.state.type === 'IDLE_COAST' || this.state.type === 'READY_COAST') && this.state.type === 'COMMIT_COAST' : stryMutAct_9fa48("271") ? false : stryMutAct_9fa48("270") ? true : (stryCov_9fa48("270", "271", "272"), (stryMutAct_9fa48("274") ? this.state.type === 'IDLE_COAST' && this.state.type === 'READY_COAST' : stryMutAct_9fa48("273") ? false : (stryCov_9fa48("273", "274"), (stryMutAct_9fa48("276") ? this.state.type !== 'IDLE_COAST' : stryMutAct_9fa48("275") ? false : (stryCov_9fa48("275", "276"), this.state.type === (stryMutAct_9fa48("277") ? "" : (stryCov_9fa48("277"), 'IDLE_COAST')))) || (stryMutAct_9fa48("279") ? this.state.type !== 'READY_COAST' : stryMutAct_9fa48("278") ? false : (stryCov_9fa48("278", "279"), this.state.type === (stryMutAct_9fa48("280") ? "" : (stryCov_9fa48("280"), 'READY_COAST')))))) || (stryMutAct_9fa48("282") ? this.state.type !== 'COMMIT_COAST' : stryMutAct_9fa48("281") ? false : (stryCov_9fa48("281", "282"), this.state.type === (stryMutAct_9fa48("283") ? "" : (stryCov_9fa48("283"), 'COMMIT_COAST')))));
    }
  }

  /**
   * Force the FSM into a coasting state (e.g., due to stillness)
   */
  public forceCoast() {
    if (stryMutAct_9fa48("284")) {
      {}
    } else {
      stryCov_9fa48("284");
      if (stryMutAct_9fa48("287") ? this.state.type !== 'IDLE' : stryMutAct_9fa48("286") ? false : stryMutAct_9fa48("285") ? true : (stryCov_9fa48("285", "286", "287"), this.state.type === (stryMutAct_9fa48("288") ? "" : (stryCov_9fa48("288"), 'IDLE')))) this.state = new StateIdleCoast();else if (stryMutAct_9fa48("291") ? this.state.type !== 'READY' : stryMutAct_9fa48("290") ? false : stryMutAct_9fa48("289") ? true : (stryCov_9fa48("289", "290", "291"), this.state.type === (stryMutAct_9fa48("292") ? "" : (stryCov_9fa48("292"), 'READY')))) this.state = new StateReadyCoast();else if (stryMutAct_9fa48("295") ? this.state.type !== 'COMMIT_POINTER' : stryMutAct_9fa48("294") ? false : stryMutAct_9fa48("293") ? true : (stryCov_9fa48("293", "294", "295"), this.state.type === (stryMutAct_9fa48("296") ? "" : (stryCov_9fa48("296"), 'COMMIT_POINTER')))) this.state = new StateCommitCoast();
    }
  }
}