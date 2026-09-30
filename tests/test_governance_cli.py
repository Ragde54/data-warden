import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from data_warden import synthetic
from data_warden.cli import app

runner = CliRunner()
REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def db_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'demo.db'}"
    synthetic.write_database(url, synthetic.generate(rows=100))
    return url


def edit(path, **changes):
    data = yaml.safe_load(path.read_text())
    data.update(changes)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def test_full_workflow_generate_fail_fill_pass(db_url, tmp_path):
    contracts = tmp_path / "contracts"
    result = runner.invoke(app, ["generate-contracts", "--url", db_url, "--dir", str(contracts)])
    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in contracts.iterdir()) == [
        "customers.yaml",
        "employees.yaml",
        "orders.yaml",
    ]

    # Fresh skeletons have no owner or retention, so the check must fail.
    failing = runner.invoke(app, ["check", "--url", db_url, "--dir", str(contracts)])
    assert failing.exit_code == 1
    assert "missing_field" in failing.output

    for path in contracts.iterdir():
        edit(path, owner="team", retention_days=365)
    customers = contracts / "customers.yaml"
    data = yaml.safe_load(customers.read_text())
    data["pii_columns"]["full_name"] = "person_name"
    edit(customers, pii_columns=data["pii_columns"])

    passing = runner.invoke(app, ["check", "--url", db_url, "--dir", str(contracts)])
    assert passing.exit_code == 0, passing.output
    assert "declared_not_detected" in passing.output  # names: declared by a human, not detected


def test_check_fails_when_a_pii_column_is_no_longer_declared(db_url):
    contracts = REPO / "examples" / "contracts"
    # Same contracts, but the scanner sees data the contract does not know about.
    customers = yaml.safe_load((contracts / "customers.yaml").read_text())
    assert "col7" in customers["pii_columns"]
    del customers["pii_columns"]["col7"]
    copy = Path(db_url.removeprefix("sqlite:///")).parent / "contracts"
    copy.mkdir()
    for path in contracts.iterdir():
        (copy / path.name).write_text(path.read_text())
    (copy / "customers.yaml").write_text(yaml.safe_dump(customers, sort_keys=False))
    result = runner.invoke(app, ["check", "--url", db_url, "--dir", str(copy), "--json"])
    assert result.exit_code == 1
    report = json.loads(result.output)
    assert report["errors"] == 1
    assert report["violations"][0]["rule"] == "undeclared_pii"
    assert report["violations"][0]["column"] == "col7"


def test_repository_example_contracts_pass_on_demo_data(tmp_path):
    """The contracts shipped in examples/ must stay valid; CI runs the same check."""
    url = f"sqlite:///{tmp_path / 'demo.db'}"
    synthetic.write_database(url, synthetic.generate())
    args = ["check", "--url", url, "--dir", str(REPO / "examples" / "contracts")]
    policy = REPO / "examples" / "policy.yaml"
    result = runner.invoke(app, [*args, "--policy", str(policy)])
    assert result.exit_code == 0, result.output


def test_bad_contract_is_exit_code_2_not_a_crash(db_url, tmp_path):
    (tmp_path / "bad.yaml").write_text("table: t\nretention_day: 5\n")
    result = runner.invoke(app, ["check", "--url", db_url, "--dir", str(tmp_path)])
    assert result.exit_code == 2
    assert "unknown field" in result.output


def test_generate_contracts_reports_nothing_to_do(tmp_path):
    from sqlalchemy import create_engine

    url = f"sqlite:///{tmp_path / 'empty.db'}"
    create_engine(url).connect().close()
    result = runner.invoke(app, ["generate-contracts", "--url", url, "--dir", str(tmp_path / "c")])
    assert "No personal data found" in result.output
