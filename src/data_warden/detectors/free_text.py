"""Free-text detector: personal data hiding inside sentences (notes, comments, descriptions).

The other detectors ask "is the whole value an email?". This one asks "does the value
*contain* an email, phone number, IBAN or national ID?". It reuses their validators, so the
checksum rules stay in one place.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from data_warden.detectors.base import match_share
from data_warden.detectors.emails import EMAIL_PATTERN
from data_warden.detectors.iban import is_valid_iban
from data_warden.detectors.national_id import is_valid_spanish_id
from data_warden.detectors.phone import is_phone_number

# Digits with optional separators, at least 9 characters long; validated afterwards.
_PHONE_CANDIDATE = re.compile(r"\+?\d[\d\s.\-()]{7,17}\d")
_TOKEN = re.compile(r"[A-Za-z0-9]+")
_IBAN_START = re.compile(r"[A-Za-z]{2}\d{2}")
_MAX_IBAN_TOKENS = 9  # a printed IBAN is at most 34 characters in groups of 4

# A column where even 1 row in 20 leaks personal data is a finding, unlike whole-value
# detectors, which need most rows to match. Tune with the evaluation in a later step.
FREE_TEXT_THRESHOLD = 0.05


def contains_personal_data(text: str) -> bool:
    if EMAIL_PATTERN.search(text):
        return True
    if any(is_phone_number(m.group()) for m in _PHONE_CANDIDATE.finditer(text)):
        return True
    tokens = _TOKEN.findall(text)
    for i, token in enumerate(tokens):
        if is_valid_spanish_id(token):
            return True
        if _IBAN_START.match(token):
            # IBANs are often printed in groups ("ES91 2100 0418 ..."), so try joining tokens.
            for end in range(i + 1, min(i + 1 + _MAX_IBAN_TOKENS, len(tokens) + 1)):
                if is_valid_iban("".join(tokens[i:end])):
                    return True
    return False


class FreeTextDetector:
    pii_type = "free_text_pii"
    threshold: float | None = FREE_TEXT_THRESHOLD

    def match_rate(self, values: Sequence[str]) -> float:
        """Share of values that contain at least one piece of personal data."""
        return match_share(values, contains_personal_data)
