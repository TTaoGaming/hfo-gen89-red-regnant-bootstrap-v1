/**
 * test_iframe_delivery.ts
 * 
 * Validates the IframeDeliveryAdapter by simulating a postMessage from a host
 * window and ensuring the correct PointerEvent is dispatched to the DOM.
 */

import { IframeDeliveryAdapter } from './iframe_delivery_adapter';

// Mock the DOM environment for testing
const mockElement = {
    tagName: 'DIV',
    id: 'test-target',
    dispatchEvent: (event: any) => {
        console.log(`[DOM] Dispatched ${event.type} to element at ${event.clientX},${event.clientY}`);
        return true;
    }
};

// Mock document.elementFromPoint
(global as any).document = {
    elementFromPoint: (x: number, y: number) => {
        if (x >= 0 && y >= 0) {
            return mockElement;
        }
        return null;
    },
    body: {
        tagName: 'BODY',
        dispatchEvent: (event: any) => {
            console.log(`[DOM] Dispatched ${event.type} to BODY`);
            return true;
        }
    }
};

// Mock window.addEventListener and window.removeEventListener
const listeners: { [key: string]: ((...args: unknown[]) => void)[] } = {};
(global as any).window = {
    addEventListener: (type: string, listener: (...args: unknown[]) => void) => {
        if (!listeners[type]) listeners[type] = [];
        listeners[type].push(listener);
    },
    removeEventListener: (type: string, listener: (...args: unknown[]) => void) => {
        if (listeners[type]) {
            listeners[type] = listeners[type].filter(l => l !== listener);
        }
    }
};

// Mock PointerEvent
class MockPointerEvent {
    type: string;
    clientX: number;
    clientY: number;
    pointerId: number;
    pointerType: string;
    isPrimary: boolean;
    bubbles: boolean;
    cancelable: boolean;
    composed: boolean;
    buttons: number;
    pressure: number;

    constructor(type: string, init: any) {
        this.type = type;
        this.clientX = init.clientX;
        this.clientY = init.clientY;
        this.pointerId = init.pointerId;
        this.pointerType = init.pointerType;
        this.isPrimary = init.isPrimary;
        this.bubbles = init.bubbles;
        this.cancelable = init.cancelable;
        this.composed = init.composed;
        this.buttons = init.buttons;
        this.pressure = init.pressure;
    }
}
(global as any).PointerEvent = MockPointerEvent;

async function runTests() {
    console.log("=== Testing IframeDeliveryAdapter ===");

    const adapter = new IframeDeliveryAdapter({ debug: true });
    adapter.connect();

    console.log("\n--- TEST 1: Valid SYNTHETIC_POINTER_EVENT ---");
    // Simulate a message from the host
    const validMessage = {
        data: {
            type: 'SYNTHETIC_POINTER_EVENT',
            eventType: 'pointerdown',
            eventInit: {
                pointerId: 10000,
                pointerType: 'touch',
                isPrimary: true,
                clientX: 100,
                clientY: 200,
                screenX: 100,
                screenY: 200,
                buttons: 1,
                pressure: 0.5
            }
        },
        origin: 'http://localhost:8080'
    };

    // Trigger the listener
    if (listeners['message']) {
        listeners['message'].forEach(l => l(validMessage));
    }

    console.log("\n--- TEST 2: Invalid Message Type ---");
    const invalidMessage = {
        data: {
            type: 'SOME_OTHER_EVENT',
            payload: 'ignored'
        },
        origin: 'http://localhost:8080'
    };
    if (listeners['message']) {
        listeners['message'].forEach(l => l(invalidMessage));
    }

    console.log("\n--- TEST 3: Out of Bounds (Fallback to Body) ---");
    const outOfBoundsMessage = {
        data: {
            type: 'SYNTHETIC_POINTER_EVENT',
            eventType: 'pointermove',
            eventInit: {
                pointerId: 10000,
                pointerType: 'touch',
                isPrimary: true,
                clientX: -50, // Negative coordinates to trigger fallback
                clientY: -50,
                screenX: -50,
                screenY: -50,
                buttons: 1,
                pressure: 0.5
            }
        },
        origin: 'http://localhost:8080'
    };
    if (listeners['message']) {
        listeners['message'].forEach(l => l(outOfBoundsMessage));
    }

    console.log("\n--- TEST 4: Security Origin Check ---");
    const secureAdapter = new IframeDeliveryAdapter({ 
        allowedOrigins: ['https://trusted.com'],
        debug: true 
    });
    secureAdapter.connect();

    const unauthorizedMessage = {
        data: {
            type: 'SYNTHETIC_POINTER_EVENT',
            eventType: 'pointerup',
            eventInit: {
                pointerId: 10000,
                pointerType: 'touch',
                isPrimary: true,
                clientX: 100,
                clientY: 200,
                buttons: 0,
                pressure: 0
            }
        },
        origin: 'http://evil.com'
    };
    if (listeners['message']) {
        listeners['message'].forEach(l => l(unauthorizedMessage));
    }

    adapter.disconnect();
    secureAdapter.disconnect();
    console.log("\n=== Tests Complete ===");
}

runTests().catch(console.error);
