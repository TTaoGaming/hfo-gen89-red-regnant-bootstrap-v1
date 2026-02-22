import os

def test_omega_v15_self_reflection_exists():
    file_path = "hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/omega_v15_self_reflection.md"
    assert os.path.exists(file_path), f"File {file_path} does not exist"

def test_omega_v15_self_reflection_content():
    file_path = "hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/omega_v15_self_reflection.md"
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Omega v15" in content
    assert "SONGS_OF_STRIFE_AND_SPLENDOR" in content
    assert "Antifragile Cognitive Swarm" in content
    assert "Fail-Closed Architecture" in content
