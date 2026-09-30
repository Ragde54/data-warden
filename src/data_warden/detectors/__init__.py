"""Registry of available detectors."""

from __future__ import annotations

from data_warden.detectors.base import Detector
from data_warden.detectors.emails import EmailDetector
from data_warden.detectors.free_text import FreeTextDetector
from data_warden.detectors.iban import IbanDetector
from data_warden.detectors.national_id import NationalIdDetector
from data_warden.detectors.phone import PhoneDetector


def default_detectors() -> list[Detector]:
    return [
        EmailDetector(),
        IbanDetector(),
        NationalIdDetector(),
        PhoneDetector(),
        FreeTextDetector(),
    ]
