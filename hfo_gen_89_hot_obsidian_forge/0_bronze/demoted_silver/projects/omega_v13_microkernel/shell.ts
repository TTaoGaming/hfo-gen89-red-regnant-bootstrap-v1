/**
 * @file shell.ts
 * @description Omega v13 — Persistent UI Shell
 *
 * Contains ALL non-canvas chrome. Zero coupling to MediaPipe or Babylon.
 * Every element lives at z=30 (SETTINGS layer). The canvas/video layers
 * below are untouched; only children that need clicks have pointer-events:auto.
 *
 * COMPONENTS (mission_state thread_keys → omega.v13.ui.*)
 * ─────────────────────────────────────────────────────────
 *   coach_bar      — top strip: CAMERA→READY→CLICK→RELEASE state machine
 *   cta_hero       — center onboarding gate, orange START CAMERA pill
 *   bottom_banner  — viral watermark bar + Ko-fi + Remove Banner CTA
 *   floating_gear  — ⚙ button bottom-right, opens Config/Layer panel
 *   right_rail     — lock + hand-mode quick toggles
 *
 * EVENT BUS CONTRACTS
 *   Listens: STATE_CHANGE, FRAME_PROCESSED, LAYER_OPACITY_CHANGE
 *   Emits:   (user-click) → AUDIO_UNLOCK, CAMERA_START_REQUESTED, SETTINGS_TOGGLE
 */

import { EventBus } from './event_bus';
import type { MicrokernelEvents, EventCallback } from './event_bus';
import { LayerManager, LAYER } from './layer_manager';
import { ConfigManager, DebugUI } from './config_ui';

// ─── Types ───────────────────────────────────────────────────────────────────

// FSM states emitted by the event bus (decoupled — no import from gesture_fsm.ts)
export type FsmState =
    | 'IDLE' | 'IDLE_COAST'
    | 'READY' | 'READY_COAST'
    | 'COMMIT_POINTER' | 'COMMIT_COAST'
    | '__CAMERA_OFF__';   // sentinel before camera starts

// Coach bar logical step (0-3)
export type CoachStep = 0 | 1 | 2 | 3;

// Map every FSM edge → coach step
const FSM_TO_STEP: Record<FsmState, CoachStep> = {
    '__CAMERA_OFF__':  0,
    'IDLE':            1,
    'IDLE_COAST':      1,
    'READY':           2,
    'READY_COAST':     2,
    'COMMIT_POINTER':  3,
    'COMMIT_COAST':    3,
};

// Which FSM states are "coasting" (tracking briefly lost)
const COAST_STATES = new Set<FsmState>(['IDLE_COAST', 'READY_COAST', 'COMMIT_COAST']);

export interface ShellCallbacks {
    /** Called when the user taps START CAMERA (trusted gesture) */
    onCameraStart: () => Promise<void>;
    /** ConfigManager instance so the settings panel can bind sliders */
    configManager: ConfigManager;
    // Scenario: Given ShellCallbacks includes eventBus and layerManager
    //           When Shell.mount() is called
    //           Then Shell subscribes on the injected bus (ATDD-ARCH-001)
    eventBus: EventBus;
    layerManager: LayerManager;
}

// ─── Tokens / Colours ────────────────────────────────────────────────────────

const T = {
    bg:         'rgba(15, 17, 35, 0.92)',
    bgPanel:    'rgba(20, 22, 45, 0.97)',
    border:     'rgba(101, 106, 160, 0.4)',
    accent:     '#7b8bff',
    accentOff:  'rgba(123,139,255,0.3)',
    orange:     '#ff7a00',
    orangeHot:  '#ff9a30',
    text:       '#e2e4f0',
    textDim:    'rgba(180,184,210,0.6)',
    stepActive: 'rgba(123,139,255,0.18)',
    stepDone:   'rgba(80,200,120,0.18)',
    success:    '#50c878',
    danger:     '#ff5566',
    font:       "'Inter', 'Segoe UI', system-ui, sans-serif",
    mono:       "'JetBrains Mono', 'Consolas', monospace",
};

