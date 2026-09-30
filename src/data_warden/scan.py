"""Run detectors over sampled columns and keep the confident findings."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine

from data_warden.detectors import default_detectors
from data_warden.detectors.base import Detector
from data_warden.introspect import collect_samples

DEFAULT_THRESHOLD = 0.8


@dataclass(frozen=True)
class Finding:
    table: str
    column: str
    pii_type: str
    # Share of sampled values that match. For free_text_pii it is the share that *contain*
    # personal data, which is why that type has its own, much lower threshold.
    confidence: float
    sample_size: int


def scan(
    engine: Engine,
    detectors: list[Detector] | None = None,
    limit: int = 1000,
    threshold: float = DEFAULT_THRESHOLD,
    schema: str | None = None,
) -> list[Finding]:
    """Return at most one finding per column.

    The detector with the highest match rate wins; ties go to the earlier detector in the list,
    so whole-value detectors beat free text (a column of pure emails is "email"). The winner then
    has to clear its own `threshold`, or the scan-wide one if it has none.
    """
    detectors = detectors if detectors is not None else default_detectors()
    findings: list[Finding] = []
    for sample in collect_samples(engine, limit=limit, schema=schema):
        if not sample.values:
            continue  # no evidence either way
        scored = [(d, d.match_rate(sample.values)) for d in detectors]
        if not scored:
            continue
        best, rate = max(scored, key=lambda pair: pair[1])  # max keeps the first of equal rates
        required = best.threshold if best.threshold is not None else threshold
        if rate >= required:
            findings.append(
                Finding(sample.table, sample.column, best.pii_type, rate, len(sample.values))
            )
    return sorted(findings, key=lambda f: (-f.confidence, f.table, f.column))
