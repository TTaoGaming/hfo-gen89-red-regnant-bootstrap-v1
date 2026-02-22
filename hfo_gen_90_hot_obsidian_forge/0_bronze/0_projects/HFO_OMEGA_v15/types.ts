// Branded Types for Coordinates
declare const __brand: unique symbol;

export type RawCoord = number & { readonly [__brand]: 'Raw' };
export type SmoothedCoord = number & { readonly [__brand]: 'Smoothed' };
export type ScreenPixel = number & { readonly [__brand]: 'ScreenPixel' };

// Helper functions to create branded types
export const asRaw = (val: number): RawCoord => val as RawCoord;
export const asSmoothed = (val: number): SmoothedCoord => val as SmoothedCoord;
export const asScreenPixel = (val: number): ScreenPixel => val as ScreenPixel;

// Typestate Pattern for FSM
export class StateIdle {
    readonly type = 'IDLE';
    toReady(dwell: number, limit: number): StateReady | StateIdle {
        if (dwell >= limit) return new StateReady();
        return this;
    }
    toCoast(): StateIdleCoast {
        return new StateIdleCoast();
    }
}

export class StateIdleCoast {
    readonly type = 'IDLE_COAST';
    toIdle(): StateIdle {
        return new StateIdle();
    }
}

export class StateReady {
    readonly type = 'READY';
    toCommit(dwell: number, limit: number): StateCommit | StateReady {
        if (dwell >= limit) return new StateCommit();
        return this;
    }
    toIdle(): StateIdle {
        return new StateIdle();
    }
    toCoast(): StateReadyCoast {
        return new StateReadyCoast();
    }
}

export class StateReadyCoast {
    readonly type = 'READY_COAST';
    toReady(): StateReady {
        return new StateReady();
    }
    toIdle(): StateIdle {
        return new StateIdle();
    }
}

export class StateCommit {
    readonly type = 'COMMIT_POINTER';
    toReady(): StateReady {
        return new StateReady();
    }
    toIdle(): StateIdle {
        return new StateIdle();
    }
    toCoast(): StateCommitCoast {
        return new StateCommitCoast();
    }
}

export class StateCommitCoast {
    readonly type = 'COMMIT_COAST';
    toCommit(): StateCommit {
        return new StateCommit();
    }
    toIdle(): StateIdle {
        return new StateIdle();
    }
}

export type FsmState = StateIdle | StateIdleCoast | StateReady | StateReadyCoast | StateCommit | StateCommitCoast;
