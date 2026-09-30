"""Score scan findings against an answer key: precision and recall per PII type.

Precision: of the columns the scanner flagged as type X, how many really are X?
Recall: of the columns that really are type X, how many did the scanner find?
A wrong type counts twice: a miss for the real type and a false alarm for the predicted one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from data_warden.scan import Finding


@dataclass(frozen=True)
class TypeScore:
    pii_type: str
    tp: int  # true positives: flagged as this type, and it is
    fp: int  # false positives: flagged as this type, and it is not
    fn: int  # false negatives: it is this type, and the scanner missed or mislabelled it

    @property
    def precision(self) -> float | None:
        """None when nothing was flagged as this type (no claims, so no precision)."""
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else None

    @property
    def recall(self) -> float | None:
        """None when the key has no column of this type."""
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else None


@dataclass(frozen=True)
class Report:
    by_type: list[TypeScore]
    overall: TypeScore  # micro-average: all counts summed, so every column weighs the same
    unlabeled: int  # flagged columns missing from the key; they are ignored, not penalised


def load_ground_truth(path: Path) -> dict[str, str | None]:
    return json.loads(path.read_text())


def evaluate(findings: list[Finding], truth: dict[str, str | None]) -> Report:
    predicted = {f"{f.table}.{f.column}": f.pii_type for f in findings}
    unlabeled = sum(1 for column in predicted if column not in truth)
    types = {t for t in truth.values() if t} | {
        t for column, t in predicted.items() if column in truth
    }
    scores: list[TypeScore] = []
    for pii_type in sorted(types):
        tp = fp = fn = 0
        for column, actual in truth.items():
            guess = predicted.get(column)
            if guess == pii_type and actual == pii_type:
                tp += 1
            elif guess == pii_type:
                fp += 1
            elif actual == pii_type:
                fn += 1
        scores.append(TypeScore(pii_type, tp, fp, fn))
    overall = TypeScore(
        "overall",
        sum(s.tp for s in scores),
        sum(s.fp for s in scores),
        sum(s.fn for s in scores),
    )
    return Report(scores, overall, unlabeled)
