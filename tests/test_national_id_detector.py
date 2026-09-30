import pytest

from data_warden.detectors.national_id import NationalIdDetector, is_valid_spanish_id


@pytest.mark.parametrize("value", ["12345678Z", "12345678-z", "X1234567L"])
def test_known_valid_ids(value):
    assert is_valid_spanish_id(value)


@pytest.mark.parametrize(
    "value",
    ["12345678A", "X1234567A", "1234567Z", "A2345678Z", "hello", "", "123456789"],
)
def test_wrong_letter_or_shape_is_rejected(value):
    assert not is_valid_spanish_id(value)


def test_match_rate():
    assert NationalIdDetector().match_rate(["12345678Z", "12345678A"]) == 0.5
