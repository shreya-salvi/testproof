import pytest
from calculator import calculate


def test_add_is_correct():
    # STRONG: exact value
    assert calculate(2, "+", 3) == 5


def test_power_is_correct():
    # STRONG: a more complex operation
    assert calculate(2, "^", 10) == 1024


def test_divide_by_zero_raises():
    # STRONG: checks the error path is handled
    with pytest.raises(ZeroDivisionError):
        calculate(5, "/", 0)


def test_multiply_smoke():
    # WEAK: only checks the type, not the value
    assert isinstance(calculate(4, "*", 5), (int, float))


def test_subtract_runs():
    # FAKE: no assertion at all
    calculate(10, "-", 4)