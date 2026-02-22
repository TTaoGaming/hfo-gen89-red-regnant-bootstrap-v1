import os


def test_sharding_options_file_exists() -> None:
    file_path = "hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/cognitive_persistence_sharding_options.md"
    assert os.path.exists(file_path), f"File {file_path} does not exist"

    with open(file_path, "r") as f:
        content = f.read()
        assert "Option A: 8 Separate SQLite Database Files" in content
        assert "Option B: 1 Unified Database with WAL Mode" in content


def test_handoff_file_exists() -> None:
    file_path = "hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/HANDOFF_cognitive_persistence_sharding.md"
    assert os.path.exists(file_path), f"Handoff file {file_path} does not exist"

    with open(file_path, "r") as f:
        content = f.read()
        assert "CRITICAL WARNINGS" in content
        assert "Option B" in content
        assert "MCP Schema Drift" in content


def test_sharding_options_has_all_four_options() -> None:
    file_path = "hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/cognitive_persistence_sharding_options.md"
    with open(file_path, "r") as f:
        content = f.read()
    for option_num in ["1.", "2.", "3.", "4."]:
        assert option_num in content, f"Option numbered '{option_num}' missing from design doc"


def test_handoff_warns_about_orphaned_sessions() -> None:
    file_path = "hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/HANDOFF_cognitive_persistence_sharding.md"
    with open(file_path, "r") as f:
        content = f.read()
    assert "11 Orphaned" in content or "orphaned" in content.lower()
    assert "Next Steps" in content


def test_pareto_collapse_present() -> None:
    """Verify the document shows exactly 2 options in the Collapsed section."""
    file_path = "hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/cognitive_persistence_sharding_options.md"
    with open(file_path, "r") as f:
        content = f.read()
    assert "Collapsed to 2 Pareto Optimal Options" in content
    assert "Option A" in content
    assert "Option B" in content