// ─── CSS injection (once) ────────────────────────────────────────────────────

function injectStyles() {
    if (document.getElementById('omega-shell-styles')) return;
    const style = document.createElement('style');
    style.id = 'omega-shell-styles';
    style.textContent = `
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

#omega-shell * { box-sizing: border-box; font-family: ${T.font}; }

/* ── Coach bar ── */
#omega-coach-bar {
    position: absolute; top: 0; left: 0; right: 0;
    background: ${T.bg};
    border-bottom: 1px solid ${T.border};
    padding: 6px 56px 6px 16px; /* right pad for skip btn */
    pointer-events: auto; user-select: none;
    display: flex; flex-direction: column;
    align-items: stretch; gap: 4px;
}
.omega-coach-title {
    text-align: center;
    font-size: 11px; font-weight: 700; letter-spacing: 0.18em;
    text-transform: uppercase; color: ${T.accent};
    line-height: 1.2; padding: 2px 0;
}
.omega-coach-subtitle {
    text-align: center;
    font-size: 9px; color: ${T.textDim}; letter-spacing: 0.03em;
    line-height: 1.4; padding-bottom: 2px;
}
#omega-coach-track {
    flex: 1; display: grid;
    grid-template-columns: 1fr auto 1fr auto 1fr auto 1fr;
    align-items: center;
    gap: 0; min-width: 0;
}
/* responsive: single row pill strip below ~720px */
@media (max-width: 720px) {
    #omega-coach-track { grid-template-columns: repeat(4, 1fr); gap: 4px; }
    .omega-step-arrow { display: none; }
    #omega-coach-bar { padding-right: 48px; }
}
.omega-step {
    display: flex; flex-direction: row; align-items: center; gap: 8px;
    padding: 7px 10px; border-radius: 8px;
    border: 1px solid rgba(101,106,160,0.2);
    background: rgba(255,255,255,0.03);
    transition: background 0.2s, border-color 0.2s, box-shadow 0.2s;
    cursor: default; overflow: hidden; min-width: 0;
}
@media (max-width: 720px) {
    .omega-step { flex-direction: column; gap: 3px; padding: 5px 6px; }
    .omega-step .step-text { display: none; }
}
.omega-step .step-badge {
    flex-shrink: 0;
    width: 28px; height: 28px; border-radius: 8px;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(101,106,160,0.25);
    font-size: 14px; line-height: 1;
    transition: background 0.2s, border-color 0.2s;
    position: relative;
}
.omega-step .step-badge .step-num-badge {
    position: absolute; top: -4px; right: -4px;
    width: 13px; height: 13px; border-radius: 50%;
    background: rgba(101,106,160,0.5);
    font-size: 8px; font-weight: 700; color: #fff;
    display: flex; align-items: center; justify-content: center;
    border: 1px solid rgba(15,17,35,0.8);
}
.omega-step .step-text { flex: 1; min-width: 0; }
.omega-step .step-label {
    font-size: 10px; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: ${T.textDim};
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    display: block;
}
.omega-step .step-fsm {
    font-size: 9px; color: rgba(101,106,160,0.5);
    font-family: ${T.mono}; letter-spacing: 0.04em;
    white-space: nowrap; display: block; margin-top: 1px;
}
.omega-step .step-desc {
    font-size: 9px; color: ${T.textDim}; margin-top: 2px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    display: block;
}
/* ── idle: dimmed card ── */
.omega-step.idle .step-badge { background: rgba(255,255,255,0.04); border-color: rgba(101,106,160,0.15); }
/* ── active: accent glow ── */
.omega-step.active {
    background: rgba(123,139,255,0.1);
    border-color: ${T.accent};
    box-shadow: 0 0 0 1px rgba(123,139,255,0.2) inset;
}
.omega-step.active .step-badge {
    background: ${T.accent}; border-color: ${T.accent};
}
.omega-step.active .step-badge .step-num-badge { background: rgba(15,17,35,0.7); }
.omega-step.active .step-label { color: ${T.text}; }
.omega-step.active .step-fsm { color: rgba(123,139,255,0.7); }
/* ── coast: pulsing warning ── */
.omega-step.coast {
    background: rgba(255,180,0,0.07);
    border-color: rgba(255,180,0,0.35);
    animation: omegaCoastPulse 0.9s ease-in-out infinite;
}
.omega-step.coast .step-badge { background: rgba(255,180,0,0.25); border-color: rgba(255,180,0,0.5); }
.omega-step.coast .step-label { color: #ffca44; }
.omega-step.coast .step-fsm { color: rgba(255,180,0,0.55); }
@keyframes omegaCoastPulse {
    0%,100% { box-shadow: none; }
    50% { box-shadow: 0 0 10px rgba(255,180,0,0.3); }
}
/* ── done: success ── */
.omega-step.done {
    background: rgba(80,200,120,0.07);
    border-color: rgba(80,200,120,0.3);
    opacity: 0.75;
}
.omega-step.done .step-badge { background: ${T.success}; border-color: ${T.success}; }
.omega-step.done .step-label { color: ${T.success}; }
.omega-step.done .step-fsm { color: rgba(80,200,120,0.5); }
/* ── connector arrows ── */
.omega-step-arrow {
    text-align: center; color: rgba(101,106,160,0.3);
    font-size: 13px; padding: 0 2px; flex-shrink: 0;
}
.omega-step.active ~ .omega-step-arrow,
.omega-step.coast ~ .omega-step-arrow { color: rgba(101,106,160,0.15); }
/* ── skip btn ── */
#omega-skip-btn {
    position: absolute; top: 50%; right: 10px;
    transform: translateY(-50%);
    padding: 4px 10px; border-radius: 6px;
    background: rgba(255,255,255,0.06); border: 1px solid ${T.border};
    color: ${T.textDim}; font-size: 10px; font-weight: 600;
    cursor: pointer; transition: all 0.15s; pointer-events: auto;
    white-space: nowrap;
}
#omega-skip-btn:hover { background: rgba(255,255,255,0.12); color: ${T.text}; }

/* ── CTA Hero ── */
#omega-cta-overlay {
    position: absolute; inset: 0;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    gap: 20px;
    pointer-events: none;
}
#omega-cta-btn {
    pointer-events: auto;
    padding: 18px 64px; border-radius: 50px;
    background: linear-gradient(135deg, ${T.orange}, ${T.orangeHot});
    border: none; color: #fff;
    font-size: 20px; font-weight: 800; letter-spacing: 0.08em;
    text-transform: uppercase; cursor: pointer;
    box-shadow: 0 0 40px rgba(255,122,0,0.5), 0 8px 24px rgba(0,0,0,0.4);
    transition: transform 0.15s, box-shadow 0.15s;
    animation: omegaPulse 2.5s ease-in-out infinite;
}
#omega-cta-btn:hover {
    transform: scale(1.04);
    box-shadow: 0 0 60px rgba(255,122,0,0.7), 0 12px 32px rgba(0,0,0,0.4);
}
#omega-cta-btn:active { transform: scale(0.98); }
#omega-cta-btn:disabled {
    opacity: 0.6; cursor: not-allowed; animation: none; transform: none;
}
@keyframes omegaPulse {
    0%, 100% { box-shadow: 0 0 40px rgba(255,122,0,0.5), 0 8px 24px rgba(0,0,0,0.4); }
    50%       { box-shadow: 0 0 70px rgba(255,122,0,0.75), 0 8px 24px rgba(0,0,0,0.4); }
}
#omega-hero-card {
    pointer-events: auto;
    background: rgba(15,17,35,0.88);
    border: 1px solid ${T.border};
    border-radius: 16px;
    padding: 24px 36px; max-width: 560px; text-align: center;
    backdrop-filter: blur(16px);
}
#omega-hero-card h2 {
    margin: 0 0 10px; font-size: 20px; font-weight: 700; color: ${T.text};
}
#omega-hero-card p {
    margin: 0 0 10px; font-size: 14px; color: ${T.textDim}; line-height: 1.6;
}
#omega-hero-card .tagline {
    font-size: 12px; color: ${T.accentOff}; font-style: italic;
}
#omega-hero-card .tagline::before { content: '🖥  '; }

/* ── Bottom banner ── */
#omega-bottom-banner {
    position: absolute; bottom: 0; left: 0; right: 0;
    height: 40px;
    background: rgba(10,11,25,0.95);
    border-top: 1px solid ${T.border};
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 14px;
    pointer-events: auto;
}
.omega-banner-brand {
    font-size: 11px; font-weight: 600; letter-spacing: 0.12em;
    color: ${T.textDim}; text-transform: uppercase; display: flex; gap: 8px;
    align-items: center;
}
.omega-banner-brand span.free-pill {
    background: rgba(123,139,255,0.2); border: 1px solid ${T.accentOff};
    border-radius: 4px; padding: 1px 6px;
    font-size: 10px; color: ${T.accent}; letter-spacing: 0.08em;
}
.omega-banner-actions { display: flex; gap: 8px; align-items: center; }
.omega-banner-btn {
    padding: 4px 12px; border-radius: 6px; font-size: 11px; font-weight: 600;
    cursor: pointer; text-decoration: none; border: none;
    display: inline-flex; align-items: center; gap: 5px;
    transition: all 0.15s;
}
.omega-banner-btn.kofi {
    background: rgba(255,94,105,0.15); border: 1px solid rgba(255,94,105,0.35);
    color: #ff8a94;
}
.omega-banner-btn.kofi:hover { background: rgba(255,94,105,0.28); }
.omega-banner-btn.support {
    background: linear-gradient(135deg, ${T.orange}, ${T.orangeHot});
    color: #fff; box-shadow: 0 0 16px rgba(255,122,0,0.35);
    border: none;
}
.omega-banner-btn.support:hover { transform: scale(1.04); }
.omega-banner-btn.consult {
    background: rgba(123,139,255,0.12); border: 1px solid ${T.accentOff};
    color: ${T.accent};
}
.omega-banner-btn.consult:hover { background: rgba(123,139,255,0.22); }

/* ── Floating gear ── */
#omega-gear-btn {
    position: absolute; bottom: 50px; right: 14px;
    width: 44px; height: 44px; border-radius: 50%;
    background: rgba(15,17,35,0.9);
    border: 1px solid ${T.border};
    color: ${T.textDim}; font-size: 20px; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.2s; pointer-events: auto;
    box-shadow: 0 4px 16px rgba(0,0,0,0.4);
}
#omega-gear-btn:hover { color: ${T.text}; border-color: ${T.accent}; transform: rotate(30deg); }
#omega-gear-btn.open { color: ${T.accent}; border-color: ${T.accent}; transform: rotate(90deg); }

/* ── Settings drawer ── */
#omega-settings-drawer {
    position: absolute; top: 0; right: 0; bottom: 40px; width: 320px;
    background: ${T.bgPanel};
    border-left: 1px solid ${T.border};
    overflow-y: auto; padding: 14px;
    pointer-events: auto;
    transform: translateX(100%);
    transition: transform 0.25s ease;
    z-index: 1;
}
#omega-settings-drawer.open { transform: translateX(0); }
#omega-settings-drawer h3 {
    margin: 0 0 12px; font-size: 12px; font-weight: 700;
    color: ${T.accent}; letter-spacing: 0.12em; text-transform: uppercase;
    border-bottom: 1px solid ${T.border}; padding-bottom: 8px;
}
.omega-slider-row {
    display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
}
.omega-slider-row label {
    width: 118px; font-size: 11px; color: ${T.textDim}; flex-shrink: 0;
}
.omega-slider-row input[type=range] { flex: 1; accent-color: ${T.accent}; }
.omega-slider-row .val {
    width: 34px; font-size: 11px; color: ${T.textDim};
    font-family: ${T.mono}; text-align: right;
}
.omega-section-title {
    font-size: 10px; font-weight: 700; color: ${T.textDim};
    letter-spacing: 0.1em; text-transform: uppercase;
    margin: 12px 0 6px; display: flex; align-items: center; gap: 6px;
}
.omega-section-title::after {
    content: ''; flex: 1; height: 1px; background: ${T.border};
}
    `;
    document.head.appendChild(style);
}

