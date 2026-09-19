"""
ci_gate.py  -  TestProof as a CI quality gate.

Runs the deterministic layers (static scan + mutation) on the project's tests,
prints a trust report, and exits non-zero if the trust score is below a
threshold. Graded the same way the app is, including exception tests.

Configure the bar with TESTPROOF_MIN_TRUST (percent, default 50).
"""

import ast
import os
import sys

import yaml

from scanner import scan_file
from mutator import run_mutation_check


def _sources(test_file):
    src = open(test_file, encoding="utf-8").read()
    tree = ast.parse(src)
    return {n.name: (ast.get_source_segment(src, n) or "")
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test")}


def evaluate(app_file, test_file):
    l1 = {n: (v, r) for n, v, r in scan_file(test_file)}
    l2 = run_mutation_check(app_file, test_file)
    srcs = _sources(test_file)
    report = {}
    for name, (v1, r1) in l1.items():
        src = srcs.get(name, "")
        if v1 == "FAKE":
            report[name] = ("FAKE", f"Layer 1: {r1 or 'no assertion'}")
        elif "pytest.raises" in src or ".assertRaises" in src:
            report[name] = ("TRUSTED", "checks the error path")
        else:
            v2, r2 = l2.get(name, ("OK", ""))
            if v2 == "FAKE":
                report[name] = ("FAKE", f"Layer 2: {r2 or 'survived a mutation'}")
            else:
                report[name] = ("TRUSTED", "passed static scan + mutation")
    return report


def main():
    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)
    app_file, test_file = cfg["app_file"], cfg["test_file"]
    min_trust = int(os.environ.get("TESTPROOF_MIN_TRUST", "50"))

    report = evaluate(app_file, test_file)
    total = len(report)
    trusted = sum(1 for v, _ in report.values() if v == "TRUSTED")
    score = round(trusted / total * 100) if total else 0

    print("=" * 55)
    print(f"  TestProof CI gate  -  {test_file}")
    print("=" * 55)
    for name, (verdict, why) in report.items():
        mark = "OK  " if verdict == "TRUSTED" else "FAKE"
        print(f"  [{mark}] {name}")
        if verdict == "FAKE":
            print(f"         -> {why}")
    print("-" * 55)
    print(f"  Trust score: {trusted}/{total} = {score}%  "
          f"(minimum required: {min_trust}%)")
    print("=" * 55)

    if score < min_trust:
        print(f"\nFAIL: trust score {score}% is below the required {min_trust}%.")
        return 1
    print(f"\nPASS: trust score {score}% meets the {min_trust}% bar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())