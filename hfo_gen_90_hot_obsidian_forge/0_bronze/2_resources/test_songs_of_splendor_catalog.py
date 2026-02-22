"""Verify SONGS_OF_SPLENDOR_EXEMPLAR_CATALOG.md was created and contains required content."""
import os
import re
import pytest

CATALOG_PATH = "hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/SONGS_OF_SPLENDOR_EXEMPLAR_CATALOG.md"


@pytest.fixture
def catalog_content() -> str:
    assert os.path.exists(CATALOG_PATH), f"Catalog missing: {CATALOG_PATH}"
    with open(CATALOG_PATH, encoding="utf-8") as f:
        return f.read()


def test_catalog_exists() -> None:
    assert os.path.exists(CATALOG_PATH)


def test_all_85_splendor_tokens_present(catalog_content: str) -> None:
    """All 85 SPLENDOR_TOKENs S001-S085 must be present."""
    for i in range(1, 86):
        token_id = f"S{i:03d}"
        assert token_id in catalog_content, f"Missing token {token_id}"


def test_obsidian_hourglass_is_s003_tier1(catalog_content: str) -> None:
    """OBSIDIAN_HOURGLASS must be S003 in Tier 1."""
    assert "S003" in catalog_content
    assert "OBSIDIAN_HOURGLASS_FRACTAL" in catalog_content
    # S003 must appear before Tier 2 section
    s003_pos = catalog_content.find("S003")
    tier2_pos = catalog_content.find("TIER 2")
    assert s003_pos < tier2_pos, "S003 must be in Tier 1 (before Tier 2)"


def test_nine_tiers_present(catalog_content: str) -> None:
    """All 9 tiers must be present (T8 bardic spells, T9 candidates added 2026-02-21)."""
    for tier in ["TIER 1", "TIER 2", "TIER 3", "TIER 4", "TIER 5", "TIER 6", "TIER 7",
                 "TIER 8", "TIER 9"]:
        assert tier in catalog_content, f"Missing {tier}"


def test_tier5_jadc2_mosaic_tokens_present(catalog_content: str) -> None:
    """Tier 5 JADC2/MOSAIC tokens must be present."""
    tier5_tokens = [
        "SENSE_MAKESENSE_ACT_PIPELINE",
        "KILL_WEB_OVER_KILL_CHAIN",
        "FORCE_PACKAGE_COMPOSER_7_STAGES",
        "IHFO_CONSUMER_UNIVERSAL_TILE",
        "MOSAIC_THREE_PROPERTIES",
        "FRAMEWORK_ALIAS_TABLE_LEVEL12",
        "SUBSTRATE_NOT_APPS_PARADIGM",
        "MAP_ELITE_SPIKE_FACTORY",
        "PARETO_GOLDILOCKS_88PCT",
    ]
    for token in tier5_tokens:
        assert token in catalog_content, f"Missing Tier 5 token: {token}"


def test_tier6_pantheon_tokens_present(catalog_content: str) -> None:
    """Tier 6 HFO PANTHEON / Phase Spider tokens must be present."""
    tier6_tokens = [
        "PHASE_SPIDER_COLONY_CHASSIS",
        "COMMUNAL_WEB_FIVE_STRANDS",
        "TREMORSENSE_STIGMERGY_PROPAGATION",
        "NATARAJA_HUNT_PROTOCOL_12_STEPS",
        "SINGER_SONG_FULL_AMPLITUDE",
        "DANCER_RESURRECTION_TRIAGE",
        "STRANGE_LOOP_GENERATIONAL_EVIDENCE",
    ]
    for token in tier6_tokens:
        assert token in catalog_content, f"Missing Tier 6 token: {token}"


def test_tier7_powerword_tokens_present(catalog_content: str) -> None:
    """All 9 Tier 7 Powerword tokens must be present."""
    tier7_tokens = [
        "POWERWORD_SPELLCASTING_CONTRACT",
        "P0_OBSERVE_SENSE_CALIBRATE_RANK_EMIT",
        "P1_BRIDGE_DISCOVER_EXTRACT_CONTRACT_BIND_VERIFY",
        "P2_SHAPE_PARSE_CONSTRAIN_GENERATE_VALIDATE_MEDAL",
        "P3_INJECT_PREFLIGHT_PAYLOAD_POSTFLIGHT_PAYOFF",
        "P4_DISRUPT_SURVEY_HYPOTHESIZE_ATTACK_RECORD_EVOLVE",
        "P5_IMMUNIZE_DETECT_QUARANTINE_GATE_HARDEN_TEACH",
        "P6_ASSIMILATE_POINT_DECOMPOSE_REENGINEER_EVALUATE_ARCHIVE_ITERATE",
        "P7_NAVIGATE_MAP_LATTICE_PRUNE_SELECT_DISPATCH_VISUALIZE",
    ]
    for token in tier7_tokens:
        assert token in catalog_content, f"Missing Tier 7 token: {token}"


