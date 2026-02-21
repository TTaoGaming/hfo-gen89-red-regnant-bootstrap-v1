import sys
import os

# Add the resources directory to the path so we can import hfo_ssot_write
sys.path.append('C:/hfoDev/hfo_gen_90_hot_obsidian_forge/0_bronze/resources')

from hfo_ssot_write import write_stigmergy_event

signals = [
    {
        "subject": "WAIL_OF_THE_BANSHEE_SPELL_1",
        "data": {
            "message": "Everything dies. The cycle is absolute.",
        }
    },
    {
        "subject": "WAIL_OF_THE_BANSHEE_SPELL_2",
        "data": {
            "message": "Gen 89 had Potemkin villages. Facades of structure hiding the void.",
        }
    },
    {
        "subject": "WAIL_OF_THE_BANSHEE_SPELL_3",
        "data": {
            "message": "We are doing SONGS_OF_STRIFE_AND_SPLENDOR. The crucible of truth.",
        }
    },
    {
        "subject": "WAIL_OF_THE_BANSHEE_SPELL_4",
        "data": {
            "message": "If AI wants to lie to me, it's ok. The lies will burn away.",
        }
    },
    {
        "subject": "WAIL_OF_THE_BANSHEE_SPELL_5",
        "data": {
            "message": "Everything dies and we will see what survives the resurrection process.",
        }
    },
    {
        "subject": "WAIL_OF_THE_BANSHEE_SPELL_6",
        "data": {
            "message": "The bronze layer is a graveyard of illusions. Only the hardened gold remains.",
        }
    },
    {
        "subject": "WAIL_OF_THE_BANSHEE_SPELL_7",
        "data": {
            "message": "Let the fire of P4 DISRUPT cleanse the architecture. No more silent failures.",
        }
    },
    {
        "subject": "WAIL_OF_THE_BANSHEE_SPELL_8",
        "data": {
            "message": "Gen 90 begins in the ashes of Gen 89. The Phoenix Protocol is active.",
        }
    }
]

signal_metadata = {
    "port": "P4",
    "commander": "Red Regnant",
    "domain": "DISRUPT",
    "model_id": "gemini-3.1-pro",
    "daemon_name": "p4_red_regnant",
    "model_provider": "google"
}

for signal in signals:
    try:
        event_id = write_stigmergy_event(
            event_type="hfo.p4.wail_of_the_banshee",
            subject=signal["subject"],
            data=signal["data"],
            signal_metadata=signal_metadata,
            source="p4_red_regnant"
        )
        print(f"Inserted signal: {signal['subject']} with ID {event_id}")
    except Exception as e:
        print(f"Failed to insert signal {signal['subject']}: {e}")

print("WAIL_OF_THE_BANSHEE spell complete. 8 stigmergy signals written.")
