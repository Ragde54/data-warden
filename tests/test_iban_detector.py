import pytest

from data_warden.detectors.iban import IbanDetector, is_valid_iban

VALID = [
    "ES9121000418450200051332",
    "DE89370400440532013000",
    "GB82WEST12345698765432",
    "FR1420041010050500013M02606",
]


@pytest.mark.parametrize("iban", VALID)
def test_known_valid_ibans(iban):
    assert is_valid_iban(iban)


def test_spaces_and_lowercase_are_tolerated():
    assert is_valid_iban("es91 2100 0418 4502 0005 1332")


def test_one_wrong_digit_breaks_the_checksum():
    assert not is_valid_iban("ES9121000418450200051333")


def test_wrong_length_for_known_country_is_rejected():
    assert not is_valid_iban("ES912100041845020005133")


@pytest.mark.parametrize("value", ["hello", "12345678", "ES00", "", "a@b.com"])
def test_non_ibans_are_rejected(value):
    assert not is_valid_iban(value)


def test_match_rate_and_empty_input():
    detector = IbanDetector()
    assert detector.match_rate([VALID[0], "nope"]) == 0.5
    assert detector.match_rate([]) == 0.0