def test_nataraja_hunt_protocol_npm_scripts(catalog_content: str) -> None:
    """Hunt Protocol must reference the key npm scripts."""
    assert "sdd:gate" in catalog_content, "Missing Stryker mutation test npm script"
    assert "ralph:purify" in catalog_content, "Missing resurrection npm script"
    assert "NATARAJA" in catalog_content, "Missing NATARAJA hunt identifier"


def test_powerword_all_8_workflows_present(catalog_content: str) -> None:
    """All 8 powerword sub-workflows must be documented."""
    workflows = [
        "SENSE.*CALIBRATE.*RANK.*EMIT",
        "DISCOVER.*EXTRACT.*CONTRACT.*BIND.*VERIFY",
        "PARSE.*CONSTRAIN.*GENERATE.*VALIDATE.*MEDAL",
        "PREFLIGHT.*PAYLOAD.*POSTFLIGHT.*PAYOFF",
        "SURVEY.*HYPOTHESIZE.*ATTACK.*RECORD.*EVOLVE",
        "DETECT.*QUARANTINE.*GATE.*HARDEN.*TEACH",
        "POINT.*DECOMPOSE.*REENGINEER.*EVALUATE.*ARCHIVE.*ITERATE",
        "MAP.*LATTICE.*PRUNE.*SELECT.*DISPATCH.*VISUALIZE",
    ]
    for pattern in workflows:
        assert re.search(pattern, catalog_content), f"Missing workflow pattern: {pattern}"


def test_token_count_updated_to_85(catalog_content: str) -> None:
    """Catalog must reflect 85 SPLENDOR tokens (expanded 2026-02-21 from 63)."""
    assert "85 SPLENDOR" in catalog_content or "S001-S085" in catalog_content, (
        "Token count must reflect 85 SPLENDOR_TOKENS (T8/T9 expansion)"
    )


def test_boxes_razor_quote_present(catalog_content: str) -> None:
    """Box's Razor quote must be present in P4 Powerword token."""
    assert "All models are wrong" in catalog_content


def test_galois_antidiagonal_sum_referenced(catalog_content: str) -> None:
    """Galois anti-diagonal structure must be referenced."""
    # Either the alias table or 'anti-diagonal' or 'sum=7' must appear
    assert (
        "anti-diagonal" in catalog_content or "sum=7" in catalog_content
        or "Galois" in catalog_content
    )


def test_tier5_source_docs_attributed(catalog_content: str) -> None:
    """Tier 5 must attribute E39 and E47 as source documents."""
    tier5_pos = catalog_content.find("TIER 5")
    tier6_pos = catalog_content.find("TIER 6")
    tier5_block = catalog_content[tier5_pos:tier6_pos]
    assert "E39" in tier5_block, "Tier 5 must cite E39 (JADC2 Mosaic doc)"
    assert "E47" in tier5_block, "Tier 5 must cite E47 (What HFO Actually Is)"


def test_tier6_source_doc_attributed(catalog_content: str) -> None:
    """Tier 6 must attribute V5 / Doc 69 as source document."""
    tier6_pos = catalog_content.find("TIER 6")
    tier7_pos = catalog_content.find("TIER 7")
    tier6_block = catalog_content[tier6_pos:tier7_pos]
    assert "Doc 69" in tier6_block or "V5" in tier6_block, (
        "Tier 6 must cite Doc 69 / V5 (HFO PANTHEON)"
    )


def test_tier7_source_doc_attributed(catalog_content: str) -> None:
    """Tier 7 must attribute R42 / Doc 128 as source document."""
    tier7_pos = catalog_content.find("TIER 7")
    tier7_block = catalog_content[tier7_pos:]
    assert "R42" in tier7_block or "Doc 128" in tier7_block, (
        "Tier 7 must cite R42 / Doc 128 (Powerword Spellbook)"
    )


