import pytest

from data_warden.detectors.emails import EmailDetector

detector = EmailDetector()


def test_all_valid_emails():
    assert detector.match_rate(["a@b.com", "first.last+tag@sub.example.org"]) == 1.0


def test_mixed_values_give_partial_rate():
    assert detector.match_rate(["a@b.com", "not an email", "x@y.es", "12345"]) == 0.5


def test_empty_input_means_no_evidence():
    assert detector.match_rate([]) == 0.0


def test_whitespace_around_value_is_ignored():
    assert detector.match_rate(["  a@b.com \n"]) == 1.0


@pytest.mark.parametrize(
    "value",
    ["call me at a@b.com please", "a@b", "@b.com", "a@@b.com", "a b@c.com", "a@b.c"],
)
def test_rejects_things_that_are_not_just_an_email(value):
    assert detector.match_rate([value]) == 0.0
