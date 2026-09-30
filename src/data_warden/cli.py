"""Command line entry point."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import create_engine

from data_warden import __version__
from data_warden.evaluate import Report, evaluate, load_ground_truth
from data_warden.scan import DEFAULT_THRESHOLD, scan

app = typer.Typer(help="Find personal data in databases and govern it as code.")

DEFAULT_URL = "postgresql+psycopg://warden:warden@localhost:5432/demo"

UrlOption = Annotated[str, typer.Option(envvar="DATA_WARDEN_DB_URL", help="Database to use.")]


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


@app.command()
def seed(
    url: UrlOption = DEFAULT_URL,
    rows: Annotated[int, typer.Option(help="Number of customers; other tables scale.")] = 200,
    seed_value: Annotated[
        int, typer.Option("--seed", help="Random seed; same seed, same data.")
    ] = 42,
    truth_out: Annotated[Path, typer.Option(help="Where to write the answer key.")] = Path(
        "ground_truth.json"
    ),
) -> None:
    """Load messy demo data into a database and write the answer key."""
    from data_warden import synthetic

    data = synthetic.generate(seed=seed_value, rows=rows)
    synthetic.write_database(url, data)
    synthetic.write_ground_truth(truth_out)
    typer.echo(f"Seeded {sum(len(r) for r in data.values())} rows; answer key: {truth_out}")


LimitOption = Annotated[int, typer.Option(help="Max values sampled per column.")]
ThresholdOption = Annotated[
    float, typer.Option(min=0.0, max=1.0, help="Minimum match share to flag a column.")
]
JsonOption = Annotated[bool, typer.Option("--json", help="Print machine-readable JSON only.")]


@app.command(name="scan")
def scan_command(
    url: UrlOption = DEFAULT_URL,
    limit: LimitOption = 1000,
    threshold: ThresholdOption = DEFAULT_THRESHOLD,
    as_json: JsonOption = False,
) -> None:
    """Scan a database and list columns that look like personal data."""
    findings = scan(create_engine(url), limit=limit, threshold=threshold)
    if as_json:
        typer.echo(json.dumps([asdict(f) for f in findings], indent=2))
        return
    if not findings:
        typer.echo(
            f"No personal data found at threshold {threshold:.0%}. "
            "A clean scan is evidence, not proof."
        )
        return
    typer.echo(f"{'COLUMN':<28}{'TYPE':<16}{'CONFIDENCE':<12}SAMPLES")
    for f in findings:
        typer.echo(
            f"{f.table + '.' + f.column:<28}{f.pii_type:<16}{f.confidence:<12.0%}{f.sample_size}"
        )


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def _report_to_dict(report: Report) -> dict:
    rows = [*report.by_type, report.overall]
    return {
        "unlabeled": report.unlabeled,
        "scores": [
            {
                "type": s.pii_type,
                "tp": s.tp,
                "fp": s.fp,
                "fn": s.fn,
                "precision": s.precision,
                "recall": s.recall,
            }
            for s in rows
        ],
    }


@app.command(name="evaluate")
def evaluate_command(
    url: UrlOption = DEFAULT_URL,
    truth: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, help="Answer key written by `seed`."),
    ] = Path("ground_truth.json"),
    limit: LimitOption = 1000,
    threshold: ThresholdOption = DEFAULT_THRESHOLD,
    as_json: JsonOption = False,
) -> None:
    """Score the scanner against an answer key (precision and recall per PII type)."""
    findings = scan(create_engine(url), limit=limit, threshold=threshold)
    report = evaluate(findings, load_ground_truth(truth))
    if as_json:
        typer.echo(json.dumps(_report_to_dict(report), indent=2))
        return
    typer.echo(f"{'TYPE':<16}{'TP':>4}{'FP':>4}{'FN':>4}  {'PRECISION':<11}RECALL")
    for s in [*report.by_type, report.overall]:
        typer.echo(
            f"{s.pii_type:<16}{s.tp:>4}{s.fp:>4}{s.fn:>4}  "
            f"{_percent(s.precision):<11}{_percent(s.recall)}"
        )
    if report.unlabeled:
        typer.echo(
            f"\n{report.unlabeled} flagged column(s) are not in the answer key and were ignored."
        )
