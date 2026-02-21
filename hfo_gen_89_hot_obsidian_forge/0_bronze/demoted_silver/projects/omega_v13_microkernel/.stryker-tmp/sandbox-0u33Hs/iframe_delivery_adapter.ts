/**
 * iframe_delivery_adapter.ts
 * 
 * This adapter runs inside a consumer iframe. It listens for 'SYNTHETIC_POINTER_EVENT'
 * messages sent via postMessage from the host window (e.g., from W3CPointerFabric).
 * 
 * It reconstructs the W3C PointerEvent and dispatches it to the correct DOM element
 * inside the iframe using document.elementFromPoint. This ensures that the consumer
 * application receives standard pointer events that are indistinguishable from a 
 * real touch screen or stylus.
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
export interface IframeDeliveryConfig {
  /**
   * Optional list of allowed origins for security.
   * If empty, accepts from any origin (useful for same-origin or controlled environments).
   */
  allowedOrigins?: string[];

  /**
   * Whether to log debug information.
   */
  debug?: boolean;
}
export class IframeDeliveryAdapter {
  private config: IframeDeliveryConfig;
  private messageListener: (event: MessageEvent) => void;
  constructor(config: IframeDeliveryConfig = {}) {
    if (stryMutAct_9fa48("468")) {
      {}
    } else {
      stryCov_9fa48("468");
      this.config = stryMutAct_9fa48("469") ? {} : (stryCov_9fa48("469"), {
        allowedOrigins: stryMutAct_9fa48("470") ? ["Stryker was here"] : (stryCov_9fa48("470"), []),
        debug: stryMutAct_9fa48("471") ? true : (stryCov_9fa48("471"), false),
        ...config
      });
      this.messageListener = this.handleMessage.bind(this);
    }
  }

  /**
   * Start listening for synthetic pointer events from the host.
   */
  public connect() {
    if (stryMutAct_9fa48("472")) {
      {}
    } else {
      stryCov_9fa48("472");
      window.addEventListener(stryMutAct_9fa48("473") ? "" : (stryCov_9fa48("473"), 'message'), this.messageListener);
      if (stryMutAct_9fa48("475") ? false : stryMutAct_9fa48("474") ? true : (stryCov_9fa48("474", "475"), this.config.debug)) {
        if (stryMutAct_9fa48("476")) {
          {}
        } else {
          stryCov_9fa48("476");
          console.log(stryMutAct_9fa48("477") ? "" : (stryCov_9fa48("477"), '[IframeDeliveryAdapter] Connected and listening for synthetic pointer events.'));
        }
      }
    }
  }

