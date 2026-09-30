"""Spanish national identifiers (DNI and NIE) with check-letter validation."""

from __future__ import annotations

import re
from collections.abc import Sequence

from data_warden.detectors.base import match_share

# Deliberately duplicated from the demo-data generator: the detector must not depend on it,
# otherwise the evaluation would be grading the scanner against its own answer sheet.
_CHECK_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_DNI = re.compile(r"\d{8}[A-Z]")
_NIE = re.compile(r"[XYZ]\d{7}[A-Z]")
_NIE_PREFIX = {"X": "0", "Y": "1", "Z": "2"}


def is_valid_spanish_id(value: str) -> bool:
    candidate = re.sub(r"[\s-]", "", value).upper()
    if _NIE.fullmatch(candidate):
        candidate = _NIE_PREFIX[candidate[0]] + candidate[1:]
    elif not _DNI.fullmatch(candidate):
        return False
    number, letter = int(candidate[:8]), candidate[8]
    return _CHECK_LETTERS[number % 23] == letter


class NationalIdDetector:
    pii_type = "national_id"
    threshold: float | None = None

    def match_rate(self, values: Sequence[str]) -> float:
        return match_share(values, is_valid_spanish_id)
