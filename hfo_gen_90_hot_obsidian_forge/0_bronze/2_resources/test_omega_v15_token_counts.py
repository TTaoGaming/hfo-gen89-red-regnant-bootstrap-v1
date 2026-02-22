import os

def test_omega_v15_rewrite_brief_token_count():
    file_path = "hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/OMEGA_V15_REWRITE_BRIEF.md"
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "5 billion tokens consumed" in content
    assert "1.5B proven on OpenRouter" in content
    assert "cursed ralph wiggums loops" in content

def test_omega_v15_state_of_union_token_count():
    file_path = "hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/omega_v15_context_bundle_state_of_union.md"
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "5 billion tokens consumed" in content
    assert "1.5B proven on OpenRouter" in content
    assert "cursed ralph wiggums loops" in content
