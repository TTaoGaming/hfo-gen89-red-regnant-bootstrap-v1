import asyncio
import os
from pathlib import Path

def _find_root() -> Path:
    for anchor in [Path.cwd(), Path(__file__).resolve().parent]:
        for candidate in [anchor] + list(anchor.parents):
            if (candidate / "AGENTS.md").exists():
                return candidate
    return Path.cwd()

os.environ["HFO_ROOT"] = str(_find_root())

from hfo_background_daemon import GeminiClient

async def main():
    client = GeminiClient()
    print("Sending test prompt to Gemini...")
    try:
        response = await client.chat("Hello, this is a test. Reply with 'OK'.", model="gemini-2.5-flash")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
