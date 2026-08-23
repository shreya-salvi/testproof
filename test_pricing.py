# test_pricing.py — three tests that ALL pass in a normal run.
# TestProof reveals that only one of them actually protects you.

from pricing import final_price


def test_price_is_correct():
    # STRONG: asserts the exact expected amount.
    # base 100, 20% off -> 80, +10% tax -> 88.00
    assert final_price(100, 20, 10) == 88.0


def test_price_smoke():
    # WEAK: looks like a real test, but only checks the TYPE.
    # A completely wrong price would still pass this.
    result = final_price(100, 20, 10)
    assert isinstance(result, float)


def test_price_runs():
    # FAKE: no assertion at all. It only checks the code doesn't crash.
    final_price(100, 20, 10)