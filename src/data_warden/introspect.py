"""Read-only access to a database: list text columns and sample their values.

This is the only module that talks to the database. Detectors receive plain lists of
strings, so they can be tested without any connection.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from sqlalchemy import Engine, String, and_, column, inspect, select, table


@dataclass(frozen=True)
class ColumnSample:
    """Non-empty values sampled from one text column."""

    table: str
    column: str
    values: list[str]


def text_columns(engine: Engine, schema: str | None = None) -> list[tuple[str, str]]:
    """Return (table, column) pairs whose type is a string type.

    `Text` is a subclass of `String`, so one check covers VARCHAR, TEXT and friends.
    """
    inspector = inspect(engine)
    found: list[tuple[str, str]] = []
    for table_name in sorted(inspector.get_table_names(schema=schema)):
        for col in inspector.get_columns(table_name, schema=schema):
            if isinstance(col["type"], String):
                found.append((table_name, col["name"]))
    return found


def sample_column(
    engine: Engine,
    table_name: str,
    column_name: str,
    limit: int = 1000,
    schema: str | None = None,
) -> list[str]:
    """Return up to `limit` non-null, non-empty values from one column.

    Names are built with SQLAlchemy constructs (never f-strings), so quoting is correct
    and a hostile table or column name cannot inject SQL.
    Note: LIMIT without ORDER BY is not a random sample. See docs/decisions/0002-sampling.md.
    """
    col = column(column_name)
    stmt = (
        select(col)
        .select_from(table(table_name, schema=schema))
        .where(and_(col.is_not(None), col != ""))
        .limit(limit)
    )
    with engine.connect() as conn:
        return [str(value) for value in conn.execute(stmt).scalars()]


def collect_samples(
    engine: Engine, limit: int = 1000, schema: str | None = None
) -> Iterator[ColumnSample]:
    """Yield one ColumnSample per text column (lazily, one column at a time)."""
    for table_name, column_name in text_columns(engine, schema=schema):
        values = sample_column(engine, table_name, column_name, limit=limit, schema=schema)
        yield ColumnSample(table=table_name, column=column_name, values=values)


def all_columns(engine: Engine, schema: str | None = None) -> dict[str, list[tuple[str, str]]]:
    """Every table with its (column name, column type) pairs, in database order."""
    inspector = inspect(engine)
    return {
        table_name: [
            (col["name"], str(col["type"]))
            for col in inspector.get_columns(table_name, schema=schema)
        ]
        for table_name in sorted(inspector.get_table_names(schema=schema))
    }
