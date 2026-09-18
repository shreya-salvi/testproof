"""
test_generator.py  -  Layer 4 of TestProof: the Test Generator.

The other layers DETECT weak tests. This one FIXES the gap: when a test is
fake/weak or a mutation survives, it asks an LLM to write a targeted test for
the missing behavior -- then it does NOT trust the LLM. It VALIDATES the
generated test deterministically:

    1. the test must PASS on the correct code   (it's a valid test), and
    2. the test must FAIL when the code is mutated (it actually catches the bug).

Only a test that clears BOTH checks is 'VALIDATED'. Anything uncertain --
the LLM returns junk, or the test passes clean but doesn't catch the mutation --
is marked 'NEEDS_REVIEW' and handed to a human. The AI proposes; the mutation
check decides.

Reuses ai_judge.call_llm (the Gemini wrapper) when available; falls back to a
built-in stub so the pipeline still runs offline / without a key.
"""

from __future__ import annotations

import ast

import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass

# ---- LLM hook: reuse the project's Gemini wrapper if present -------------
try:
    from ai_judge import call_llm as _project_call_llm   # their Layer 3 wrapper
except Exception:
    _project_call_llm = None


@dataclass
class GenResult:
    target: str            # the test / behavior we generated for
    status: str            # VALIDATED | NEEDS_REVIEW | FAILED
    generated_code: str
    reason: str
    passed_clean: bool | None = None
    caught_mutation: bool | None = None


# --------------------------------------------------------------------------- #
#  Generation
# --------------------------------------------------------------------------- #
_PROMPT = """You are a senior test engineer. Write ONE simple pytest test.

STRICT rules:
- Use ONLY the example and expected value given below. Do NOT invent extra
  cases and do NOT compute any new expected numbers yourself.
- Exactly ONE assert statement. Do NOT use @pytest.mark.parametrize.
- import the function under test from the module `{module}`.
- assert the EXACT expected value shown (never a type or not-None check).
- name the function starting with `test_`.

Module under test ({module}.py):
{app_code}

The behavior to lock in (use this exact example and value):
{gap}

Reply ONLY as JSON: {{"code": "<the full python test as a single string>"}}.
Put the whole test (imports + one function with one assert) in the code field.
No prose."""


def _fallback_generate(app_code: str, module: str, gap: str) -> str:
    """Deterministic stand-in when no LLM is configured.

    It reads a documented example from the gap description of the form
    `final_price(100, 20, 10) == 88.0` and builds a strong equality test, so the
    validation loop is demonstrable end-to-end with no API key.
    """
    # accept: func(args) == N   |  ... should equal N  |  equals N
    #         ... should be N | returns N | -> N | = N
    m = re.search(
        r"([a-zA-Z_]\w*)\(([^)]*)\)\s*"
        r"(?:==|=|->|should\s+equal|equals?|should\s+be|returns?|is)\s*"
        r"([-\d.]+)",
        gap, re.IGNORECASE)
    if not m:
        return ""
    func, args, expected = m.group(1), m.group(2), m.group(3)
    return (f"from {module} import {func}\n\n"
            f"def test_{func}_exact_value():\n"
            f"    assert {func}({args}) == {expected}\n")


def generate_test(app_code: str, module: str, gap: str) -> str:
    prompt = _PROMPT.format(module=module, app_code=app_code, gap=gap)
    if _project_call_llm is not None:
        try:
            raw = _project_call_llm(prompt)
            code = _extract_code(raw)
            if code.strip():
                return code
        except Exception:
            pass
    return _fallback_generate(app_code, module, gap)


def _extract_code(raw: str) -> str:
    """The project's call_llm asks Gemini for JSON, so a reply is usually
    {"code": "..."} (sometimes under another key, sometimes fenced). Pull the
    Python out of whatever shape comes back."""
    import json
    text = raw.strip()
    # try to parse the whole thing, or the first {...} block, as JSON
    candidate = text
    if not candidate.startswith("{"):
        i, j = text.find("{"), text.rfind("}")
        if i != -1 and j != -1 and j > i:
            candidate = text[i:j + 1]
    try:
        data = json.loads(candidate)
        if isinstance(data, dict):
            for key in ("code", "test", "test_code", "python", "content"):
                if isinstance(data.get(key), str) and data[key].strip():
                    return _strip_fences(data[key])
            # single string value under any key
            for v in data.values():
                if isinstance(v, str) and "def test" in v:
                    return _strip_fences(v)
    except Exception:
        pass
    return _strip_fences(text)


