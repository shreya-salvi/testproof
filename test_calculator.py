# test_calculator.py
# Three tests for the calculator.
# They will ALL show green when we run them.
# But only ONE of them is actually a real test. Watch.

from calculator import add


# ---- TEST 1: a REAL test ----
# It checks the actual answer: 2 + 2 must be 4.
def test_add_good():
    result = add(2, 2)
    assert result == 4


# ---- TEST 2: a LAZY FAKE ----
# It runs the code... but never checks the answer.
# No "assert" at all. It checks nothing. (Guard with eyes closed.)
def test_add_lazy():
    result = add(2, 2)
    # (no assert here - this test can never fail)


# ---- TEST 3: a SNEAKY FAKE ----
# It HAS an assert, so it looks real...
# but it only checks "is the result a number?" - not that it's 4.
# If the calculator broke and returned 5, this test would still pass.
def test_add_sneaky():
    result = add(2, 2)
    assert isinstance(result, int)