// ─── Shell ───────────────────────────────────────────────────────────────────

export class Shell {
    private root!: HTMLElement;
    private coachBar!: HTMLElement;
    private ctaOverlay!: HTMLElement;
    private ctaBtn!: HTMLButtonElement;
    private settingsDrawer!: HTMLElement;
    private gearBtn!: HTMLButtonElement;
    private currentStep: CoachStep = 0;
    private currentFsmState: FsmState = '__CAMERA_OFF__';
    private coachVisible = true;
    private settingsOpen = false;
    private callbacks: ShellCallbacks;
    private eventBus: EventBus;
    private layerManager: LayerManager;

    /** Stable bound refs — ARCH-ZOMBIE guard: bound once in constructor.
     *  Typed explicitly against MicrokernelEvents so the typed EventBus accepts
     *  them without unsafe casts (ARCH-TYPED-EVENTS enforcement). */
    private readonly boundOnStateChange:    EventCallback<MicrokernelEvents['STATE_CHANGE']>;
    private readonly boundOnFrameProcessed: EventCallback<MicrokernelEvents['FRAME_PROCESSED']>;
    private readonly boundOnSettingsToggle: EventCallback<MicrokernelEvents['SETTINGS_TOGGLE']>;

    constructor(callbacks: ShellCallbacks) {
        this.callbacks    = callbacks;
        this.eventBus     = callbacks.eventBus;
        this.layerManager = callbacks.layerManager;

        this.boundOnStateChange    = this.onStateChange.bind(this);
        this.boundOnFrameProcessed = this.onFrameProcessed.bind(this);
        this.boundOnSettingsToggle = this.toggleSettings.bind(this);
    }

