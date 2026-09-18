"""Layer 1 — static scanner. Flags tests that make no real check."""

import ast


def scan_file(test_file):
    src = open(test_file, encoding="utf-8").read()
    tree = ast.parse(src)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
            seg = ast.get_source_segment(src, node) or ""
            has_assert = any(isinstance(n, ast.Assert) for n in ast.walk(node))
            has_raises = "pytest.raises" in seg or ".assertRaises" in seg
            if has_assert or has_raises:
                out.append((node.name, "OK", ""))
            else:
                out.append((node.name, "FAKE", "no real check — no assertion"))
    return out