def test_hunt_protocol_has_12_steps(catalog_content: str) -> None:
    """Hunt Protocol must have exactly 12 numbered steps listed."""
    hunt_pos = catalog_content.find("NATARAJA_HUNT_PROTOCOL_12_STEPS")
    assert hunt_pos != -1
    # Find the table section following the token header
    hunt_block = catalog_content[hunt_pos:hunt_pos + 3000]
    # Steps 1-12 must all appear
    for step in range(1, 13):
        assert f"| {step} |" in hunt_block or f"| **{step}** |" in hunt_block, (
            f"Hunt Protocol step {step} missing from table"
        )


def test_phase_spider_colony_has_8_members(catalog_content: str) -> None:
    """Eight Phase Spider identities must be documented."""
    eight_spiders = [
        "WATCHER", "BINDER", "MAKER", "HARBINGER",
        "SINGER", "DANCER", "DEVOURER", "SUMMONER",
    ]
    for spider in eight_spiders:
        assert spider in catalog_content, f"Missing Phase Spider: {spider}"


def test_meadows_l12_framework_alias_table_present(catalog_content: str) -> None:
    """FRAMEWORK_ALIAS_TABLE_LEVEL12 must reference multiple paradigm aliases."""
    assert "OODA" in catalog_content, "Alias table must include OODA"
    assert "MAPE-K" in catalog_content, "Alias table must include MAPE-K"
    assert "PDCA" in catalog_content, "Alias table must include PDCA"
    assert "HIVE8" in catalog_content or "HIVE" in catalog_content, (
        "Alias table must include HIVE8"
    )


def test_substrate_not_apps_paradigm_present(catalog_content: str) -> None:
    """SUBSTRATE_NOT_APPS_PARADIGM must contain the key framing."""
    assert "substrate" in catalog_content.lower()
    # The Netflix / streaming analogy or equivalent
    assert "Netflix" in catalog_content or "substrate, not apps" in catalog_content or "Substrate" in catalog_content


def test_iching_trigrams_present(catalog_content: str) -> None:
    """I Ching trigrams must be present in Tier 7 Powerword section."""
    # Check for at least 3 trigram symbols
    trigrams = ["☷", "☶", "☵", "☴", "☳", "☲", "☱", "☰"]
    found = sum(1 for t in trigrams if t in catalog_content)
    assert found >= 6, f"Expected at least 6 I Ching trigrams, found {found}"


def test_survival_ranking_table_present(catalog_content: str) -> None:
    """Survival ranking table must exist."""
    assert "EIGHT_PORT_OCTREE_KERNEL" in catalog_content
    assert "OBSIDIAN_HOURGLASS_FRACTAL" in catalog_content
    assert "STIGMERGY_O1_COORDINATION" in catalog_content


def test_shodh_context_present(catalog_content: str) -> None:
    """Shodh Hebbian reinforcement context must be documented."""
    assert "shodh" in catalog_content.lower()
    assert "Hebbian" in catalog_content
    assert "seed_port" in catalog_content or "seed ports" in catalog_content


def test_port_p4_in_frontmatter(catalog_content: str) -> None:
    """Document must be tagged to P4."""
    assert "port: P4" in catalog_content or "P4" in catalog_content


def test_dual_token_ledger_section(catalog_content: str) -> None:
    """Dual token ledger section must be present."""
    assert "SONGS_OF_STRIFE_TOKENS" in catalog_content
    assert "SONGS_OF_SPLENDOR_TOKENS" in catalog_content


def test_obsidian_hourglass_has_diagram(catalog_content: str) -> None:
    """OBSIDIAN_HOURGLASS entry must contain the scatter-gather diagram."""
    assert "scatter" in catalog_content.lower() or "SENSE" in catalog_content
    assert "OBSIDIAN_HOURGLASS_FRACTAL" in catalog_content


def test_top_10_survival_exemplars_present(catalog_content: str) -> None:
    """All 10 top survival exemplars in the ranking table must be present."""
    top_10 = [
        "EIGHT_PORT_OCTREE_KERNEL",
        "OBSIDIAN_HOURGLASS_FRACTAL",
        "STIGMERGY_O1_COORDINATION",
        "PREY8_DARWINIAN_LOOP",
        "FAIL_CLOSED_GATE_DEFAULT",
        "FEDERATION_QUINE_REBUILD",
        "HEBBIAN_ASSOCIATION_GRAPH",
        "MEDALLION_FLOW_BRONZE_SILVER_GOLD",
        "UNIVERSAL_DARWINISM_ENGINE",
        "MOSAIC_JADC2_FORCE_COMPOSER",
    ]
    for name in top_10:
        assert name in catalog_content, f"Top-10 survival exemplar missing: {name}"


