"""Registry of available detectors."""

from __future__ import annotations

from data_warden.detectors.base import Detector
from data_warden.detectors.emails import EmailDetector


def default_detectors() -> list[Detector]:
    return [EmailDetector()]
