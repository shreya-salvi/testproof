# scanner.py
# LAYER 1 of TestProof: the cheap Static Scanner.
#
# What it does: reads a test file WITHOUT running it, and checks each
# test function for a real check (an "assert"). A test with no assert
# checks nothing - it's an obvious fake. We catch it here, for free.
#
# How it "reads" code: Python can turn code into an AST
# (Abstract Syntax Tree) - a structured map of the code's parts.
# We walk that map and look for assert statements.

import ast
import sys


def find_test_functions(tree):
    """Return every function whose name starts with 'test'."""
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test")
    ]


def has_assertion(func_node):
    """Return True if this function contains at least one 'assert'."""
    for node in ast.walk(func_node):
        if isinstance(node, ast.Assert):
            return True
    return False


def scan_file(path):
    """Scan one test file and return a verdict for each test."""
    with open(path) as f:
        source = f.read()

    tree = ast.parse(source)          # turn the code into an AST map
    tests = find_test_functions(tree) # find all the test functions

    results = []
    for test in tests:
        if has_assertion(test):
            results.append((test.name, "OK", "has a real check"))
        else:
            results.append((test.name, "FAKE", "no assert - checks nothing"))
    return results


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "test_calculator.py"
    results = scan_file(path)

    print("\n=== TestProof - Layer 1: Static Scanner ===")
    print(f"Scanning: {path}\n")

    fake_count = 0
    for name, verdict, reason in results:
        mark = "OK  " if verdict == "OK" else "FAKE"
        print(f"  [{mark}] {name}  ->  {reason}")
        if verdict == "FAKE":
            fake_count += 1

    print(f"\n  {len(results)} tests scanned. {fake_count} flagged as fake.\n")


if __name__ == "__main__":
    main()
