/**
 * @file config_ui.ts
 * @description Omega v13 Microkernel Plugin: Config Mosaic & Debug UI
 * 
 * GHERKIN SBE SPECS:
 * 
 * Feature: Hot-Swappable Config Mosaic
 * 
 *   Scenario: Load and Update Config
 *     Given a ConfigManager initialized with a default ConfigMosaic JSON
 *     When a new JSON payload is fed in live
 *     Then the ConfigManager updates its state and emits a "config_changed" event
 * 
 *   Scenario: Debug UI Interaction
 *     Given the DebugUI is rendered on top of the application
 *     When the user adjusts a slider (e.g., Schmitt Trigger High)
 *     Then the ConfigManager updates the value and downstream plugins (like the FSM) react immediately
 */

// ============================================================================
// CONFIG MOSAIC (The Data Structure)
// ============================================================================

export interface ConfigMosaic {
    // FSM Tuning (Schmitt Triggers & Leaky Buckets)
    fsm_conf_high: number;
    fsm_conf_low: number;
    /** Milliseconds of qualifying gesture required to leave IDLE → READY. */
    fsm_dwell_ready: number;
    /** Milliseconds of qualifying gesture required to enter / exit COMMIT_POINTER. */
    fsm_dwell_commit: number;
    /** Milliseconds in a COAST state before hard-reset to IDLE. */
    fsm_coast_timeout_ms: number;

    // Physics Tuning (Velocnertia)
    physics_max_velocity: number;
    physics_spring_constant: number;

    // Kalman Smoother
    // MediaPipe Tasks API (tasks-vision) does NOT include built-in landmark smoothing —
    // the old @mediapipe/hands package had LandmarksSmoothingCalculator (1 Euro Filter)
    // but it was removed in the Tasks rewrite for latency reasons. Kalman is our ONLY
    // temporal smoother. Q=process noise, R=measurement noise. GA will evolve these in v14.
    kalman_q: number;
    kalman_r: number;

    // Gesture Tuning
    gesture_pinch_threshold: number;
}

export const DEFAULT_CONFIG: ConfigMosaic = {
    fsm_conf_high: 0.64,
    fsm_conf_low: 0.50,
    // Time-based dwell — framerate-independent (100 ms ≈ 6 frames @ 60 fps)
    fsm_dwell_ready:      100, // ms
    fsm_dwell_commit:     100, // ms
    fsm_coast_timeout_ms: 500, // ms before COAST→IDLE hard reset

    physics_max_velocity: 50.0,
    physics_spring_constant: 15.0,

    // Tuned for 30fps MediaPipe tasks-vision @ 480–720p.
    // Q=0.05: trust the model strongly — landmark noise is real.
    // R=10.0: high measurement noise because raw landmarks jump ~5px/frame.
    // GA (v14) will personalise these per-user via Shadow Tracker fitness signal.
    kalman_q: 0.05,
    kalman_r: 10.0,

    gesture_pinch_threshold: 0.05
};

// ============================================================================
// CONFIG MANAGER (The State Holder)
// ============================================================================

type ConfigChangeListener = (newConfig: ConfigMosaic) => void;

export class ConfigManager {
    private currentConfig: ConfigMosaic;
    private listeners: Set<ConfigChangeListener> = new Set();

    constructor(initialConfig: Partial<ConfigMosaic> = {}) {
        this.currentConfig = { ...DEFAULT_CONFIG, ...initialConfig };
    }

    public get(): ConfigMosaic {
        return { ...this.currentConfig };
    }

    /**
     * Hot-swap the configuration with a new JSON object.
     * Only updates provided keys.
     */
    public update(newValues: Partial<ConfigMosaic>) {
        this.currentConfig = { ...this.currentConfig, ...newValues };
        this.notifyListeners();
    }

    public subscribe(listener: ConfigChangeListener) {
        this.listeners.add(listener);
        // Immediately notify the new listener of the current state
        listener(this.get());
    }

    public unsubscribe(listener: ConfigChangeListener) {
        this.listeners.delete(listener);
    }

    private notifyListeners() {
        const snapshot = this.get();
        for (const listener of this.listeners) {
            listener(snapshot);
        }
    }
}

// ============================================================================
// DEBUG UI (The Canvas/HTML Overlay)
// ============================================================================

