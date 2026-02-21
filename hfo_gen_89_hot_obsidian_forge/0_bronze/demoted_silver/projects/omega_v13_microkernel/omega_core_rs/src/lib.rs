use wasm_bindgen::prelude::*;

#[wasm_bindgen]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FsmStateType {
    Idle,
    IdleCoast,
    Ready,
    ReadyCoast,
    CommitPointer,
    CommitCoast,
}

#[wasm_bindgen]
pub struct GestureFsmRs {
    state: FsmStateType,
    conf_high: f64,
    conf_low: f64,
    dwell_limit_ready_ms: f64,
    dwell_limit_commit_ms: f64,
    coast_timeout_ms: f64,
    
    current_confidence: f64,
    dwell_accumulator_ms: f64,
    coast_elapsed_ms: f64,
    last_frame_ms: f64,
}

#[wasm_bindgen]
impl GestureFsmRs {
    #[wasm_bindgen(constructor)]
    pub fn new() -> Self {
        Self {
            state: FsmStateType::Idle,
            conf_high: 0.64,
            conf_low: 0.50,
            dwell_limit_ready_ms: 100.0,
            dwell_limit_commit_ms: 100.0,
            coast_timeout_ms: 500.0,
            
            current_confidence: 0.0,
            dwell_accumulator_ms: 0.0,
            coast_elapsed_ms: 0.0,
            last_frame_ms: f64::NAN,
        }
    }

    pub fn get_state(&self) -> FsmStateType {
        self.state
    }

    pub fn configure(&mut self, dwell_ready_ms: Option<f64>, dwell_commit_ms: Option<f64>, coast_timeout_ms: Option<f64>) {
        if let Some(val) = dwell_ready_ms { self.dwell_limit_ready_ms = val; }
        if let Some(val) = dwell_commit_ms { self.dwell_limit_commit_ms = val; }
        if let Some(val) = coast_timeout_ms { self.coast_timeout_ms = val; }
    }

    pub fn force_coast(&mut self) {
        match self.state {
            FsmStateType::Idle => self.state = FsmStateType::IdleCoast,
            FsmStateType::Ready => self.state = FsmStateType::ReadyCoast,
            FsmStateType::CommitPointer => self.state = FsmStateType::CommitCoast,
            _ => {}
        }
    }

    pub fn process_frame(&mut self, gesture: &str, confidence: f64, _x: f64, _y: f64, now_ms: f64) {
        let delta_ms = if self.last_frame_ms.is_nan() { 0.0 } else { now_ms - self.last_frame_ms };
        self.last_frame_ms = now_ms;
        self.current_confidence = confidence;

        if self.is_coast_state() {
            self.coast_elapsed_ms += delta_ms;
            if self.coast_elapsed_ms >= self.coast_timeout_ms {
                self.transition_to(FsmStateType::Idle);
                self.dwell_accumulator_ms = 0.0;
                return;
            }
        } else {
            self.coast_elapsed_ms = 0.0;
        }

        match self.state {
            FsmStateType::Idle => self.handle_idle(gesture, delta_ms),
            FsmStateType::IdleCoast => self.handle_idle_coast(gesture),
            FsmStateType::Ready => self.handle_ready(gesture, delta_ms),
            FsmStateType::ReadyCoast => self.handle_ready_coast(gesture),
            FsmStateType::CommitPointer => self.handle_commit(gesture, delta_ms),
            FsmStateType::CommitCoast => self.handle_commit_coast(gesture),
        }
    }

    fn is_coast_state(&self) -> bool {
        matches!(self.state, FsmStateType::IdleCoast | FsmStateType::ReadyCoast | FsmStateType::CommitCoast)
    }

    fn transition_to(&mut self, new_state: FsmStateType) {
        if self.state == FsmStateType::Idle && new_state == FsmStateType::CommitPointer {
            return;
        }
        self.state = new_state;
    }

    fn handle_idle(&mut self, gesture: &str, delta_ms: f64) {
        if gesture == "open_palm" && self.current_confidence >= self.conf_high {
            self.dwell_accumulator_ms += delta_ms;
            if self.dwell_accumulator_ms >= self.dwell_limit_ready_ms {
                self.transition_to(FsmStateType::Ready);
                self.dwell_accumulator_ms = 0.0;
            }
        } else {
            self.dwell_accumulator_ms = (self.dwell_accumulator_ms - (delta_ms * 2.0)).max(0.0);
            if self.current_confidence < self.conf_low {
                self.transition_to(FsmStateType::IdleCoast);
            }
        }
    }

    fn handle_idle_coast(&mut self, _gesture: &str) {
        if self.current_confidence >= self.conf_low {
            self.transition_to(FsmStateType::Idle);
        }
    }

    fn handle_ready(&mut self, gesture: &str, delta_ms: f64) {
        if gesture == "closed_fist" && self.current_confidence >= self.conf_high {
            self.dwell_accumulator_ms += delta_ms;
            if self.dwell_accumulator_ms >= self.dwell_limit_commit_ms {
                self.transition_to(FsmStateType::CommitPointer);
                self.dwell_accumulator_ms = 0.0;
            }
        } else if gesture != "open_palm" && gesture != "closed_fist" {
            self.transition_to(FsmStateType::Idle);
            self.dwell_accumulator_ms = 0.0;
        } else if self.current_confidence < self.conf_low {
            self.transition_to(FsmStateType::ReadyCoast);
        } else {
            self.dwell_accumulator_ms = (self.dwell_accumulator_ms - (delta_ms * 2.0)).max(0.0);
        }
    }

    fn handle_ready_coast(&mut self, _gesture: &str) {
        if self.current_confidence >= self.conf_low {
            self.transition_to(FsmStateType::Ready);
        }
    }

    fn handle_commit(&mut self, gesture: &str, _delta_ms: f64) {
        if gesture == "open_palm" && self.current_confidence >= self.conf_high {
            self.transition_to(FsmStateType::Ready);
            self.dwell_accumulator_ms = 0.0;
        } else if self.current_confidence < self.conf_low {
            self.transition_to(FsmStateType::CommitCoast);
        }
    }

    fn handle_commit_coast(&mut self, _gesture: &str) {
        if self.current_confidence >= self.conf_low {
            self.transition_to(FsmStateType::CommitPointer);
        }
    }
}
