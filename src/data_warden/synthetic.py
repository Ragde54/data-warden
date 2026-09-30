"""Deterministic, deliberately messy demo data with known ground truth.

Why: to measure a scanner you need to know the right answers in advance.
Every column here is labelled in GROUND_TRUTH (a PII type, or None for decoys).
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from sqlalchemy import Column, Integer, MetaData, Numeric, Table, Text, create_engine

DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"

# Products named after people: a trap for anything that guesses "person name" by word shape.
PRODUCT_NAMES = [
    "Silla Eames", "Lampara Tiffany", "Mesa Bauhaus", "Sofa Chesterfield",
    "Estanteria Billy", "Escritorio Ferdinand", "Cama Montessori", "Butaca Wassily",
]  # fmt: skip

# "table.column" -> PII type, or None when the column is NOT personal data (a decoy).
GROUND_TRUTH: dict[str, str | None] = {
    "customers.id": None,
    "customers.full_name": "person_name",
    "customers.col7": "email",  # hidden behind a useless name on purpose
    "customers.iban_raw": "iban",
    "customers.phone": "phone",
    "customers.postcode": None,  # digits, but not personal
    "customers.segment": None,
    "customers.company_name": None,  # decoy: reads like a surname, but it is a company
    "orders.id": None,
    "orders.customer_id": None,
    "orders.amount": None,
    "orders.order_ref": None,  # looks like an identifier, is not PII
    "orders.product_name": None,  # decoy: product names borrowed from people
    "orders.notes": "free_text_pii",  # sometimes contains a phone number
    "employees.id": None,
    "employees.ref_code": "national_id",  # Spanish DNI hidden in a vague column
    "employees.department": None,
    "employees.hired_year": None,
}


def make_dni(rng: random.Random) -> str:
    """Spanish DNI: 8 digits plus a check letter derived from the number."""
    number = rng.randrange(10_000_000, 99_999_999)
    return f"{number}{DNI_LETTERS[number % 23]}"


def generate(seed: int = 42, rows: int = 200) -> dict[str, list[dict[str, Any]]]:
    """Build the demo dataset in memory. Same seed, same data."""
    from faker import Faker  # optional dependency (extra: demo)

    fake = Faker("es_ES")
    Faker.seed(seed)
    rng = random.Random(seed)

    customers = [
        {
            "id": i,
            "full_name": fake.name(),
            "col7": fake.email(),
            "iban_raw": fake.iban(),
            "phone": fake.phone_number(),
            "postcode": fake.postcode(),
            "segment": rng.choice(["retail", "smb", "enterprise"]),
            "company_name": fake.company(),
        }
        for i in range(1, rows + 1)
    ]
    orders = []
    for i in range(1, rows * 2 + 1):
        leaks_phone = rng.random() < 0.15
        note = "call back " + fake.phone_number() if leaks_phone else fake.sentence(nb_words=6)
        orders.append(
            {
                "id": i,
                "customer_id": rng.randint(1, rows),
                "amount": round(rng.uniform(5, 900), 2),
                "order_ref": f"ORD-{i:06d}",
                "product_name": rng.choice(PRODUCT_NAMES),
                "notes": note,
            }
        )
    employees = [
        {
            "id": i,
            "ref_code": make_dni(rng),
            "department": rng.choice(["data", "ops", "finance", "sales"]),
            "hired_year": rng.randint(2012, 2026),
        }
        for i in range(1, max(rows // 10, 5) + 1)
    ]
    return {"customers": customers, "orders": orders, "employees": employees}


def _tables(meta: MetaData) -> None:
    Table(
        "customers",
        meta,
        Column("id", Integer, primary_key=True),
        Column("full_name", Text),
        Column("col7", Text),
        Column("iban_raw", Text),
        Column("phone", Text),
        Column("postcode", Text),
        Column("segment", Text),
        Column("company_name", Text),
    )
    Table(
        "orders",
        meta,
        Column("id", Integer, primary_key=True),
        Column("customer_id", Integer),
        Column("amount", Numeric(10, 2)),
        Column("order_ref", Text),
        Column("product_name", Text),
        Column("notes", Text),
    )
    Table(
        "employees",
        meta,
        Column("id", Integer, primary_key=True),
        Column("ref_code", Text),
        Column("department", Text),
        Column("hired_year", Integer),
    )


def write_database(url: str, data: dict[str, list[dict[str, Any]]]) -> None:
    """Drop and recreate the demo tables, then load the data."""
    engine = create_engine(url)
    meta = MetaData()
    _tables(meta)
    meta.drop_all(engine)
    meta.create_all(engine)
    with engine.begin() as conn:
        for name, rows in data.items():
            conn.execute(meta.tables[name].insert(), rows)


def write_ground_truth(path: Path) -> None:
    path.write_text(json.dumps(GROUND_TRUTH, indent=2, sort_keys=True) + "\n")
