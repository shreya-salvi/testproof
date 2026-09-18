"""Layer 2 — mutation agent, in-process (fast, no subprocesses).

Breaks the app in memory and re-runs each test by calling it directly. A test
that stays green while the code is broken never really checked anything.
"""

import ast
import sys
import types

_MUT = [(" + ", " - "), (" - ", " + "), (" * ", " / "),
        (" / ", " * "), (" ** ", " * ")]


def make_mutants(src):
    outs = []
    for old, new in _MUT:
        i = src.find(old)
        while i != -1:
            cand = src[:i] + new + src[i + len(old):]
            if cand != src:
                try:
                    compile(cand, "<m>", "exec")
                    outs.append(cand)
                except SyntaxError:
                    pass
            i = src.find(old, i + 1)
    seen, res = set(), []
    for m in outs:
        if m not in seen:
            seen.add(m)
            res.append(m)
    return res


def run_test_inproc(app_src, module_name, test_src, test_name):
    """Return True if the named test passes when run against app_src.

    We register a throwaway module (e.g. 'calculator') built from app_src, then
    exec the test file and call the one test function. No files, no subprocess.
    """
    saved = sys.modules.get(module_name)
    try:
        mod = types.ModuleType(module_name)
        exec(compile(app_src, f"<{module_name}>", "exec"), mod.__dict__)
        sys.modules[module_name] = mod
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
            sys.modules[module_name] = saved
        else:
            sys.modules.pop(module_name, None)


def run_mutation_check(app_file, test_file):
    import os
    app_src = open(app_file, encoding="utf-8").read()
    test_src = open(test_file, encoding="utf-8").read()
    module = os.path.splitext(os.path.basename(app_file))[0]
    names = [n.name for n in ast.walk(ast.parse(test_src))
             if isinstance(n, ast.FunctionDef) and n.name.startswith("test")]
    muts = make_mutants(app_src)
    result = {}
    for name in names:
        if not run_test_inproc(app_src, module, test_src, name):
            result[name] = ("OK", "")          # doesn't pass clean; others judge
            continue
        killed = any(not run_test_inproc(m, module, test_src, name) for m in muts)
        result[name] = ("OK", "") if killed else ("FAKE", "stayed green while the app was broken")
    return result