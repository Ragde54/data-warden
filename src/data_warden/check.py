"""Compare what the scanner found with what the contracts declare."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from data_warden.contracts import Contract
from data_warden.policy import Policy
from data_warden.scan import Finding


@dataclass(frozen=True)
class Violation:
    severity: str  # "error" fails the check, "warning" does not
    rule: str
    table: str
    column: str | None
    message: str


def run_checks(
    findings: list[Finding], contracts: dict[str, Contract], policy: Policy
) -> list[Violation]:
    detected: dict[str, dict[str, str]] = defaultdict(dict)
    for f in findings:
        detected[f.table][f.column] = f.pii_type
    declared_tables = {table for table, c in contracts.items() if c.pii_columns}

    out: list[Violation] = []
    for table in sorted(set(detected) | declared_tables):
        found = detected.get(table, {})
        contract = contracts.get(table)
        if contract is None:
            out.append(
                Violation(
                    "error",
                    "missing_contract",
                    table,
                    None,
                    f"personal data found in {', '.join(sorted(found))} but the table has no "
                    "contract",
                )
            )
            continue
        for column, pii_type in sorted(found.items()):
            declared = contract.pii_columns.get(column)
            if declared is None:
                out.append(
                    Violation(
                        "error",
                        "undeclared_pii",
                        table,
                        column,
                        f"scanner found {pii_type}; the contract does not declare it",
                    )
                )
            elif declared != pii_type:
                out.append(
                    Violation(
                        "error",
                        "pii_type_mismatch",
                        table,
                        column,
                        f"contract declares {declared}, scanner found {pii_type}",
                    )
                )
        for column, declared in sorted(contract.pii_columns.items()):
            if column not in found:
                out.append(
                    Violation(
                        "warning",
                        "declared_not_detected",
                        table,
                        column,
                        f"declared as {declared} but the scanner did not detect it "
                        "(expected for types rules cannot find, such as person names)",
                    )
                )
        for required in policy.pii_tables_require:
            if not getattr(contract, required):
                out.append(
                    Violation(
                        "error",
                        "missing_field",
                        table,
                        None,
                        f"table holds personal data but `{required}` is not set",
                    )
                )
    return sorted(out, key=lambda v: (v.severity != "error", v.table, v.column or "", v.rule))
