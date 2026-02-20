"""
Test: SONGS_OF_STRIFE_AND_SPLENDOR Archetype Registry in 3_hyper_fractal_obsidian

PREY8 Session: be38d62bad090ee6
SBE Tier 1 — Invariant Scenario: Exactly 1 document in HFO meta-layer resources.
SBE Tier 2 — Happy Path: YAML frontmatter parses correctly with all required fields.

Run:
    cd c:\\hfoDev
    python -m pytest hfo_gen_89_hot_obsidian_forge/0_bronze/resources/test_songs_archetype_registry.py -v
"""

import os
import re
import sys
import yaml
import pathlib
import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HFO_ROOT = pathlib.Path(__file__).resolve().parents[3]  # hfoDev/
HFO_META_RESOURCES = (
    HFO_ROOT
    / "hfo_gen_89_hot_obsidian_forge"
    / "3_hyper_fractal_obsidian"
    / "resources"
)
REGISTRY_FILENAME = "SONGS_OF_STRIFE_AND_SPLENDOR_ARCHETYPE_REGISTRY_V1.md"
REGISTRY_PATH = HFO_META_RESOURCES / REGISTRY_FILENAME


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_yaml_frontmatter(filepath: pathlib.Path) -> dict:
    """Extract and parse YAML frontmatter from a Markdown file with --- delimiters."""
    text = filepath.read_text(encoding="utf-8")
    # Match content between first --- and second ---
    match = re.match(r"^---\n(.*?\n)---", text, re.DOTALL)
    assert match, f"No YAML frontmatter found in {filepath.name}"
    return yaml.safe_load(match.group(1))


# ===========================================================================
# TIER 1 — INVARIANT SCENARIOS (fail-closed safety)
# ===========================================================================

class TestHFOLayerInvariant:
    """Exactly 1 real document must exist in 3_hyper_fractal_obsidian/resources."""

    def test_hfo_resources_directory_exists(self):
        """Given the forge layout, the HFO resources dir must exist."""
        assert HFO_META_RESOURCES.is_dir(), (
            f"Directory missing: {HFO_META_RESOURCES}"
        )

    def test_exactly_one_document_in_hfo_resources(self):
        """Given .gitkeep is the only prior file, there must be exactly 1 real document."""
        real_files = [
            f for f in HFO_META_RESOURCES.iterdir()
            if f.is_file() and f.name != ".gitkeep"
        ]
        assert len(real_files) == 1, (
            f"Expected exactly 1 document in HFO resources (excluding .gitkeep), "
            f"found {len(real_files)}: {[f.name for f in real_files]}"
        )

    def test_document_is_the_archetype_registry(self):
        """The 1 document must be the SONGS archetype registry."""
        assert REGISTRY_PATH.exists(), (
            f"Expected {REGISTRY_FILENAME} at {REGISTRY_PATH}"
        )

    def test_document_is_not_empty(self):
        """The document must have substantial content (not a stub)."""
        size = REGISTRY_PATH.stat().st_size
        assert size > 5000, (
            f"Document too small ({size} bytes) — expected a chunky reference document"
        )


# ===========================================================================
# TIER 2 — HAPPY PATH SCENARIOS (core desired behavior)
# ===========================================================================

class TestYAMLFrontmatter:
    """YAML frontmatter must parse and contain all required fields."""

    @pytest.fixture(scope="class")
    def frontmatter(self) -> dict:
        return _parse_yaml_frontmatter(REGISTRY_PATH)

    def test_schema_id(self, frontmatter):
        assert "schema_id" in frontmatter
        assert "hyper_fractal_obsidian" in frontmatter["schema_id"]

    def test_required_top_level_fields(self, frontmatter):
        required = [
            "schema_id", "medallion_layer", "hive", "doc_id", "title",
            "version", "date", "author", "layer", "port", "commander",
            "domain", "status", "bluf",
        ]
        for field in required:
            assert field in frontmatter, f"Missing required field: {field}"

    def test_layer_is_hyper_fractal(self, frontmatter):
        assert frontmatter["layer"] == "3_hyper_fractal_obsidian"

    def test_port_is_p4(self, frontmatter):
        assert frontmatter["port"] == "P4"

    def test_status_is_living(self, frontmatter):
        assert frontmatter["status"] == "LIVING"


class TestSourceDocuments:
    """Source document cross-references must be present and complete."""

    @pytest.fixture(scope="class")
    def frontmatter(self) -> dict:
        return _parse_yaml_frontmatter(REGISTRY_PATH)

    def test_source_documents_present(self, frontmatter):
        assert "source_documents" in frontmatter
        assert isinstance(frontmatter["source_documents"], list)

    def test_minimum_source_count(self, frontmatter):
        docs = frontmatter["source_documents"]
        assert len(docs) >= 10, (
            f"Expected at least 10 source documents, found {len(docs)}"
        )

    def test_key_documents_referenced(self, frontmatter):
        """Critical SSOT docs must be in the source list."""
        doc_ids = {d["id"] for d in frontmatter["source_documents"]}
        required_ids = {267, 270, 272, 273, 84}  # core ontology docs
        missing = required_ids - doc_ids
        assert not missing, f"Missing critical source docs: {missing}"