    mount(): void {
        injectStyles();

        // Root: fills the SETTINGS layer div (pointer-events:none by default)
        this.root = document.createElement('div');
        this.root.id = 'omega-shell';
        Object.assign(this.root.style, {
            position: 'absolute', inset: '0',
            pointerEvents: 'none', // children opt in
            overflow: 'hidden',
        });

        this.buildCoachBar();
        this.buildCtaOverlay();
        this.buildGearButton();
        this.buildSettingsDrawer();
        this.buildBottomBanner();

        // Attach to the SETTINGS layer
        const settingsLayer = document.getElementById('omega-settings');
        if (settingsLayer) {
            settingsLayer.appendChild(this.root);
        } else {
            document.body.appendChild(this.root);
        }

        // Wire event bus — injected, never global (ATDD-ARCH-001)
        // ARCH-ZOMBIE guard: use pre-bound refs from constructor — NOT inline .bind(this) here
        this.eventBus.subscribe('STATE_CHANGE',    this.boundOnStateChange);
        this.eventBus.subscribe('FRAME_PROCESSED', this.boundOnFrameProcessed);
        this.eventBus.subscribe('SETTINGS_TOGGLE', this.boundOnSettingsToggle);

        // Keyboard shortcut: backtick/F1 toggles settings
        document.addEventListener('keydown', (e) => {
            if (e.key === '`' || e.key === 'F1') this.toggleSettings();
        });
    }

