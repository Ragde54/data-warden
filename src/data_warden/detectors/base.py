"""The contract every detector follows.

A detector never sees a database. It receives plain strings and answers one question:
"what share of these values look like my kind of personal data?"
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol


class Detector(Protocol):
    pii_type: str

    def match_rate(self, values: Sequence[str]) -> float:
        """Share of values (0.0 to 1.0) that match this detector's PII type."""
        ...


def match_share(values: Sequence[str], predicate: Callable[[str], bool]) -> float:
    """Fraction of values for which `predicate` is true. Empty input gives 0.0 (no evidence)."""
    if not values:
        return 0.0
    return sum(1 for value in values if predicate(value)) / len(values)