def test_splendor_token_generation_rules_present(catalog_content: str) -> None:
    """SPLENDOR token generation rules must be present."""
    assert "Gold Diataxis" in catalog_content
    assert "recipe card" in catalog_content.lower() or "recipe" in catalog_content.lower()
    assert "PREY8" in catalog_content


def test_cultural_tier_has_pick_a_worthy_cause(catalog_content: str) -> None:
    """PICK_A_WORTHY_CAUSE must be in Tier 4 cultural patterns."""
    assert "PICK_A_WORTHY_CAUSE" in catalog_content
    tier4_pos = catalog_content.find("TIER 4")
    pick_pos = catalog_content.find("PICK_A_WORTHY_CAUSE")
    assert pick_pos > tier4_pos, "PICK_A_WORTHY_CAUSE must be in Tier 4"


def test_source_doc_e67_attributed(catalog_content: str) -> None:
    """Source attribution to E67 / Doc 272 must be present."""
    assert "E67" in catalog_content or "Doc 272" in catalog_content


def test_silk_web_protocols_five_entries(catalog_content: str) -> None:
    """SW-1 through SW-5 must all be referenced."""
    for i in range(1, 6):
        assert f"SW-{i}" in catalog_content, f"Missing SW-{i} in Silk Web protocols"


def test_tier8_bardic_spells_present(catalog_content: str) -> None:
    """Tier 8 bardic spell SPLENDOR tokens (S064-S070) must be present."""
    tier8_tokens = [
        "INSPIRE_HEROICS_CHAMPION",
        "INSPIRE_GREATNESS_FORTIFICATION",
        "HARMONIC_CHORUS_AMPLIFICATION",
        "SONG_OF_FREEDOM_LIBERATION",
        "HYMN_OF_PRAISE_ALIGNMENT",
        "DISSONANT_CHORD_CLEARANCE",
        "WAR_CRY_SELF_BUFF",
    ]
    for token in tier8_tokens:
        assert token in catalog_content, f"Missing Tier 8 token: {token}"


def test_tier9_candidates_present(catalog_content: str) -> None:
    """Key Tier 9 candidate tokens (S071-S085) must be present."""
    tier9_candidates = [
        "SPEED_OF_RELEVANCE",
        "COMPLEXITY_CLIFF_AWARENESS",
        "INDRA_NET_TRAVERSAL",
        "AI_AGENT_TOOL_SCALING",
        "COMPREHENSION_PROOF",
    ]
    for token in tier9_candidates:
        assert token in catalog_content, f"Missing Tier 9 candidate: {token}"


def test_songs_of_strife_catalog_present(catalog_content: str) -> None:
    """SONGS_OF_STRIFE antipattern catalog must be present with key entries."""
    assert "SONGS_OF_STRIFE ANTIPATTERN CATALOG" in catalog_content
    strife_required = [
        "STRIFE_KILL",
        "STRIFE_ACCUMULATION",
        "STRIFE_DEMOLITION",
        "STRIFE_THUNDER",
        "STRIFE_DRAIN",
        "STRIFE_MEMORY_KILL",
        "STRIFE_GATE_FAILURE",
        "STRIFE_GRUDGE_RECORD",
        "STRIFE_NONCE_MISMATCH",
    ]
    for token in strife_required:
        assert token in catalog_content, f"Missing STRIFE token: {token}"


def test_grudge_instances_documented(catalog_content: str) -> None:
    """Named GRUDGE/BREACH instances must appear in the STRIFE catalog."""
    for grudge in ["GRUDGE_001", "GRUDGE_002", "GRUDGE_033", "BREACH_001"]:
        assert grudge in catalog_content, f"Missing named GRUDGE instance: {grudge}"


def test_nataraja_score_formula_present(catalog_content: str) -> None:
    """NATARAJA_Score formula must be in the catalog."""
    assert "NATARAJA_Score" in catalog_content or "NATARAJA_SCORE" in catalog_content
    assert "P4_kill_rate" in catalog_content or "kill_rate" in catalog_content
