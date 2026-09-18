"""A calculator with real branching and error handling.

Supports +, -, *, /, % (modulo) and ^ (power). Raises on divide/modulo by
zero and on an unknown operation, so its tests have real behavior — and real
error paths — to get right or wrong.
"""


def calculate(a, op, b):
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if b == 0:
            raise ZeroDivisionError("Cannot divide by zero")
        return a / b
    if op == "%":
        if b == 0:
            raise ZeroDivisionError("Cannot take modulo by zero")
        return a % b
    if op == "^":
        return a ** b
    raise ValueError(f"Unknown operation: {op!r}")