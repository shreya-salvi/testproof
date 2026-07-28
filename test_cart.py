# test_cart.py - tests for the cart (1 real, 1 fake)
from cart import total

# REAL: checks the actual total
def test_total_good():
    assert total(10, 5) == 15

# FAKE: has an assert but checks nothing meaningful
def test_total_fake():
    result = total(10, 5)
    assert result != None