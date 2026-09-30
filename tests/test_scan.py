import pytest
from sqlalchemy import create_engine, text
from typer.testing import CliRunner

from data_warden import synthetic
from data_warden.cli import app
from data_warden.scan import scan


@pytest.fixture
def db_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'demo.db'}"
    synthetic.write_database(url, synthetic.generate(rows=100))
    return url


def test_finds_the_hidden_columns(db_url):
    found = {(f.table, f.column): f.pii_type for f in scan(create_engine(db_url))}
    assert found[("customers", "col7")] == "email"
    assert found[("customers", "iban_raw")] == "iban"
    assert found[("employees", "ref_code")] == "national_id"
    assert found[("customers", "phone")] == "phone"
    assert found[("orders", "notes")] == "free_text_pii"


def test_every_finding_matches_the_answer_key(db_url):
    """Precision check: no decoy column may be flagged, and no type may be wrong."""
    for f in scan(create_engine(db_url)):
        assert synthetic.GROUND_TRUTH[f"{f.table}.{f.column}"] == f.pii_type


def test_scan_threshold_only_governs_whole_value_detectors(db_url):
    """An impossible scan-wide threshold silences every detector except free text,
    which deliberately has its own (much lower) bar."""
    findings = scan(create_engine(db_url), threshold=1.01)
    assert [(f.table, f.column, f.pii_type) for f in findings] == [
        ("orders", "notes", "free_text_pii")
    ]


def test_scan_command_prints_findings(db_url):
    result = CliRunner().invoke(app, ["scan", "--url", db_url])
    assert result.exit_code == 0, result.output
    for expected in (
        "customers.col7",
        "customers.iban_raw",
        "customers.phone",
        "orders.notes",
        "employees.ref_code",
    ):
        assert expected in result.output


def test_scan_command_reports_clean_scan(tmp_path):
    url = f"sqlite:///{tmp_path / 'empty.db'}"
    create_engine(url).connect().close()
    result = CliRunner().invoke(app, ["scan", "--url", url])
    assert "No personal data found" in result.output


def test_one_leaking_row_in_twenty_flags_a_free_text_column(tmp_path):
    url = f"sqlite:///{tmp_path / 'notes.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("create table tickets (id integer primary key, body text)"))
        rows = [{"id": i, "body": "all fine"} for i in range(1, 20)]
        rows.append({"id": 20, "body": "reach me at x@y.com"})
        conn.execute(text("insert into tickets values (:id, :body)"), rows)
    findings = scan(engine)
    assert [(f.column, f.pii_type, f.confidence) for f in findings] == [
        ("body", "free_text_pii", 0.05)
    ]


def test_pure_email_column_is_email_not_free_text(tmp_path):
    url = f"sqlite:///{tmp_path / 'mail.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("create table t (id integer primary key, addr text)"))
        conn.execute(
            text("insert into t values (:id, :a)"),
            [{"id": i, "a": f"user{i}@example.com"} for i in range(1, 11)],
        )
    assert [f.pii_type for f in scan(engine)] == ["email"]


def test_a_single_stray_match_does_not_flag_a_text_column(tmp_path):
    url = f"sqlite:///{tmp_path / 'notes.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("create table t (note text)"))
        rows = [{"n": f"entregado sin incidencias {i}"} for i in range(99)]
        rows.append({"n": "llamar al +34 612 345 678"})
        conn.execute(text("insert into t values (:n)"), rows)
    assert scan(engine) == []
