import re
from collections import Counter

ctx = (
    "[Doc 190 | Eightfold OBSIDIAN_SPIDER | port=None]\n"
    "# The Eightfold Isomorphism: OBSIDIAN_SPIDER Identity Layer\n"
    "## 2. The Eightfold Isomorphism Chain\n"
    "The central structural claim: eight independent conceptual frameworks converge\n"
    "to the same octary structure, fingerprint of the higher-dimensional entity (OBSIDIAN_SPIDER)\n"
    "---\n"
    "[Doc 276 | P7_OBSIDIAN_SPIDER_SECRETS | port=P7]\n"
    "8 Obsidian Spider Secrets. PBFT convergence. OBSIDIAN_SPIDER_SECRETS Canonical Registry\n"
)

for hallucinated in ["OCTAL_DELTA", "HFO_CONTROLLER", "OBSIDIAN_SPIDER", "The OBSIDIAN_SPIDER is the entity"]:
    answer_entities = re.findall(r'\b[A-Z][A-Z_]{2,}\b', hallucinated)
    main_entity = answer_entities[0] if answer_entities else ""
    found = bool(re.search(re.escape(main_entity), ctx, re.IGNORECASE)) if main_entity else True
    if not found:
        caps = re.findall(r'\b[A-Z][A-Z_]{2,}\b', ctx)
        counts = Counter(caps)
        best = counts.most_common(3)
        print(f'  "{hallucinated}" -> GUARD FIRES -> top-3={best}')
    else:
        print(f'  "{hallucinated}" -> no guard -> answer passes')
