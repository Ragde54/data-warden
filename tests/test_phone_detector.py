import pytest

from data_warden.detectors.phone import PhoneDetector, is_phone_number


@pytest.mark.parametrize(
    "value",
    ["+34 612 345 678", "+34612345678", "612345678", "912 345 678", "+34 (91) 234 56 78",
     "+49 30 1234567", "612-345-678", "612.345.678"],
)  # fmt: skip
def test_valid_phone_formats(value):
    assert is_phone_number(value)


@pytest.mark.parametrize(
    "value",
    [
        "08001",  # Spanish postcode
        "ORD-000123",  # order reference
        "12345678Z",  # national ID
        "ES9121000418450200051332",  # IBAN
        "0000123456",  # zero-padded id
        "512345678",  # 9 digits but starts with 5, not a Spanish phone
        "call back +34 612 345 678",  # free text is a different detector's job
        "a@b.com",
        "",
    ],
)
def test_lookalikes_are_rejected(value):
    assert not is_phone_number(value)


def test_match_rate():
    assert PhoneDetector().match_rate(["612345678", "08001"]) == 0.5
    assert PhoneDetector().match_rate([]) == 0.0