/**
 * A simple HTML-based UI overlay to adjust the ConfigMosaic on the fly.
 * We use HTML instead of raw Canvas drawing for accessibility and ease of input handling (sliders).
 */
export class DebugUI {
    private container: HTMLDivElement;
    private configManager: ConfigManager;

    constructor(configManager: ConfigManager) {
        this.configManager = configManager;
        
        // Create the UI container
        this.container = (globalThis as unknown as { document: { createElement: (tag: string) => HTMLDivElement } }).document.createElement("div");
        (this.container as unknown as { style: { position: string, top: string, right: string, backgroundColor: string, color: string, padding: string, fontFamily: string, fontSize: string, borderRadius: string, zIndex: string, width: string } }).style.position = "absolute";
        (this.container as unknown as { style: { position: string, top: string, right: string, backgroundColor: string, color: string, padding: string, fontFamily: string, fontSize: string, borderRadius: string, zIndex: string, width: string } }).style.top = "10px";
        (this.container as unknown as { style: { position: string, top: string, right: string, backgroundColor: string, color: string, padding: string, fontFamily: string, fontSize: string, borderRadius: string, zIndex: string, width: string } }).style.right = "10px";
        (this.container as unknown as { style: { position: string, top: string, right: string, backgroundColor: string, color: string, padding: string, fontFamily: string, fontSize: string, borderRadius: string, zIndex: string, width: string } }).style.backgroundColor = "rgba(0, 0, 0, 0.8)";
        (this.container as unknown as { style: { position: string, top: string, right: string, backgroundColor: string, color: string, padding: string, fontFamily: string, fontSize: string, borderRadius: string, zIndex: string, width: string } }).style.color = "#00ff00";
        (this.container as unknown as { style: { position: string, top: string, right: string, backgroundColor: string, color: string, padding: string, fontFamily: string, fontSize: string, borderRadius: string, zIndex: string, width: string } }).style.padding = "15px";
        (this.container as unknown as { style: { position: string, top: string, right: string, backgroundColor: string, color: string, padding: string, fontFamily: string, fontSize: string, borderRadius: string, zIndex: string, width: string } }).style.fontFamily = "monospace";
        (this.container as unknown as { style: { position: string, top: string, right: string, backgroundColor: string, color: string, padding: string, fontFamily: string, fontSize: string, borderRadius: string, zIndex: string, width: string } }).style.fontSize = "12px";
        (this.container as unknown as { style: { position: string, top: string, right: string, backgroundColor: string, color: string, padding: string, fontFamily: string, fontSize: string, borderRadius: string, zIndex: string, width: string } }).style.borderRadius = "5px";
        (this.container as unknown as { style: { position: string, top: string, right: string, backgroundColor: string, color: string, padding: string, fontFamily: string, fontSize: string, borderRadius: string, zIndex: string, width: string } }).style.zIndex = "9999";
        (this.container as unknown as { style: { position: string, top: string, right: string, backgroundColor: string, color: string, padding: string, fontFamily: string, fontSize: string, borderRadius: string, zIndex: string, width: string } }).style.width = "300px";

        (globalThis as unknown as { document: { body: { appendChild: (el: HTMLDivElement) => void } } }).document.body.appendChild(this.container);

        this.buildUI();

        // Listen for external config changes (e.g., if a JSON file is loaded)
        this.configManager.subscribe((newConfig) => {
            this.updateUIFromConfig(newConfig);
        });
    }

    private buildUI() {
        const title = (globalThis as unknown as { document: { createElement: (tag: string) => HTMLHeadingElement } }).document.createElement("h3");
        (title as unknown as { innerText: string }).innerText = "Omega v13 Config Mosaic";
        (title as unknown as { style: { margin: string, borderBottom: string } }).style.margin = "0 0 10px 0";
        (title as unknown as { style: { margin: string, borderBottom: string } }).style.borderBottom = "1px solid #00ff00";
        (this.container as unknown as { appendChild: (el: unknown) => void }).appendChild(title);

        const config = this.configManager.get();

        // FSM Tuning
        this.createSlider("fsm_conf_high", "Schmitt High", 0, 1, 0.01, config.fsm_conf_high);
        this.createSlider("fsm_conf_low", "Schmitt Low", 0, 1, 0.01, config.fsm_conf_low);
        this.createSlider("fsm_dwell_ready", "Dwell Ready (ticks)", 1, 60, 1, config.fsm_dwell_ready);
        this.createSlider("fsm_dwell_commit", "Dwell Commit (ticks)", 1, 60, 1, config.fsm_dwell_commit);

        // Physics Tuning
        this.createSlider("physics_max_velocity", "Velocnertia Max", 1, 200, 1, config.physics_max_velocity);
        this.createSlider("physics_spring_constant", "Spring Constant", 1, 50, 0.5, config.physics_spring_constant);

        // Gesture Tuning
        this.createSlider("gesture_pinch_threshold", "Pinch Threshold", 0.01, 0.2, 0.01, config.gesture_pinch_threshold);
    }

