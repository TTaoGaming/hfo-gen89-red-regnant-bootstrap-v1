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
        this.config = {
            allowedOrigins: [],
            debug: false,
            ...config
        };

        this.messageListener = this.handleMessage.bind(this);
    }

    /**
     * Start listening for synthetic pointer events from the host.
     */
    public connect() {
        window.addEventListener('message', this.messageListener);
        if (this.config.debug) {
            console.log('[IframeDeliveryAdapter] Connected and listening for synthetic pointer events.');
        }
    }

    /**
     * Stop listening for events.
     */
    public disconnect() {
        window.removeEventListener('message', this.messageListener);
        if (this.config.debug) {
            console.log('[IframeDeliveryAdapter] Disconnected.');
        }
    }

    private handleMessage(event: MessageEvent) {
        // 1. Security check: Verify origin if allowedOrigins is configured
        if (this.config.allowedOrigins && this.config.allowedOrigins.length > 0) {
            if (!this.config.allowedOrigins.includes(event.origin)) {
                if (this.config.debug) {
                    console.warn(`[IframeDeliveryAdapter] Rejected message from unauthorized origin: ${event.origin}`);
                }
                return;
            }
        }

        // 2. Validate message format
        const data = event.data;
        if (!data || data.type !== 'SYNTHETIC_POINTER_EVENT') {
            return; // Not our message
        }

        const { eventType, eventInit } = data;
        if (!eventType || !eventInit) {
            if (this.config.debug) {
                console.warn('[IframeDeliveryAdapter] Malformed SYNTHETIC_POINTER_EVENT payload.', data);
            }
            return;
        }

        // 3. Find the target element at the given coordinates
        const { clientX, clientY } = eventInit;
        let targetElement = document.elementFromPoint(clientX, clientY);

        // Fallback to body or document element if out of bounds or no specific element found
        if (!targetElement) {
            targetElement = document.body || document.documentElement;
        }

        if (!targetElement) {
            if (this.config.debug) {
                console.warn('[IframeDeliveryAdapter] Could not find a valid target element to dispatch the event.');
            }
            return;
        }

        // 4. Reconstruct and dispatch the PointerEvent
        try {
            // Ensure the event bubbles and is composed so it behaves like a real user interaction
            const finalEventInit: PointerEventInit = {
                ...eventInit,
                bubbles: true,
                cancelable: true,
                composed: true,
                // Ensure pointerType is set (usually 'touch' or 'pen' from the host)
                pointerType: eventInit.pointerType || 'touch'
            };

            const syntheticEvent = new PointerEvent(eventType, finalEventInit);
            
            // Dispatch the event
            targetElement.dispatchEvent(syntheticEvent);

            if (this.config.debug) {
                console.log(`[IframeDeliveryAdapter] Dispatched ${eventType} to`, targetElement, finalEventInit);
            }
        } catch (error) {
            if (this.config.debug) {
                console.error('[IframeDeliveryAdapter] Failed to dispatch synthetic pointer event:', error);
            }
        }
    }
}