    // ── Coach Bar ────────────────────────────────────────────────────────────

    private buildCoachBar(): void {
        this.coachBar = document.createElement('div');
        this.coachBar.id = 'omega-coach-bar';

        const title = document.createElement('div');
        title.className = 'omega-coach-title';
        title.textContent = 'HFO × EXCALIDRAW GEN8 V13';
        this.coachBar.appendChild(title);

        const track = document.createElement('div');
        track.id = 'omega-coach-track';

        // Step definitions — each card shows: emoji badge, user label, FSM state names, hint
        const STEPS: {
            icon: string; label: string; desc: string;
            fsmLabel: string;   // the FSM state(s) this maps to
        }[] = [
            {
                icon: '📷', label: 'Camera',
                desc: 'No data collection — local AI',
                fsmLabel: 'PRE-CAMERA',
            },
            {
                icon: '🤚', label: 'Ready',
                desc: 'Face open palm towards camera',
                fsmLabel: 'IDLE → READY',
            },
            {
                icon: '☝️', label: 'Click',
                desc: 'Point index finger up (pinch: thumb + 3 fingers)',
                fsmLabel: 'READY',
            },
            {
                icon: '🤚', label: 'Release',
                desc: 'Open palm again to release',
                fsmLabel: 'COMMIT_POINTER',
            },
        ];

        STEPS.forEach((s, i) => {
            if (i > 0) {
                const arrow = document.createElement('div');
                arrow.className = 'omega-step-arrow';
                arrow.textContent = '›';
                track.appendChild(arrow);
            }
            const step = document.createElement('div');
            step.className = 'omega-step idle';
            step.id = `omega-step-${i}`;
            step.innerHTML = `
                <div class="step-badge">
                    ${s.icon}
                    <span class="step-num-badge">${i + 1}</span>
                </div>
                <div class="step-text">
                    <span class="step-label">${s.label}</span>
                    <span class="step-fsm">${s.fsmLabel}</span>
                    <span class="step-desc">${s.desc}</span>
                </div>`;
            track.appendChild(step);
        });

        this.coachBar.appendChild(track);

        const subtitle = document.createElement('div');
        subtitle.className = 'omega-coach-subtitle';
        subtitle.innerHTML = '⚙ Tap the floating ⚙ to tune settings &nbsp;·&nbsp; 🔊 Turn up volume for audio feedback';
        this.coachBar.appendChild(subtitle);

        const skipBtn = document.createElement('button');
        skipBtn.id = 'omega-skip-btn';
        skipBtn.textContent = 'Skip';
        skipBtn.addEventListener('click', () => this.hideCoachBar());
        this.coachBar.appendChild(skipBtn);

        this.root.appendChild(this.coachBar);
        // Set initial state
        this.applyCoachState('__CAMERA_OFF__', false);
    }

