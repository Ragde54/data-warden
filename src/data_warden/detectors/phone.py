"""Phone number detector (international format or Spanish national format)."""

from __future__ import annotations

import re
from collections.abc import Sequence

from data_warden.detectors.base import match_share

# After stripping spaces, dots, hyphens and brackets, accept only:
#   +<8 to 14 digits>   international format (the E.164 standard allows 15 digits in total)
#   [6-9]<8 digits>     Spanish national format: 9 digits, first digit 6, 7, 8 or 9
# Not accepted on purpose: a "00" international prefix (zero-padded IDs would match) and bare
# digit strings of other lengths (postcodes, order numbers). Precision over recall.
_PHONE = re.compile(r"\+\d{8,14}|[6-9]\d{8}")
_SEPARATORS = re.compile(r"[\s.\-()]")


def is_phone_number(value: str) -> bool:
    return _PHONE.fullmatch(_SEPARATORS.sub("", value)) is not None


class PhoneDetector:
    pii_type = "phone"
    threshold: float | None = None

    def match_rate(self, values: Sequence[str]) -> float:
        return match_share(values, is_phone_number)
