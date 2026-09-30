"""Email address detector."""

from __future__ import annotations

import re
from collections.abc import Sequence

from data_warden.detectors.base import match_share

# Pragmatic, not RFC 5322: local part, one @, dotted domain, alphabetic top-level domain.
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")


class EmailDetector:
    pii_type = "email"
    threshold: float | None = None

    def match_rate(self, values: Sequence[str]) -> float:
        # fullmatch, not search: a sentence that merely contains an email is free text,
        # which gets its own detector later. A column is "email" when the whole value is one.
        return match_share(values, lambda v: EMAIL_PATTERN.fullmatch(v.strip()) is not None)
