"""to_currency(decimals=False) rounds to whole units and respects the locale's decimal symbol."""
import pytest

import rangekeeper as rk


@pytest.mark.parametrize(
    "value, expected",
    [
        (1265.9, "£1,266"),
        (99.99, "£100"),
        (0.9, "£1"),
        (0.4, "£0"),
        (1156404.46, "£1,156,404"),
        (1156404.6, "£1,156,405"),
        (1265.0, "£1,265"),
        (-1265.9, "-£1,266"),
    ],
)
def test_whole_units_are_rounded_not_truncated(value, expected):
    assert (
        rk.format.to_currency(value, currency="GBP", locale="en_GB", decimals=False)
        == expected
    )


def test_half_rounds_to_even_like_to_decimal():
    # to_currency already uses to_decimal's ROUND_HALF_EVEN for its two decimals
    assert (
        rk.format.to_currency(1264.5, currency="GBP", locale="en_GB", decimals=False)
        == "£1,264"
    )
    assert (
        rk.format.to_currency(1265.5, currency="GBP", locale="en_GB", decimals=False)
        == "£1,266"
    )


@pytest.mark.parametrize(
    "locale, expected_prefix",
    [("de_DE", "1.266"), ("fr_FR", "1 266")],
)
def test_comma_decimal_locales_keep_the_whole_part(locale, expected_prefix):
    # splitting on "." returned "1" for locales whose decimal symbol is a comma
    text = rk.format.to_currency(
        1265.9, currency="EUR", locale=locale, decimals=False
    )
    assert text.startswith(expected_prefix) or expected_prefix in text
    assert "," not in text


def test_decimals_true_is_unchanged():
    assert (
        rk.format.to_currency(1265.9, currency="GBP", locale="en_GB") == "£1,265.90"
    )