    /** Apply FSM state to coach bar — decoupled, reads only from event bus FSM events */
    private applyCoachState(fsmState: FsmState, isCoast: boolean): void {
        this.currentFsmState = fsmState;
        const targetStep = FSM_TO_STEP[fsmState];
        this.currentStep = targetStep;

        for (let i = 0; i < 4; i++) {
            const el = document.getElementById(`omega-step-${i}`);
            if (!el) continue;
            let cls = 'omega-step ';
            if (i < targetStep)          cls += 'done';
            else if (i === targetStep)   cls += isCoast ? 'coast' : 'active';
            else                         cls += 'idle';
            el.className = cls;
        }
    }

    /** Legacy helper kept for external callers that set step directly */
    private setCoachStep(step: CoachStep): void {
        const fsmMap: FsmState[] = ['__CAMERA_OFF__', 'IDLE', 'READY', 'COMMIT_POINTER'];
        this.applyCoachState(fsmMap[step] ?? '__CAMERA_OFF__', false);
    }

    private hideCoachBar(): void {
        this.coachVisible = false;
        this.coachBar.style.display = 'none';
    }

    // ── CTA Hero ─────────────────────────────────────────────────────────────

    private buildCtaOverlay(): void {
        this.ctaOverlay = document.createElement('div');
        this.ctaOverlay.id = 'omega-cta-overlay';

        this.ctaBtn = document.createElement('button');
        this.ctaBtn.id = 'omega-cta-btn';
        this.ctaBtn.textContent = 'START CAMERA';
        this.ctaBtn.addEventListener('click', async () => {
            this.ctaBtn.textContent = 'Starting…';
            this.ctaBtn.disabled = true;
            this.eventBus.publish('AUDIO_UNLOCK', null);
            try {
                await this.callbacks.onCameraStart();
                this.dismissCtaOverlay();
                this.setCoachStep(1);
            } catch (e) {
                this.ctaBtn.textContent = 'Error — retry';
                this.ctaBtn.disabled = false;
            }
        });

        const heroCard = document.createElement('div');
        heroCard.id = 'omega-hero-card';
        heroCard.innerHTML = `
            <h2>HFO × tldraw Interactive Whiteboard</h2>
            <p>Draw, present &amp; collaborate with hand gestures — no mouse, no touch.<br>
               The coach bar guides you through each gesture.</p>
            <div class="tagline">Best on a big screen — cast to TV or projector for presentations</div>
        `;

        this.ctaOverlay.appendChild(this.ctaBtn);
        this.ctaOverlay.appendChild(heroCard);
        this.root.appendChild(this.ctaOverlay);
    }

