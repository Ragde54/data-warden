import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from typer.testing import CliRunner

from data_warden import synthetic
from data_warden.catalog import build_catalog, to_dict
from data_warden.cli import app
from data_warden.drift import diff_catalogs, load_catalog, previous_catalog
from data_warden.scan import Finding

runner = CliRunner()
REPO = Path(__file__).resolve().parent.parent


def catalog(columns, findings=()):
    return to_dict(build_catalog(columns, list(findings), {}, []))


BASE = {"t": [("id", "INTEGER"), ("mail", "TEXT")]}
MAIL = Finding("t", "mail", "email", 1.0, 5)


def kinds(changes):
    return [(c.kind, c.table, c.column) for c in changes]


def test_identical_catalogs_have_no_changes():
    assert diff_catalogs(catalog(BASE, [MAIL]), catalog(BASE, [MAIL])) == []


def test_new_column_holding_pii_is_a_risk():
    new = {"t": [*BASE["t"], ("contact", "TEXT")]}
    found = [MAIL, Finding("t", "contact", "phone", 1.0, 5)]
    changes = diff_catalogs(catalog(BASE, [MAIL]), catalog(new, found))
    assert kinds(changes) == [("column_added", "t", "contact"), ("pii_added", "t", "contact")]
    assert [c.is_pii_risk for c in changes] == [False, True]


def test_new_plain_column_is_not_a_risk():
    new = {"t": [*BASE["t"], ("note", "TEXT")]}
    (change,) = diff_catalogs(catalog(BASE), catalog(new))
    assert (change.kind, change.is_pii_risk) == ("column_added", False)


def test_existing_column_becoming_pii_or_changing_type():
    assert kinds(diff_catalogs(catalog(BASE), catalog(BASE, [MAIL]))) == [
        ("pii_added", "t", "mail")
    ]
    phone = Finding("t", "mail", "phone", 1.0, 5)
    (change,) = diff_catalogs(catalog(BASE, [MAIL]), catalog(BASE, [phone]))
    assert (change.kind, change.detail, change.is_pii_risk) == (
        "pii_type_changed",
        "email -> phone",
        True,
    )


def test_pii_disappearing_is_reported_but_not_a_risk():
    (change,) = diff_catalogs(catalog(BASE, [MAIL]), catalog(BASE))
    assert (change.kind, change.is_pii_risk) == ("pii_removed", False)


def test_tables_and_columns_appearing_and_disappearing():
    new = {"other": [("x", "TEXT")]}
    found = [Finding("other", "x", "email", 1.0, 5)]
    changes = diff_catalogs(catalog(BASE, [MAIL]), catalog(new, found))
    assert kinds(changes) == [
        ("table_added", "other", None),
        ("pii_added", "other", "x"),
        ("table_removed", "t", None),
    ]
    removed = diff_catalogs(catalog(BASE), catalog({"t": [("id", "INTEGER")]}))
    assert kinds(removed) == [("column_removed", "t", "mail")]


def test_previous_catalog_picks_the_newest_earlier_run(tmp_path):
    for run in ("2026-10-01", "2026-10-03", "2026-10-05"):
        (tmp_path / run).mkdir()
        (tmp_path / run / "catalog.json").write_text("{}")
    (tmp_path / "2026-10-04").mkdir()  # no catalog.json inside: must be ignored
    assert previous_catalog(tmp_path / "2026-10-05" / "catalog.json") == (
        tmp_path / "2026-10-03" / "catalog.json"
    )
    assert previous_catalog(tmp_path / "2026-10-01" / "catalog.json") is None


def test_load_catalog_rejects_other_json(tmp_path):
    path = tmp_path / "x.json"
    path.write_text(json.dumps([1, 2]))
    with pytest.raises(ValueError, match="not a catalog"):
        load_catalog(path)


# --- the Phase 4 "done" criterion, without Airflow ------------------------------------------


def run_nightly(db_url, contracts, history, run_id):
    """What the DAG does, in order: catalog, diff, check. Returns (diff output, check result)."""
    out = history / run_id
    common = ["--url", db_url, "--dir", str(contracts)]
    policy = ["--policy", str(REPO / "examples" / "policy.yaml")]
    cat = runner.invoke(app, ["catalog", *common, *policy, "--out", str(out)])
    assert cat.exit_code == 0, cat.output
    diff = runner.invoke(app, ["diff", str(out / "catalog.json")])
    assert diff.exit_code == 0, diff.output
    return diff.output, runner.invoke(app, ["check", *common, *policy])


def test_adding_a_pii_column_is_caught_on_the_next_nightly_run(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'source.db'}"
    synthetic.write_database(db_url, synthetic.generate())
    history = tmp_path / "history"

    day1, check1 = run_nightly(db_url, REPO / "examples" / "contracts", history, "2026-10-01")
    assert "baseline" in day1
    assert check1.exit_code == 0, check1.output

    # A developer ships a column full of email addresses and nobody updates the contract.
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("alter table customers add column contact_email text"))
        conn.execute(text("update customers set contact_email = 'person' || id || '@example.com'"))

    day2, check2 = run_nightly(db_url, REPO / "examples" / "contracts", history, "2026-10-02")
    assert "contact_email" in day2 and "pii_added" in day2  # the audit trail says when
    assert check2.exit_code == 1  # the alarm
    assert "undeclared_pii" in check2.output and "customers.contact_email" in check2.output


def test_diff_command_reports_baseline_and_bad_input(tmp_path):
    lone = tmp_path / "2026-10-01" / "catalog.json"
    lone.parent.mkdir()
    lone.write_text(json.dumps({"tables": []}))
    assert "baseline" in runner.invoke(app, ["diff", str(lone)]).output
    lone.write_text("not json")
    assert runner.invoke(app, ["diff", str(lone), str(lone)]).exit_code == 2
