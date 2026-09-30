import pytest
from sqlalchemy import create_engine
from typer.testing import CliRunner

from data_warden import synthetic
from data_warden.cli import app
from data_warden.scan import scan


@pytest.fixture
def db_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'demo.db'}"
    synthetic.write_database(url, synthetic.generate(rows=100))
    return url


def test_finds_the_hidden_email_column(db_url):
    findings = scan(create_engine(db_url))
    email = [f for f in findings if f.pii_type == "email"]
    assert [(f.table, f.column) for f in email] == [("customers", "col7")]
    assert email[0].confidence == 1.0


def test_no_email_false_positives_against_ground_truth(db_url):
    for f in scan(create_engine(db_url)):
        assert synthetic.GROUND_TRUTH[f"{f.table}.{f.column}"] == f.pii_type


def test_impossible_threshold_flags_nothing(db_url):
    assert scan(create_engine(db_url), threshold=1.01) == []


def test_scan_command_prints_finding(db_url):
    result = CliRunner().invoke(app, ["scan", "--url", db_url])
    assert result.exit_code == 0, result.output
    assert "customers.col7" in result.output
    assert "email" in result.output


def test_scan_command_reports_clean_scan(tmp_path):
    url = f"sqlite:///{tmp_path / 'empty.db'}"
    create_engine(url).connect().close()
    result = CliRunner().invoke(app, ["scan", "--url", url])
    assert "No personal data found" in result.output
