"""Command line entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from data_warden import __version__

app = typer.Typer(help="Find personal data in databases and govern it as code.")

DEFAULT_URL = "postgresql+psycopg://warden:warden@localhost:5432/demo"


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


@app.command()
def seed(
    url: Annotated[
        str, typer.Option(envvar="DATA_WARDEN_DB_URL", help="Target database.")
    ] = DEFAULT_URL,
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
