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
        this.container = document.createElement("div");
        this.container.style.position = "absolute";
        this.container.style.top = "10px";
        this.container.style.right = "10px";
        this.container.style.backgroundColor = "rgba(0, 0, 0, 0.8)";
        this.container.style.color = "#00ff00";
        this.container.style.padding = "15px";
        this.container.style.fontFamily = "monospace";
        this.container.style.fontSize = "12px";
        this.container.style.borderRadius = "5px";
        this.container.style.zIndex = "9999";
        this.container.style.width = "300px";

        document.body.appendChild(this.container);

        this.buildUI();

        // Listen for external config changes (e.g., if a JSON file is loaded)
        this.configManager.subscribe((newConfig) => {
            this.updateUIFromConfig(newConfig);
        });
    }

    private buildUI() {
        const title = document.createElement("h3");
        title.innerText = "Omega v13 Config Mosaic";
        title.style.margin = "0 0 10px 0";
        title.style.borderBottom = "1px solid #00ff00";
        this.container.appendChild(title);

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
        const wrapper = document.createElement("div");
        wrapper.style.marginBottom = "10px";

        const label = document.createElement("label");
        label.innerText = `${labelText}: `;
        label.style.display = "inline-block";
        label.style.width = "150px";

        const valueDisplay = document.createElement("span");
        valueDisplay.id = `val_${key}`;
        valueDisplay.innerText = initialValue.toFixed(2);
        valueDisplay.style.display = "inline-block";
        valueDisplay.style.width = "40px";

        const slider = document.createElement("input");
        slider.type = "range";
        slider.id = `slider_${key}`;
        slider.min = min.toString();
        slider.max = max.toString();
        slider.step = step.toString();
        slider.value = initialValue.toString();
        slider.style.width = "100%";

        slider.addEventListener("input", (e) => {
            const val = parseFloat((e.target as HTMLInputElement).value);
            valueDisplay.innerText = val.toFixed(2);
            
            // Hot-swap the config
            this.configManager.update({ [key]: val });
        });

        wrapper.appendChild(label);
        wrapper.appendChild(valueDisplay);
        wrapper.appendChild(slider);
        this.container.appendChild(wrapper);
    }

    /**
     * Updates the sliders if the config was changed externally (e.g., via JSON load)
     */
    private updateUIFromConfig(config: ConfigMosaic) {
        for (const key in config) {
            const slider = document.getElementById(`slider_${key}`) as HTMLInputElement;
            const display = document.getElementById(`val_${key}`) as HTMLSpanElement;
            
            if (slider && display) {
                const val = config[key as keyof ConfigMosaic];
                slider.value = val.toString();
                display.innerText = val.toFixed(2);
            }
        }
    }

    public dispose() {
        if (this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
    }
}