    private dismissCtaOverlay(): void {
        this.ctaOverlay.style.transition = 'opacity 0.5s ease';
        this.ctaOverlay.style.opacity = '0';
        setTimeout(() => { this.ctaOverlay.style.display = 'none'; }, 520);
    }

    // ── Bottom Banner ─────────────────────────────────────────────────────────

    private buildBottomBanner(): void {
        const banner = document.createElement('div');
        banner.id = 'omega-bottom-banner';

        banner.innerHTML = `
            <div class="omega-banner-brand">
                HFO Interactive Whiteboard
                <span class="free-pill">FREE</span>
            </div>
            <div class="omega-banner-actions">
                <a class="omega-banner-btn kofi"
                   href="https://ko-fi.com/hfo" target="_blank" rel="noopener">
                    ☕ Ko-fi
                </a>
                <a class="omega-banner-btn consult"
                   href="mailto:hfo@hfo.ai?subject=AI+Consulting" target="_blank" rel="noopener">
                    🤖 AI Consulting
                </a>
                <button class="omega-banner-btn support" id="omega-remove-banner-btn">
                    ● SUPPORT · REMOVE BANNER
                </button>
            </div>
        `;

        document.getElementById('omega-remove-banner-btn')?.addEventListener('click', () => {
            window.open('https://ko-fi.com/hfo/tiers', '_blank', 'noopener');
        });

        // Wire after DOM insert (banner appended after)
        setTimeout(() => {
            banner.querySelector<HTMLElement>('#omega-remove-banner-btn')
                ?.addEventListener('click', () => {
                    window.open('https://ko-fi.com/hfo/tiers', '_blank', 'noopener');
                });
        }, 0);

        this.root.appendChild(banner);
    }

    // ── Gear Button + Settings Drawer ─────────────────────────────────────────

    private buildGearButton(): void {
        this.gearBtn = document.createElement('button');
        this.gearBtn.id = 'omega-gear-btn';
        this.gearBtn.title = 'Settings (` or F1)';
        this.gearBtn.textContent = '⚙';
        this.gearBtn.addEventListener('click', () => this.toggleSettings());
        this.root.appendChild(this.gearBtn);
    }

