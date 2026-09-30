import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from typer.testing import CliRunner

from data_warden import synthetic
from data_warden.catalog import build_catalog, render_markdown, to_dict
from data_warden.check import Violation
from data_warden.cli import app
from data_warden.contracts import Contract
from data_warden.introspect import all_columns
from data_warden.scan import Finding

runner = CliRunner()
REPO = Path(__file__).resolve().parent.parent

COLUMNS = {"t": [("id", "INTEGER"), ("mail", "TEXT"), ("note", "TEXT")], "plain": [("x", "TEXT")]}


def columns_by_name(table):
    return {c.name: c for c in table.columns}


def test_column_sources_are_classified():
    findings = [
        Finding("t", "mail", "email", 1.0, 9),
        Finding("t", "note", "free_text_pii", 0.2, 9),
    ]
    contract = Contract("t", "team", 30, {"mail": "email", "ghost": "person_name"})
    table = build_catalog(COLUMNS, findings, {"t": contract}, []).tables[1]
    cols = columns_by_name(table)
    assert cols["mail"].source == "detected + declared"
    assert cols["note"].source == "detected only"
    assert cols["id"].source is None and cols["id"].pii_type is None
    assert cols["ghost"].source == "declared only"
    assert cols["ghost"].data_type == "not found in database"


def test_declared_type_wins_over_detected_type():
    findings = [Finding("t", "mail", "phone", 1.0, 9)]
    table = build_catalog(
        COLUMNS, findings, {"t": Contract("t", pii_columns={"mail": "email"})}, []
    )
    assert columns_by_name(table.tables[1])["mail"].pii_type == "email"


def test_violations_are_counted_per_table():
    violations = [
        Violation("error", "missing_field", "t", None, "x"),
        Violation("warning", "declared_not_detected", "t", "a", "y"),
    ]
    tables = {t.name: t for t in build_catalog(COLUMNS, [], {}, violations).tables}
    assert (tables["t"].errors, tables["t"].warnings) == (1, 1)
    assert (tables["plain"].errors, tables["plain"].warnings) == (0, 0)


def test_table_without_contract_is_called_out():
    findings = [Finding("t", "mail", "email", 1.0, 9)]
    markdown = render_markdown(build_catalog(COLUMNS, findings, {}, []))
    assert "No contract" in markdown
    assert "no personal data" in markdown  # the `plain` table


def test_markdown_is_deterministic_and_escapes_pipes():
    contract = Contract("t", "a|b", 30, {"mail": "email"})
    catalog = build_catalog(COLUMNS, [Finding("t", "mail", "email", 1.0, 9)], {"t": contract}, [])
    assert render_markdown(catalog) == render_markdown(catalog)
    assert "a\\|b" in render_markdown(catalog)


def test_to_dict_is_json_serialisable():
    catalog = build_catalog(COLUMNS, [Finding("t", "mail", "email", 0.123456, 9)], {}, [])
    data = json.loads(json.dumps(to_dict(catalog)))
    assert data["tables"][1]["columns"][1]["confidence"] == 0.1235


@pytest.fixture
def db_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'demo.db'}"
    synthetic.write_database(url, synthetic.generate())
    return url


def test_all_columns_lists_every_column_including_non_text(db_url):
    columns = dict(all_columns(create_engine(db_url))["orders"])
    assert "amount" in columns and "notes" in columns


def test_catalog_command_writes_both_files(db_url, tmp_path):
    out = tmp_path / "out"
    args = ["--url", db_url, "--dir", str(REPO / "examples" / "contracts"), "--out", str(out)]
    result = runner.invoke(app, ["catalog", *args])
    assert result.exit_code == 0, result.output
    markdown = (out / "catalog.md").read_text()
    assert "customer-data-team" in markdown
    data = json.loads((out / "catalog.json").read_text())
    assert {t["name"] for t in data["tables"]} == {"customers", "employees", "orders"}


def test_catalog_command_documents_violations_without_failing(db_url, tmp_path):
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    out = tmp_path / "out"
    result = runner.invoke(
        app, ["catalog", "--url", db_url, "--dir", str(contracts), "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert "No contract" in (out / "catalog.md").read_text()
