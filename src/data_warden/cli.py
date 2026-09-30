"""Command line entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import create_engine

from data_warden import __version__
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


@app.command(name="scan")
def scan_command(
    url: UrlOption = DEFAULT_URL,
    limit: Annotated[int, typer.Option(help="Max values sampled per column.")] = 1000,
    threshold: Annotated[
        float, typer.Option(min=0.0, max=1.0, help="Minimum match share to flag a column.")
    ] = DEFAULT_THRESHOLD,
) -> None:
    """Scan a database and list columns that look like personal data."""
    findings = scan(create_engine(url), limit=limit, threshold=threshold)
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
