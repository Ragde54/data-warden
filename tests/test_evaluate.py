import json

import pytest
from sqlalchemy import create_engine
from typer.testing import CliRunner

from data_warden import synthetic
from data_warden.cli import app
from data_warden.evaluate import evaluate
from data_warden.scan import Finding, scan


def finding(column, pii_type, table="t"):
    return Finding(table, column, pii_type, 1.0, 10)


def by_type(report):
    return {s.pii_type: s for s in report.by_type}


def test_perfect_scan():
    truth = {"t.a": "email", "t.b": None, "t.c": "phone"}
    report = evaluate([finding("a", "email"), finding("c", "phone")], truth)
    assert report.overall.precision == 1.0
    assert report.overall.recall == 1.0


def test_missed_column_hurts_recall_not_precision():
    truth = {"t.a": "email", "t.b": "email"}
    score = by_type(evaluate([finding("a", "email")], truth))["email"]
    assert (score.tp, score.fp, score.fn) == (1, 0, 1)
    assert score.precision == 1.0
    assert score.recall == 0.5


def test_flagging_a_decoy_hurts_precision_not_recall():
    truth = {"t.a": "email", "t.decoy": None}
    score = by_type(evaluate([finding("a", "email"), finding("decoy", "email")], truth))["email"]
    assert (score.tp, score.fp, score.fn) == (1, 1, 0)
    assert score.precision == 0.5
    assert score.recall == 1.0


def test_wrong_type_counts_as_a_miss_and_a_false_alarm():
    report = evaluate([finding("a", "phone")], {"t.a": "email"})
    scores = by_type(report)
    assert (scores["email"].tp, scores["email"].fn) == (0, 1)
    assert (scores["phone"].tp, scores["phone"].fp) == (0, 1)


def test_type_never_predicted_has_no_precision_but_zero_recall():
    score = by_type(evaluate([], {"t.name": "person_name"}))["person_name"]
    assert score.precision is None
    assert score.recall == 0.0


def test_columns_missing_from_the_key_are_ignored_and_counted():
    report = evaluate([finding("a", "email"), finding("mystery", "email")], {"t.a": "email"})
    assert report.unlabeled == 1
    assert report.overall.fp == 0


@pytest.fixture
def db_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'demo.db'}"
    synthetic.write_database(url, synthetic.generate(rows=100))
    return url


def test_demo_data_has_no_false_alarms_and_misses_only_names(db_url):
    """Regression guard for the README numbers. Names are the known, documented gap."""
    report = evaluate(scan(create_engine(db_url)), synthetic.GROUND_TRUTH)
    scores = by_type(report)
    assert report.overall.fp == 0
    assert [t for t, s in scores.items() if s.fn] == ["person_name"]
    assert scores["person_name"].recall == 0.0


def test_scan_json_output_is_valid_json(db_url):
    result = CliRunner().invoke(app, ["scan", "--url", db_url, "--json"])
    assert result.exit_code == 0, result.output
    columns = {(row["table"], row["column"]): row["pii_type"] for row in json.loads(result.output)}
    assert columns[("customers", "col7")] == "email"


def test_evaluate_command_prints_table_and_json(db_url, tmp_path):
    truth = tmp_path / "truth.json"
    synthetic.write_ground_truth(truth)
    args = ["evaluate", "--url", db_url, "--truth", str(truth)]
    table = CliRunner().invoke(app, args)
    assert table.exit_code == 0, table.output
    assert "person_name" in table.output
    assert "overall" in table.output
    data = json.loads(CliRunner().invoke(app, [*args, "--json"]).output)
    assert data["scores"][-1]["type"] == "overall"


def test_evaluate_command_fails_clearly_without_answer_key(db_url, tmp_path):
    result = CliRunner().invoke(app, ["evaluate", "--url", db_url, "--truth", str(tmp_path / "x")])
    assert result.exit_code != 0
