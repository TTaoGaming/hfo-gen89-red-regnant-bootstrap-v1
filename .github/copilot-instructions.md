# HFO Gen 90 - Agent Structural Enforcement

## STRICT ROOT CLEANLINESS RULE

**NEVER** create, move, or copy files into the workspace root directory (\"C:\hfoDev\" or \"\").

If you need to create a script, scratchpad, or document, you **MUST** place it in the appropriate PARA folder inside the forge:
- \"hfo_gen_90_hot_obsidian_forge/0_bronze/2_resources/\" (for scripts, tools, scratchpads)
- \"hfo_gen_90_hot_obsidian_forge/0_bronze/1_areas/\" (for domain knowledge)
- \"hfo_gen_90_hot_obsidian_forge/0_bronze/0_archives/\" (for old data)

If the user asks you to create a file and does not specify a path, **default to the bronze resources folder**. Do not ask for permission, just put it there.

If you attempt to write to the root directory, you are violating the Medallion Architecture and the pre-commit hook will fail.
