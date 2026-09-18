"""Layer 3 — AI test reviewer (Google Gemini).

Judges whether a test's assertion is STRONG or WEAK. Fails fast on rate limits
so the app never freezes: at most a couple of short retries, then it gives up
gracefully and the caller falls back to a static check.
"""

import ast
import json
import os
import time
import urllib.request
import urllib.error

MODEL = "gemini-3.5-flash"
API_URL = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{MODEL}:generateContent")
API_KEY = os.environ.get("GEMINI_API_KEY", "")


def get_test_sources(test_file):
    src = open(test_file, encoding="utf-8").read()
    tree = ast.parse(src)
    return {n.name: ast.get_source_segment(src, n)
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test")}


def call_llm(prompt, max_retries=2):
    if not API_KEY:
        raise RuntimeError("No API key found. Set GEMINI_API_KEY first.")
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"},
    }).encode()
    for attempt in range(max_retries):
        req = urllib.request.Request(
            API_URL, data=body,
            headers={"Content-Type": "application/json", "x-goog-api-key": API_KEY})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            detail = e.read().decode()
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(2)          # short, fail-fast backoff
                continue
            raise RuntimeError(f"HTTP {e.code}: {detail}") from None


def judge_test(test_code, llm=call_llm):
    prompt = f"""You are a test quality reviewer. Look at this Python test and decide
if its check is STRONG (it verifies the actual expected value) or WEAK
(it only checks the type, or that the result is not None, or something
trivial that a wrong answer could still pass).

Test:
{test_code}

Reply ONLY as JSON: {{"verdict": "STRONG" or "WEAK", "reason": "short reason"}}"""
    reply = llm(prompt)
    result = json.loads(reply.replace("```json", "").replace("```", "").strip())
    return result["verdict"], result["reason"]


if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load(open("config.yaml"))
    for name, code in get_test_sources(cfg["test_file"]).items():
        try:
            v, r = judge_test(code)
        except Exception as e:
            v, r = "?", str(e)
        print(f"  [{v:6}] {name} -> {r}")