  /**
   * Stop listening for events.
   */
  public disconnect() {
    if (stryMutAct_9fa48("478")) {
      {}
    } else {
      stryCov_9fa48("478");
      window.removeEventListener(stryMutAct_9fa48("479") ? "" : (stryCov_9fa48("479"), 'message'), this.messageListener);
      if (stryMutAct_9fa48("481") ? false : stryMutAct_9fa48("480") ? true : (stryCov_9fa48("480", "481"), this.config.debug)) {
        if (stryMutAct_9fa48("482")) {
          {}
        } else {
          stryCov_9fa48("482");
          console.log(stryMutAct_9fa48("483") ? "" : (stryCov_9fa48("483"), '[IframeDeliveryAdapter] Disconnected.'));
        }
      }
    }
  }
  private handleMessage(event: MessageEvent) {
    if (stryMutAct_9fa48("484")) {
      {}
    } else {
      stryCov_9fa48("484");
      // 1. Security check: Verify origin if allowedOrigins is configured
      if (stryMutAct_9fa48("487") ? this.config.allowedOrigins || this.config.allowedOrigins.length > 0 : stryMutAct_9fa48("486") ? false : stryMutAct_9fa48("485") ? true : (stryCov_9fa48("485", "486", "487"), this.config.allowedOrigins && (stryMutAct_9fa48("490") ? this.config.allowedOrigins.length <= 0 : stryMutAct_9fa48("489") ? this.config.allowedOrigins.length >= 0 : stryMutAct_9fa48("488") ? true : (stryCov_9fa48("488", "489", "490"), this.config.allowedOrigins.length > 0)))) {
        if (stryMutAct_9fa48("491")) {
          {}
        } else {
          stryCov_9fa48("491");
          if (stryMutAct_9fa48("494") ? false : stryMutAct_9fa48("493") ? true : stryMutAct_9fa48("492") ? this.config.allowedOrigins.includes(event.origin) : (stryCov_9fa48("492", "493", "494"), !this.config.allowedOrigins.includes(event.origin))) {
            if (stryMutAct_9fa48("495")) {
              {}
            } else {
              stryCov_9fa48("495");
              if (stryMutAct_9fa48("497") ? false : stryMutAct_9fa48("496") ? true : (stryCov_9fa48("496", "497"), this.config.debug)) {
                if (stryMutAct_9fa48("498")) {
                  {}
                } else {
                  stryCov_9fa48("498");
                  console.warn(stryMutAct_9fa48("499") ? `` : (stryCov_9fa48("499"), `[IframeDeliveryAdapter] Rejected message from unauthorized origin: ${event.origin}`));
                }
              }
              return;
            }
          }
        }
      }

      // 2. Validate message format
      const data = event.data;
      if (stryMutAct_9fa48("502") ? !data && data.type !== 'SYNTHETIC_POINTER_EVENT' : stryMutAct_9fa48("501") ? false : stryMutAct_9fa48("500") ? true : (stryCov_9fa48("500", "501", "502"), (stryMutAct_9fa48("503") ? data : (stryCov_9fa48("503"), !data)) || (stryMutAct_9fa48("505") ? data.type === 'SYNTHETIC_POINTER_EVENT' : stryMutAct_9fa48("504") ? false : (stryCov_9fa48("504", "505"), data.type !== (stryMutAct_9fa48("506") ? "" : (stryCov_9fa48("506"), 'SYNTHETIC_POINTER_EVENT')))))) {
        if (stryMutAct_9fa48("507")) {
          {}
        } else {
          stryCov_9fa48("507");
          return; // Not our message
        }
      }
      const {
        eventType,
        eventInit
      } = data;
      if (stryMutAct_9fa48("510") ? !eventType && !eventInit : stryMutAct_9fa48("509") ? false : stryMutAct_9fa48("508") ? true : (stryCov_9fa48("508", "509", "510"), (stryMutAct_9fa48("511") ? eventType : (stryCov_9fa48("511"), !eventType)) || (stryMutAct_9fa48("512") ? eventInit : (stryCov_9fa48("512"), !eventInit)))) {
        if (stryMutAct_9fa48("513")) {
          {}
        } else {
          stryCov_9fa48("513");
          if (stryMutAct_9fa48("515") ? false : stryMutAct_9fa48("514") ? true : (stryCov_9fa48("514", "515"), this.config.debug)) {
            if (stryMutAct_9fa48("516")) {
              {}
            } else {
              stryCov_9fa48("516");
              console.warn(stryMutAct_9fa48("517") ? "" : (stryCov_9fa48("517"), '[IframeDeliveryAdapter] Malformed SYNTHETIC_POINTER_EVENT payload.'), data);
            }
          }
          return;
        }
      }

      // 3. Find the target element at the given coordinates
      const {
        clientX,
        clientY
      } = eventInit;
      let targetElement = document.elementFromPoint(clientX, clientY);

      // Fallback to body or document element if out of bounds or no specific element found
      if (stryMutAct_9fa48("520") ? false : stryMutAct_9fa48("519") ? true : stryMutAct_9fa48("518") ? targetElement : (stryCov_9fa48("518", "519", "520"), !targetElement)) {
        if (stryMutAct_9fa48("521")) {
          {}
        } else {
          stryCov_9fa48("521");
          targetElement = stryMutAct_9fa48("524") ? document.body && document.documentElement : stryMutAct_9fa48("523") ? false : stryMutAct_9fa48("522") ? true : (stryCov_9fa48("522", "523", "524"), document.body || document.documentElement);
        }
      }
      if (stryMutAct_9fa48("527") ? false : stryMutAct_9fa48("526") ? true : stryMutAct_9fa48("525") ? targetElement : (stryCov_9fa48("525", "526", "527"), !targetElement)) {
        if (stryMutAct_9fa48("528")) {
          {}
        } else {
          stryCov_9fa48("528");
          if (stryMutAct_9fa48("530") ? false : stryMutAct_9fa48("529") ? true : (stryCov_9fa48("529", "530"), this.config.debug)) {
            if (stryMutAct_9fa48("531")) {
              {}
            } else {
              stryCov_9fa48("531");
              console.warn(stryMutAct_9fa48("532") ? "" : (stryCov_9fa48("532"), '[IframeDeliveryAdapter] Could not find a valid target element to dispatch the event.'));
            }
          }
          return;
        }
      }

      // 4. Reconstruct and dispatch the PointerEvent
      try {
        if (stryMutAct_9fa48("533")) {
          {}
        } else {
          stryCov_9fa48("533");
          // Ensure the event bubbles and is composed so it behaves like a real user interaction
          const finalEventInit: PointerEventInit = stryMutAct_9fa48("534") ? {} : (stryCov_9fa48("534"), {
            ...eventInit,
            bubbles: stryMutAct_9fa48("535") ? false : (stryCov_9fa48("535"), true),
            cancelable: stryMutAct_9fa48("536") ? false : (stryCov_9fa48("536"), true),
            composed: stryMutAct_9fa48("537") ? false : (stryCov_9fa48("537"), true),
            // Ensure pointerType is set (usually 'touch' or 'pen' from the host)
            pointerType: stryMutAct_9fa48("540") ? eventInit.pointerType && 'touch' : stryMutAct_9fa48("539") ? false : stryMutAct_9fa48("538") ? true : (stryCov_9fa48("538", "539", "540"), eventInit.pointerType || (stryMutAct_9fa48("541") ? "" : (stryCov_9fa48("541"), 'touch')))
          });
          const syntheticEvent = new PointerEvent(eventType, finalEventInit);

          // Dispatch the event
          targetElement.dispatchEvent(syntheticEvent);
          if (stryMutAct_9fa48("543") ? false : stryMutAct_9fa48("542") ? true : (stryCov_9fa48("542", "543"), this.config.debug)) {
            if (stryMutAct_9fa48("544")) {
              {}
            } else {
              stryCov_9fa48("544");
              console.log(stryMutAct_9fa48("545") ? `` : (stryCov_9fa48("545"), `[IframeDeliveryAdapter] Dispatched ${eventType} to`), targetElement, finalEventInit);
            }
          }
        }
      } catch (error) {
        if (stryMutAct_9fa48("546")) {
          {}
        } else {
          stryCov_9fa48("546");
          if (stryMutAct_9fa48("548") ? false : stryMutAct_9fa48("547") ? true : (stryCov_9fa48("547", "548"), this.config.debug)) {
            if (stryMutAct_9fa48("549")) {
              {}
            } else {
              stryCov_9fa48("549");
              console.error(stryMutAct_9fa48("550") ? "" : (stryCov_9fa48("550"), '[IframeDeliveryAdapter] Failed to dispatch synthetic pointer event:'), error);
            }
          }
        }
      }
    }
  }
}