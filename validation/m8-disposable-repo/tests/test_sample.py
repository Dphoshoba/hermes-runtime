"""Tests for the sample service. Used by EVOSIA M8 preparation validation."""

from src import calc, config


def test_add():
    assert calc.add(2, 3) == 5


def test_subtract():
    assert calc.subtract(5, 2) == 3


def test_multiply():
    assert calc.multiply(3, 4) == 12


def test_divide():
    assert calc.divide(10, 2) == 5


def test_health_check():
    result = calc.health_check()
    assert result["status"] == "ok"


def test_config_has_placeholder_key():
    # The placeholder key is obviously fake and must remain so.
    assert config.API_KEY.startswith("example-fake-key")
