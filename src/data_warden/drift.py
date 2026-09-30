"""What changed between two catalog snapshots: new tables and columns, new or changed PII.

This is the audit trail, not the alarm. The alarm is `check`, which compares the live database
with the contracts and needs no stored state. `diff` answers a different question: *when* did a
column first show up, and what else moved.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Change:
    kind: str  # table_added, table_removed, column_added, column_removed, pii_added, ...
    table: str
    column: str | None
    detail: str

    @property
    def is_pii_risk(self) -> bool:
        """True for changes that mean more personal data than before."""
        return self.kind in {"pii_added", "pii_type_changed", "pii_table_added"}


def _index(catalog: dict) -> dict[str, dict[str, dict]]:
    return {t["name"]: {c["name"]: c for c in t["columns"]} for t in catalog["tables"]}


def diff_catalogs(old: dict, new: dict) -> list[Change]:
    """Compare two `catalog.json` documents."""
    before, after = _index(old), _index(new)
    changes: list[Change] = []
    for table in sorted(after.keys() - before.keys()):
        pii = [n for n, c in after[table].items() if c["pii_type"]]
        changes.append(Change("table_added", table, None, f"{len(after[table])} column(s)"))
        for column in sorted(pii):
            changes.append(
                Change(
                    "pii_added", table, column, f"{after[table][column]['pii_type']} (new table)"
                )
            )
    for table in sorted(before.keys() - after.keys()):
        changes.append(Change("table_removed", table, None, "no longer in the database"))
    for table in sorted(before.keys() & after.keys()):
        old_cols, new_cols = before[table], after[table]
        for column in sorted(new_cols.keys() - old_cols.keys()):
            pii = new_cols[column]["pii_type"]
            changes.append(Change("column_added", table, column, new_cols[column]["data_type"]))
            if pii:
                changes.append(Change("pii_added", table, column, pii))
        for column in sorted(old_cols.keys() - new_cols.keys()):
            changes.append(Change("column_removed", table, column, old_cols[column]["data_type"]))
        for column in sorted(old_cols.keys() & new_cols.keys()):
            was, now = old_cols[column]["pii_type"], new_cols[column]["pii_type"]
            if was is None and now:
                changes.append(Change("pii_added", table, column, now))
            elif was and now is None:
                changes.append(Change("pii_removed", table, column, was))
            elif was and now and was != now:
                changes.append(Change("pii_type_changed", table, column, f"{was} -> {now}"))
    return changes


def load_catalog(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "tables" not in data:
        raise ValueError(f"{path}: not a catalog.json (no `tables` key)")
    return data


def previous_catalog(current: Path) -> Path | None:
    """The newest sibling run folder that sorts before this one, if any.

    Layout: <history>/<run-id>/catalog.json, where run ids are ISO dates, which sort correctly as
    plain text. Falling back to "the latest earlier folder" (not "yesterday") keeps the diff
    working across skipped days, manual runs and backfills.
    """
    history, run_id = current.parent.parent, current.parent.name
    earlier = sorted(
        d.name
        for d in history.iterdir()
        if d.is_dir() and d.name < run_id and (d / current.name).exists()
    )
    return history / earlier[-1] / current.name if earlier else None
