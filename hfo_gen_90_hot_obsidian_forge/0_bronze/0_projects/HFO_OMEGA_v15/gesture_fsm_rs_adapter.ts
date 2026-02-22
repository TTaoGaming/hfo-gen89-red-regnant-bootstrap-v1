import init, { GestureFsmRs, FsmStateType } from './omega_core_rs/pkg/omega_core_rs.js';
import { FsmState, StateIdle, StateIdleCoast, StateReady, StateReadyCoast, StateCommit, StateCommitCoast, RawCoord } from './types.js';

// Ensure WASM is initialized before use
let wasmInitialized = false;
export async function initWasm() {
    if (!wasmInitialized) {
        await init();
        wasmInitialized = true;
    }
}

export class GestureFSM {
    private rsFsm: GestureFsmRs;

    constructor() {
        if (!wasmInitialized) {
            throw new Error("WASM not initialized. Call initWasm() first.");
        }
        this.rsFsm = new GestureFsmRs();
    }

    public get state(): FsmState {
        const rsState = this.rsFsm.get_state();
        switch (rsState) {
            case FsmStateType.Idle: return new StateIdle();
            case FsmStateType.IdleCoast: return new StateIdleCoast();
            case FsmStateType.Ready: return new StateReady();
            case FsmStateType.ReadyCoast: return new StateReadyCoast();
            case FsmStateType.CommitPointer: return new StateCommit();
            case FsmStateType.CommitCoast: return new StateCommitCoast();
            default: return new StateIdle();
        }
    }

    // We need a setter for state to satisfy the interface, though it shouldn't be used directly
    public set state(val: FsmState) {
        // In a strict FSM, we shouldn't allow arbitrary state setting.
        // But to satisfy the existing TS interface, we might need to map it back,
        // or just ignore it since the Rust FSM manages its own state.
        console.warn("Direct state mutation is ignored in Rust FSM adapter.");
    }

    public configure(cfg: {
        dwellReadyMs?:   number;
        dwellCommitMs?:  number;
        coastTimeoutMs?: number;
    }): void {
        this.rsFsm.configure(cfg.dwellReadyMs, cfg.dwellCommitMs, cfg.coastTimeoutMs);
    }

    public processFrame(
        gesture: string,
        confidence: number,
        x: RawCoord = -1 as RawCoord,
        y: RawCoord = -1 as RawCoord,
        nowMs = performance.now()
    ) {
        this.rsFsm.process_frame(gesture, confidence, x as number, y as number, nowMs);
    }

    public forceCoast() {
        this.rsFsm.force_coast();
    }
}
