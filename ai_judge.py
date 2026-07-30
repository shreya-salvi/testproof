# ai_judge.py
# LAYER 3 of TestProof: the AI Test Reviewer.
# Reads each test and judges whether its check is STRONG or WEAK,
# using Google's Gemini API (free tier).
#
# Includes retry-with-backoff so temporary rate limits (HTTP 429)
# don't crash the run - a real production habit.

import ast
import json
import os
import time
import urllib.request
import urllib.error

MODEL = "gemini-3.5-flash"
API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent"
)
API_KEY = os.environ.get("GEMINI_API_KEY", "")


def get_test_sources(test_file):
    with open(test_file) as f:
        source = f.read()
    tree = ast.parse(source)
    tests = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
            tests[node.name] = ast.get_source_segment(source, node)
    return tests


def call_llm(prompt, max_retries=4):
    if not API_KEY:
        raise RuntimeError("No API key found. Set GEMINI_API_KEY first.")

    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"},
    }).encode()

    for attempt in range(max_retries):
        req = urllib.request.Request(
            API_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": API_KEY,
            },
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
            return data["candidates"][0]["content"]["parts"][0]["text"]

        except urllib.error.HTTPError as e:
            detail = e.read().decode()          # the REAL reason from Google
            if e.code == 429 and attempt < max_retries - 1:
                wait = 20 * (attempt + 1)        # 20s, 40s, 60s...
                print(f"    rate limited (429). waiting {wait}s and retrying...")
                time.sleep(wait)
                continue
            # not retryable, or out of retries: show the real message
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
    result = json.loads(reply)
    return result["verdict"], result["reason"]


def run_ai_review(test_file, llm=call_llm):
    tests = get_test_sources(test_file)
    results = {}
    for name, code in tests.items():
        results[name] = judge_test(code, llm)
        time.sleep(4)        # small gap between tests to stay under rate limits
    return results


def main():
    import yaml
    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)

    print("\n=== TestProof - Layer 3: AI Test Reviewer ===")
    print(f"Model: {MODEL} (via Gemini API)\n")

    results = run_ai_review(cfg["test_file"])

    for name, (verdict, reason) in results.items():
        mark = "STRONG" if verdict == "STRONG" else "WEAK  "
        print(f"  [{mark}] {name}  ->  {reason}")
    print()


if __name__ == "__main__":
    main()