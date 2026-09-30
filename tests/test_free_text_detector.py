import pytest

from data_warden.detectors.free_text import FreeTextDetector, contains_personal_data


@pytest.mark.parametrize(
    "text",
    [
        "please write to ana.lopez@example.com tomorrow",
        "call back +34 612 345 678 after lunch",
        "call 612345678 asap",
        "pay into ES9121000418450200051332 by friday",
        "pay into ES91 2100 0418 4502 0005 1332 by friday",
        "customer id 12345678Z confirmed",
        "NIE X1234567L pending",
    ],
)
def test_detects_embedded_personal_data(text):
    assert contains_personal_data(text)


@pytest.mark.parametrize(
    "text",
    [
        "delivered to the front desk",
        "order ORD-000123 shipped",
        "total 49.90 EUR, postcode 08001",
        "12345 67890",  # digits, but not a valid phone shape
        "ES91 is a country code followed by nothing useful",
        "ticket 12345678A has a wrong check letter",
        "",
    ],
)
def test_ignores_ordinary_text(text):
    assert not contains_personal_data(text)


def test_match_rate_is_share_of_rows_that_leak():
    values = ["call 612345678", "all good", "nothing here", "mail a@b.com"]
    assert FreeTextDetector().match_rate(values) == 0.5


def test_has_its_own_low_threshold():
    assert FreeTextDetector().threshold == 0.05