def _strip_fences(text: str) -> str:
    return text.replace("```python", "").replace("```", "").strip()


# --------------------------------------------------------------------------- #
#  Validation  --  the part that makes this trustworthy
# --------------------------------------------------------------------------- #
# Arithmetic-operator swaps. We generate several candidate mutants and keep only
# the ones that STILL COMPILE -- a syntax-error mutant would make every test
# "fail" on it and produce false validations, so those are discarded.
_MUTATIONS = [("+", "-"), ("-", "+"), ("*", "/"), ("/", "*"), ("**", "*")]


def _run_test_inproc(app_src, module, test_src, test_name):
    """Run one test against app_src in memory (no subprocess). True = passed."""
    import sys, types
    saved = sys.modules.get(module)
    try:
        mod = types.ModuleType(module)
        exec(compile(app_src, f"<{module}>", "exec"), mod.__dict__)
        sys.modules[module] = mod
        g = {}
        exec(compile(test_src, "<test>", "exec"), g)
        fn = g.get(test_name)
        if fn is None:
            return False
        fn()
        return True
    except Exception:
        return False
    finally:
        if saved is not None:
            sys.modules[module] = saved
        else:
            sys.modules.pop(module, None)


def _make_mutants(app_code: str) -> list[str]:
    """Return every compilable single-operator mutant of app_code.

    We only swap an arithmetic operator that has a space on BOTH sides (the
    normal way these appear in code), so we never touch an identifier, an
    indent, a unary sign, or a newline. Every candidate must still compile,
    or it is dropped -- a syntax-error mutant would make any test look like it
    "caught" the bug and cause false validations.
    """
    mutants = []
    for old, new in _MUTATIONS:
        token = f" {old} "
        repl = f" {new} "
        idx = app_code.find(token)
        while idx != -1:
            candidate = app_code[:idx] + repl + app_code[idx + len(token):]
            if candidate != app_code:
                try:
                    compile(candidate, "<mutant>", "exec")
                    mutants.append(candidate)
                except SyntaxError:
                    pass
            idx = app_code.find(token, idx + 1)
    seen, out = set(), []
    for m in mutants:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def validate_test(app_code: str, module: str, test_code: str) -> tuple[bool, bool]:
    """Return (passed_clean, caught_mutation), all in-process."""
    if not test_code.strip():
        return (False, False)
    try:
        names = [n.name for n in ast.walk(ast.parse(test_code))
                 if isinstance(n, ast.FunctionDef) and n.name.startswith("test")]
    except SyntaxError:
        return (False, False)
    if not names:
        return (False, False)
    tname = names[0]
    passed_clean = _run_test_inproc(app_code, module, test_code, tname)
    if not passed_clean:
        return (False, False)
    mutants = _make_mutants(app_code)
    if not mutants:
        return (True, False)
    caught = any(not _run_test_inproc(m, module, test_code, tname) for m in mutants)
    return (True, caught)


def generate_and_validate(app_code: str, module: str, gap: str,
                          target: str = "") -> GenResult:
    code = generate_test(app_code, module, gap)
    if not code.strip():
        return GenResult(target, "FAILED", code,
                         "The model returned no usable test.", None, None)

    passed_clean, caught = validate_test(app_code, module, code)

    if passed_clean and caught:
        status, reason = "VALIDATED", (
            "Generated test passes on the correct code AND fails when the code "
            "is mutated -- it genuinely catches the bug.")
    elif passed_clean and not caught:
        status, reason = "NEEDS_REVIEW", (
            "Test passes on correct code but did not catch the injected bug. "
            "Flagged for a human -- the AI's suggestion isn't trusted yet.")
    else:
        status, reason = "NEEDS_REVIEW", (
            "The generated test did not pass against the function as written -- "
            "either the function has a bug or the expected value is off. Sent for "
            "human review; the AI never has the final say.")

    return GenResult(target, status, code, reason, passed_clean, caught)


if __name__ == "__main__":
    # quick self-demo
    app = open("pricing.py").read()
    res = generate_and_validate(
        app, "pricing",
        gap="final_price applies discount then tax: final_price(100, 20, 10) == 88.0",
        target="test_price_smoke (weak)")
    print("STATUS:", res.status)
    print("passed_clean:", res.passed_clean, "| caught_mutation:", res.caught_mutation)
    print("REASON:", res.reason)
    print("--- generated test ---")
    print(res.generated_code)