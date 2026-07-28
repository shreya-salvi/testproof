# mutator.py
# LAYER 2 of TestProof: the Mutation Agent.
# Secretly breaks the app, re-runs tests, sees who notices.
#   - real test FAILS  -> caught the bug  -> OK
#   - fake test PASSES -> missed the bug  -> FAKE

import ast
import shutil
import subprocess
import sys


def make_mutant(source):
    """Swap the first '+' operator for '-' to create a broken version."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            node.op = ast.Sub()
            break
    return ast.unparse(tree)


def list_tests(source):
    """Find every function named test_*"""
    tree = ast.parse(source)
    return [
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test")
    ]


def run_one_test(test_file, test_name):
    """Run a single test. Return True if PASSED, False if FAILED."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", f"{test_file}::{test_name}", "-q"],
        capture_output=True, text=True
    )
    return result.returncode == 0


def run_mutation_check(app_file, test_file):
    """Break the app, run each test, restore the app. Returns {name: (verdict, reason)}."""
    with open(app_file) as f:
        original_app = f.read()
    with open(test_file) as f:
        test_source = f.read()

    tests = list_tests(test_source)
    results = {}
    backup = app_file + ".backup"

    shutil.copy(app_file, backup)
    mutant = make_mutant(original_app)
    with open(app_file, "w") as f:
        f.write(mutant)

    try:
        for name in tests:
            passed = run_one_test(test_file, name)
            if passed:
                results[name] = ("FAKE", "stayed green while app was broken")
            else:
                results[name] = ("OK", "caught the bug (failed as it should)")
    finally:
        shutil.move(backup, app_file)

    return results


def main():
    # when run directly, read settings from config.yaml
    import yaml
    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)

    print("\n=== TestProof - Layer 2: Mutation Agent ===")
    print("Secretly breaking the app (changing +  to  -)...\n")

    results = run_mutation_check(cfg["app_file"], cfg["test_file"])

    fake_count = 0
    for name, (verdict, reason) in results.items():
        mark = "OK  " if verdict == "OK" else "FAKE"
        print(f"  [{mark}] {name}  ->  {reason}")
        if verdict == "FAKE":
            fake_count += 1

    print(f"\n  {len(results)} tests checked. {fake_count} exposed as fake by mutation.\n")


if __name__ == "__main__":
    main()