    private buildSettingsDrawer(): void {
        this.settingsDrawer = document.createElement('div');
        this.settingsDrawer.id = 'omega-settings-drawer';

        const header = document.createElement('h3');
        header.textContent = 'Omega v13 Settings';
        this.settingsDrawer.appendChild(header);

        // Layer opacity section — uses injected layerManager (ATDD-ARCH-001)
        this.buildDrawerSection('Layer Opacity', () => {
            for (const layer of this.layerManager.allLayers()) {
                this.addSlider(
                    this.settingsDrawer, layer.label,
                    0, 1, 0.05, layer.opacity,
                    (v) => this.layerManager.setOpacity(layer.id, v)
                );
            }
        });

        // FSM tuning section
        this.buildDrawerSection('Gesture Tuning', () => {
            const cfg = this.callbacks.configManager.get();
            this.addSlider(this.settingsDrawer, 'Schmitt High', 0, 1, 0.01, cfg.fsm_conf_high,
                (v) => this.callbacks.configManager.update({ fsm_conf_high: v }));
            this.addSlider(this.settingsDrawer, 'Schmitt Low', 0, 1, 0.01, cfg.fsm_conf_low,
                (v) => this.callbacks.configManager.update({ fsm_conf_low: v }));
            this.addSlider(this.settingsDrawer, 'Dwell Ready (ticks)', 1, 60, 1, cfg.fsm_dwell_ready,
                (v) => this.callbacks.configManager.update({ fsm_dwell_ready: v }));
            this.addSlider(this.settingsDrawer, 'Dwell Commit (ticks)', 1, 60, 1, cfg.fsm_dwell_commit,
                (v) => this.callbacks.configManager.update({ fsm_dwell_commit: v }));
        });

        // Kalman smoother tuning
        // MediaPipe Tasks API has NO built-in smoothing — Kalman is the only temporal filter.
        // Q = how much to trust the model prediction (low = more smoothing).
        // R = how noisy the raw landmark measurements are (high = more smoothing).
        this.buildDrawerSection('Kalman Smoother', () => {
            const cfg = this.callbacks.configManager.get();
            this.addSlider(this.settingsDrawer, 'Process Noise Q', 0.001, 1, 0.001, cfg.kalman_q,
                (v) => this.callbacks.configManager.update({ kalman_q: v }));
            this.addSlider(this.settingsDrawer, 'Meas. Noise R', 0.1, 50, 0.1, cfg.kalman_r,
                (v) => this.callbacks.configManager.update({ kalman_r: v }));
        });

        // Physics tuning
        this.buildDrawerSection('Physics (Velocnertia)', () => {
            const cfg = this.callbacks.configManager.get();
            this.addSlider(this.settingsDrawer, 'Max Velocity', 1, 200, 1, cfg.physics_max_velocity,
                (v) => this.callbacks.configManager.update({ physics_max_velocity: v }));
            this.addSlider(this.settingsDrawer, 'Spring Constant', 1, 50, 0.5, cfg.physics_spring_constant,
                (v) => this.callbacks.configManager.update({ physics_spring_constant: v }));
        });

        this.root.appendChild(this.settingsDrawer);
    }

    private buildDrawerSection(title: string, builder: () => void): void {
        const sectionTitle = document.createElement('div');
        sectionTitle.className = 'omega-section-title';
        sectionTitle.textContent = title;
        this.settingsDrawer.appendChild(sectionTitle);
        builder();
    }

    private addSlider(
        parent: HTMLElement, label: string,
        min: number, max: number, step: number, value: number,
        onChange: (v: number) => void
    ): void {
        const row = document.createElement('div');
        row.className = 'omega-slider-row';

        const lbl = document.createElement('label');
        lbl.textContent = label;

        const input = document.createElement('input');
        input.type = 'range';
        Object.assign(input, { min, max, step, value });

        const val = document.createElement('span');
        val.className = 'val';
        val.textContent = String(value);

        input.addEventListener('input', () => {
            const v = parseFloat(input.value);
            val.textContent = step < 1 ? v.toFixed(2) : String(Math.round(v));
            onChange(v);
        });

        row.appendChild(lbl);
        row.appendChild(input);
        row.appendChild(val);
        parent.appendChild(row);
    }

    private toggleSettings(): void {
        this.settingsOpen = !this.settingsOpen;
        this.settingsDrawer.classList.toggle('open', this.settingsOpen);
        this.gearBtn.classList.toggle('open', this.settingsOpen);
        // LIE2 FIX: when closed, SETTINGS layer must not intercept gesture pointer events
        // (z=30 means an always-'auto' SETTINGS div silently blocks the TLDRAW layer below)
        this.layerManager.setPointerEvents(LAYER.SETTINGS, this.settingsOpen ? 'auto' : 'none');
        this.eventBus.publish('SETTINGS_PANEL_STATE', { open: this.settingsOpen });
    }

    // ── Event bus handlers ────────────────────────────────────────────────────

    private onStateChange(data: { handId: number; currentState: string; previousState?: string }): void {
        const fsm = data.currentState as FsmState;
        // Only handle known FSM states — ignore anything unexpected (fully decoupled)
        if (!(fsm in FSM_TO_STEP)) return;
        const isCoast = COAST_STATES.has(fsm);
        this.applyCoachState(fsm, isCoast);
    }

    private onFrameProcessed(hands: any[]): void {
        // If camera just started (still PRE-CAMERA) and we get frames, move to IDLE
        if (this.currentFsmState === '__CAMERA_OFF__' && hands !== undefined) {
            this.applyCoachState('IDLE', false);
        }
    }
}