    private createSlider(key: keyof ConfigMosaic, labelText: string, min: number, max: number, step: number, initialValue: number) {
        const wrapper = (globalThis as unknown as { document: { createElement: (tag: string) => HTMLDivElement } }).document.createElement("div");
        (wrapper as unknown as { style: { marginBottom: string } }).style.marginBottom = "10px";

        const label = (globalThis as unknown as { document: { createElement: (tag: string) => HTMLLabelElement } }).document.createElement("label");
        (label as unknown as { innerText: string }).innerText = `${labelText}: `;
        (label as unknown as { style: { display: string, width: string } }).style.display = "inline-block";
        (label as unknown as { style: { display: string, width: string } }).style.width = "150px";

        const valueDisplay = (globalThis as unknown as { document: { createElement: (tag: string) => HTMLSpanElement } }).document.createElement("span");
        (valueDisplay as unknown as { id: string }).id = `val_${key}`;
        (valueDisplay as unknown as { innerText: string }).innerText = initialValue.toFixed(2);
        (valueDisplay as unknown as { style: { display: string, width: string } }).style.display = "inline-block";
        (valueDisplay as unknown as { style: { display: string, width: string } }).style.width = "40px";

        const slider = (globalThis as unknown as { document: { createElement: (tag: string) => HTMLInputElement } }).document.createElement("input");
        (slider as unknown as { type: string }).type = "range";
        (slider as unknown as { id: string }).id = `slider_${key}`;
        (slider as unknown as { min: string }).min = min.toString();
        (slider as unknown as { max: string }).max = max.toString();
        (slider as unknown as { step: string }).step = step.toString();
        (slider as unknown as { value: string }).value = initialValue.toString();
        (slider as unknown as { style: { width: string } }).style.width = "100%";

        (slider as unknown as { addEventListener: (event: string, cb: (e: unknown) => void) => void }).addEventListener("input", (e) => {
            const val = parseFloat(((e as { target: { value: string } }).target).value);
            (valueDisplay as unknown as { innerText: string }).innerText = val.toFixed(2);
            
            // Hot-swap the config
            this.configManager.update({ [key]: val });
        });

        (wrapper as unknown as { appendChild: (el: unknown) => void }).appendChild(label);
        (wrapper as unknown as { appendChild: (el: unknown) => void }).appendChild(valueDisplay);
        (wrapper as unknown as { appendChild: (el: unknown) => void }).appendChild(slider);
        (this.container as unknown as { appendChild: (el: unknown) => void }).appendChild(wrapper);
    }

    /**
     * Updates the sliders if the config was changed externally (e.g., via JSON load)
     */
    private updateUIFromConfig(config: ConfigMosaic) {
        for (const key in config) {
            const slider = (globalThis as unknown as { document: { getElementById: (id: string) => HTMLInputElement } }).document.getElementById(`slider_${key}`) as HTMLInputElement;
            const display = (globalThis as unknown as { document: { getElementById: (id: string) => HTMLSpanElement } }).document.getElementById(`val_${key}`) as HTMLSpanElement;
            
            if (slider && display) {
                const val = config[key as keyof ConfigMosaic];
                (slider as unknown as { value: string }).value = val.toString();
                (display as unknown as { innerText: string }).innerText = val.toFixed(2);
            }
        }
    }

    public dispose() {
        if ((this.container as unknown as { parentNode: unknown }).parentNode) {
            ((this.container as unknown as { parentNode: { removeChild: (el: unknown) => void } }).parentNode).removeChild(this.container);
        }
    }
}