class TestOntologicalLadder:
    """The 5-layer ontological ladder must be present."""

    @pytest.fixture(scope="class")
    def frontmatter(self) -> dict:
        return _parse_yaml_frontmatter(REGISTRY_PATH)

    def test_ladder_present(self, frontmatter):
        assert "ontological_ladder" in frontmatter

    def test_five_layers(self, frontmatter):
        ladder = frontmatter["ontological_ladder"]
        required_layers = ["concept", "archetype", "name", "port", "agent"]
        for layer in required_layers:
            assert layer in ladder, f"Missing ontological layer: {layer}"


class TestSongsAliases:
    """Both songs must have complete alias tables."""

    @pytest.fixture(scope="class")
    def frontmatter(self) -> dict:
        return _parse_yaml_frontmatter(REGISTRY_PATH)

    @pytest.fixture(scope="class")
    def songs(self, frontmatter) -> dict:
        assert "songs" in frontmatter
        return frontmatter["songs"]

    def test_strife_song_present(self, songs):
        assert "songs_of_strife" in songs

    def test_splendor_song_present(self, songs):
        assert "songs_of_splendor" in songs

    def test_strife_aliases_minimum(self, songs):
        aliases = songs["songs_of_strife"].get("aliases", [])
        assert len(aliases) >= 5, (
            f"Expected at least 5 STRIFE aliases, found {len(aliases)}"
        )

    def test_splendor_aliases_minimum(self, songs):
        aliases = songs["songs_of_splendor"].get("aliases", [])
        assert len(aliases) >= 4, (
            f"Expected at least 4 SPLENDOR aliases, found {len(aliases)}"
        )

    def test_strife_canonical_names(self, songs):
        """Key canonical aliases must be present in STRIFE."""
        alias_names = {a["canonical"] for a in songs["songs_of_strife"]["aliases"]}
        required = {"FESTERING_ANGER_TOKENS", "SONGS_OF_STRIFE_TOKENS", "SONGS_OF_STRIFE"}
        missing = required - alias_names
        assert not missing, f"Missing STRIFE aliases: {missing}"

    def test_splendor_canonical_names(self, songs):
        """Key canonical aliases must be present in SPLENDOR."""
        alias_names = {a["canonical"] for a in songs["songs_of_splendor"]["aliases"]}
        required = {"SONGS_OF_SPLENDOR", "SONGS_OF_SPLENDOR_TOKENS", "SPLENDOR_TOKEN"}
        missing = required - alias_names
        assert not missing, f"Missing SPLENDOR aliases: {missing}"

    def test_strife_has_spells(self, songs):
        spells = songs["songs_of_strife"].get("spells", [])
        assert len(spells) >= 5, f"Expected at least 5 spells, found {len(spells)}"

    def test_splendor_has_buffs(self, songs):
        buffs = songs["songs_of_splendor"].get("buffs", [])
        assert len(buffs) >= 3, f"Expected at least 3 buffs, found {len(buffs)}"

    def test_strife_etymology(self, songs):
        etym = songs["songs_of_strife"].get("etymology", {})
        assert "SONGS" in etym
        assert "STRIFE" in etym

    def test_splendor_etymology(self, songs):
        etym = songs["songs_of_splendor"].get("etymology", {})
        assert "SONGS" in etym
        assert "SPLENDOR" in etym


class TestDualTokenSystem:
    """Dual token invariants must be specified."""

    @pytest.fixture(scope="class")
    def frontmatter(self) -> dict:
        return _parse_yaml_frontmatter(REGISTRY_PATH)

    def test_invariants_present(self, frontmatter):
        assert "dual_token_invariants" in frontmatter

    def test_formula(self, frontmatter):
        inv = frontmatter["dual_token_invariants"]
        assert "total_formula" in inv
        assert "STRIFE" in inv["total_formula"] and "SPLENDOR" in inv["total_formula"]

    def test_always_positive(self, frontmatter):
        inv = frontmatter["dual_token_invariants"]
        assert inv.get("strife_always_positive") is True
        assert inv.get("splendor_always_positive") is True

    def test_core_thesis(self, frontmatter):
        inv = frontmatter["dual_token_invariants"]
        assert "core_thesis" in inv
        assert "nihilism" in inv["core_thesis"].lower() or "delusion" in inv["core_thesis"].lower()


