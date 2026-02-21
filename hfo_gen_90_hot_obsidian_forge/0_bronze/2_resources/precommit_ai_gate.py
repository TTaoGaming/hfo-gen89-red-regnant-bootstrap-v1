import sys
import os
import json
import urllib.request
import urllib.error

def check_commit_message(msg_file):
    try:
        with open(msg_file, 'r', encoding='utf-8') as f:
            msg = f.read().strip()
    except Exception as e:
        print(f"Error reading commit message: {e}")
        return 0 # Fail open

    # Ignore merge commits or empty messages
    if not msg or msg.startswith("Merge branch") or msg.startswith("Merge pull request"):
        return 0

    # Basic heuristic
    words = msg.split()
    if len(words) < 3:
        print(f"❌ AI GATE: Commit message '{msg}' is too short. Explain WHAT and WHY.")
        return 1

    # Try Ollama first (local, fast, free)
    try:
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": "llama3.2", # or whatever small model is common, e.g., qwen2.5:0.5b, phi3
            "prompt": f"Analyze this git commit message for 'slop' (low effort, meaningless filler like 'update', 'fix', 'wip', 'test'). Reply ONLY with 'VALID' if it contains actual semantic meaning explaining what was changed, or 'SLOP' if it is low-effort filler.\n\nCommit message: {msg}",
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 5
            }
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=2) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            reply = res_data.get("response", "").strip()
            if "SLOP" in reply.upper():
                print(f"❌ AI GATE (Ollama): Commit message '{msg}' was classified as SLOP. Please write a meaningful commit message.")
                return 1
            else:
                print(f"✓ AI GATE (Ollama): Commit message accepted.")
                return 0
    except Exception as e:
        # Ollama not running or model missing, fallback to Gemini if available
        pass

    # Fallback to Gemini
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Try to read from .env
        try:
            with open(".env", "r") as f:
                for line in f:
                    if line.startswith("GEMINI_API_KEY="):
                        api_key = line.strip().split("=", 1)[1].strip('"\'')
                        break
        except Exception:
            pass

    if api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{
                    "parts": [{"text": f"Analyze this git commit message for 'slop' (low effort, meaningless filler like 'update', 'fix', 'wip', 'test', 'asdf'). Reply ONLY with 'VALID' if it contains actual semantic meaning explaining what was changed, or 'SLOP' if it is low-effort filler.\n\nCommit message: {msg}"}]
                }],
                "generationConfig": {
                    "temperature": 0.0,
                    "maxOutputTokens": 5
                }
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=3) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                reply = res_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                if "SLOP" in reply.upper():
                    print(f"❌ AI GATE (Gemini): Commit message '{msg}' was classified as SLOP. Please write a meaningful commit message.")
                    return 1
                elif "VALID" in reply.upper():
                    print(f"✓ AI GATE (Gemini): Commit message accepted.")
                    return 0
                else:
                    print(f"⚠ AI GATE (Gemini): Unexpected response '{reply}'. Failing open.")
                    return 0
        except Exception as e:
            print(f"⚠ AI GATE (Gemini): Failed to connect ({e}). Failing open.")
            pass # Fail open
    else:
        print("⚠ AI GATE: No local Ollama and no GEMINI_API_KEY found. Failing open.")

    return 0

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(check_commit_message(sys.argv[1]))
    sys.exit(0)
