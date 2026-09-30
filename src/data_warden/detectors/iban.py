"""IBAN (international bank account number) detector with checksum validation."""

from __future__ import annotations

import re
from collections.abc import Sequence

from data_warden.detectors.base import match_share

_SHAPE = re.compile(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}")

# Exact lengths for common European countries. Unknown countries fall back to the generic shape.
_LENGTH_BY_COUNTRY = {
    "AT": 20, "BE": 16, "CH": 21, "DE": 22, "ES": 24, "FR": 27,
    "GB": 22, "IE": 22, "IT": 27, "LU": 20, "NL": 18, "PT": 25,
}  # fmt: skip


def is_valid_iban(value: str) -> bool:
    iban = re.sub(r"[\s-]", "", value).upper()
    if not _SHAPE.fullmatch(iban):
        return False
    expected = _LENGTH_BY_COUNTRY.get(iban[:2])
    if expected is not None and len(iban) != expected:
        return False
    # mod-97 check: move the first four characters to the end, turn letters into numbers
    # (A=10 ... Z=35), and the resulting big integer must leave remainder 1 when divided by 97.
    rearranged = iban[4:] + iban[:4]
    digits = "".join(str(int(char, 36)) for char in rearranged)
    return int(digits) % 97 == 1


class IbanDetector:
    pii_type = "iban"
    threshold: float | None = None

    def match_rate(self, values: Sequence[str]) -> float:
        return match_share(values, is_valid_iban)