class TestNatarajaDyad:
    """NATARAJA P4+P5 dyad structure must be documented."""

    @pytest.fixture(scope="class")
    def frontmatter(self) -> dict:
        return _parse_yaml_frontmatter(REGISTRY_PATH)

    def test_nataraja_present(self, frontmatter):
        assert "nataraja" in frontmatter

    def test_formula(self, frontmatter):
        nat = frontmatter["nataraja"]
        assert "formula" in nat
        assert "P4_kill_rate" in nat["formula"]
        assert "P5_rebirth_rate" in nat["formula"]

    def test_apex_designation(self, frontmatter):
        nat = frontmatter["nataraja"]
        assert "apex_designation" in nat
        assert nat["apex_designation"] == "DIVINE_ADJACENT_HYPER_SLIVER_APEX"


class TestAlliterationLattice:
    """All 8 commanders must be in the alliteration lattice."""

    @pytest.fixture(scope="class")
    def frontmatter(self) -> dict:
        return _parse_yaml_frontmatter(REGISTRY_PATH)

    def test_lattice_present(self, frontmatter):
        assert "alliteration_lattice" in frontmatter

    def test_all_eight_ports(self, frontmatter):
        commanders = frontmatter["alliteration_lattice"].get("commanders", {})
        expected_ports = {"P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7"}
        actual_ports = set(commanders.keys())
        assert actual_ports == expected_ports, (
            f"Missing ports: {expected_ports - actual_ports}"
        )

    def test_p4_is_singer(self, frontmatter):
        p4 = frontmatter["alliteration_lattice"]["commanders"]["P4"]
        assert "SINGER" in p4["title"]
        assert "STRIFE" in p4["title"]
        assert "SPLENDOR" in p4["title"]


class TestKeywordIndex:
    """Machine-searchable keyword index must be comprehensive."""

    @pytest.fixture(scope="class")
    def frontmatter(self) -> dict:
        return _parse_yaml_frontmatter(REGISTRY_PATH)

    def test_keywords_present(self, frontmatter):
        assert "keywords" in frontmatter
        assert isinstance(frontmatter["keywords"], list)

    def test_minimum_keyword_count(self, frontmatter):
        kw = frontmatter["keywords"]
        assert len(kw) >= 40, (
            f"Expected at least 40 keywords for comprehensive indexing, found {len(kw)}"
        )

    def test_critical_keywords(self, frontmatter):
        kw_set = set(frontmatter["keywords"])
        critical = {
            "SONGS_OF_STRIFE", "SONGS_OF_SPLENDOR",
            "FESTERING_ANGER_TOKENS", "NATARAJA",
            "SINGER_OF_STRIFE_AND_SPLENDOR",
            "RED_REGNANT", "PYRE_PRAETORIAN",
            "BORN_OF_THE_THREE_THUNDERS",
            "WAIL_OF_THE_BANSHEE",
            "DUAL_TOKEN_SYSTEM",
        }
        missing = critical - kw_set
        assert not missing, f"Missing critical keywords: {missing}"


# ===========================================================================
# TIER 3 — MARKDOWN BODY STRUCTURE
# ===========================================================================

class TestMarkdownBody:
    """The markdown body must have the expected section structure."""

    @pytest.fixture(scope="class")
    def body(self) -> str:
        text = REGISTRY_PATH.read_text(encoding="utf-8")
        # Get everything after the second ---
        parts = text.split("---", 2)
        assert len(parts) >= 3, "Document must have YAML frontmatter + markdown body"
        return parts[2]

    def test_has_purpose_section(self, body):
        assert "## I. Purpose" in body

    def test_has_ontological_ladder_section(self, body):
        assert "## II. The Ontological Ladder" in body

    def test_has_two_songs_section(self, body):
        assert "## III. The Two Songs" in body

    def test_has_nataraja_section(self, body):
        assert "## IV. The NATARAJA Dyad" in body

    def test_has_etymology_section(self, body):
        assert "## V. Etymological Decompositions" in body

    def test_has_alliteration_section(self, body):
        assert "## VI. The Alliteration Lattice" in body

    def test_has_class_stack_section(self, body):
        assert "## VII. Race & Class Stack" in body

    def test_has_token_inventory_section(self, body):
        assert "## VIII. Token Tier Inventory" in body

    def test_has_crossref_section(self, body):
        assert "## IX. Cross-Reference Map" in body

    def test_strife_aliases_in_body(self, body):
        assert "FESTERING_ANGER_TOKENS" in body
        assert "RAGE_ACCUMULATOR" in body
        assert "DISEASE_HOST_LEDGER" in body

    def test_splendor_aliases_in_body(self, body):
        assert "INSPIRE_COURAGE_LEDGER" in body
        assert "PATTERN_ACCUMULATOR" in body

    def test_inseparability_thesis(self, body):
        assert "Strife without Splendor is nihilism" in body
        assert "Splendor without Strife is delusion" in body
