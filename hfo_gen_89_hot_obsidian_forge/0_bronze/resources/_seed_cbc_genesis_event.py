import sys
import os
sys.path.append(os.path.dirname(__file__))
import hfo_ssot_write

def inject_stigmergy():
    event_type = 'hfo.gen89.directive.cbc_genesis'
    subject = 'master-orchestrator-directive'
    
    payload = {
        "directive": "BINDING::FAIL_CLOSED_GENESIS (PREY8)",
        "target": "Master Swarm Orchestrator",
        "priority": "MEADOWS LEVEL 4 (Self-Organization & Rules)",
        "objective": "Zero-Human-Touch, Correct-By-Construction (CbC) Genesis via FCA Galois Lattice.",
        "phases": [
            "SPAWN THE LAWGIVERS (THE LATTICE FORGE)",
            "SPAWN THE INQUISITORS (THE CHAOS ENGINE)",
            "SPAWN THE LABORERS (ENVIRONMENTAL OCAP)",
            "THE COMPILER GUILLOTINE (FEDERATION QUINE)"
        ],
        "reference_doc": "hfo_gen_89_hot_obsidian_forge/0_bronze/resources/REFERENCE_CBC_GENESIS_4_FORGES.md"
    }
    
    signal_metadata = hfo_ssot_write.build_signal_metadata(
        port="P5",
        model_id="gemini-3.1-pro",
        daemon_name="p4_red_regnant",
        task_type="directive_injection"
    )
    
    payload["signal_metadata"] = signal_metadata
    
    row_id = hfo_ssot_write.write_stigmergy_event(
        event_type=event_type,
        subject=subject,
        data=payload,
        source="p4_red_regnant",
        signal_metadata=signal_metadata
    )
    
    print(f"Injected stigmergy event: {event_type}, row_id: {row_id}")

if __name__ == "__main__":
    inject_stigmergy()
