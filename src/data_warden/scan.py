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
    confidence: float  # share of sampled values that matched
    sample_size: int


def scan(
    engine: Engine,
    detectors: list[Detector] | None = None,
    limit: int = 1000,
    threshold: float = DEFAULT_THRESHOLD,
    schema: str | None = None,
) -> list[Finding]:
    """Return one finding per column: the best-matching detector, if it clears the threshold."""
    detectors = detectors if detectors is not None else default_detectors()
    findings: list[Finding] = []
    for sample in collect_samples(engine, limit=limit, schema=schema):
        if not sample.values:
            continue  # no evidence either way
        best = max(
            ((d.pii_type, d.match_rate(sample.values)) for d in detectors),
            key=lambda pair: pair[1],
            default=None,
        )
        if best and best[1] >= threshold:
            findings.append(
                Finding(sample.table, sample.column, best[0], best[1], len(sample.values))
            )
    return sorted(findings, key=lambda f: (-f.confidence, f.table, f.column))
