import pytest
from sqlalchemy import create_engine
from typer.testing import CliRunner

from data_warden import synthetic
from data_warden.cli import app
from data_warden.evaluate import evaluate
from data_warden.llm import LlmResponseError, add_llm_findings
from data_warden.scan import Finding, scan

runner = CliRunner()


class FakeClassifier:
    """Stands in for a model. `rule(table, column, samples)` returns a label, None, or raises."""

    def __init__(self, rule):
        self.rule = rule
        self.calls = []

    def classify(self, table, column, samples):
        self.calls.append((table, column, list(samples)))
        return self.rule(table, column, samples)


NAME_COLUMNS = ("full_name", "billing_name", "first_name")
DECOY_COLUMNS = ("company_name", "product_name", "carrier", "warehouse")


def says_name_for(*columns):
    return FakeClassifier(lambda t, c, s: "person_name" if c in columns else None)


@pytest.fixture
def engine(tmp_path):
    url = f"sqlite:///{tmp_path / 'demo.db'}"
    synthetic.write_database(url, synthetic.generate(rows=100))
    return create_engine(url)


def test_model_is_never_asked_about_columns_the_rules_already_flagged(engine):
    fake = says_name_for("full_name")
    add_llm_findings(engine, scan(engine), fake)
    asked = {(t, c) for t, c, _ in fake.calls}
    assert ("customers", "col7") not in asked
    assert ("orders", "notes") not in asked
    assert ("customers", "full_name") in asked


def test_model_findings_are_marked_and_merged(engine):
    rules = scan(engine)
    merged, unusable = add_llm_findings(engine, rules, says_name_for("full_name"))
    added = [f for f in merged if f.source == "llm"]
    assert [(f.table, f.column, f.pii_type, f.confidence) for f in added] == [
        ("customers", "full_name", "person_name", 1.0)
    ]
    assert unusable == 0
    assert all(f.source == "rules" for f in rules)  # the input list is not modified
    assert len(merged) == len(rules) + 1


def test_at_most_fifteen_distinct_values_per_column_leave_the_database(engine):
    fake = says_name_for()
    add_llm_findings(engine, [], fake, per_vote=5, votes=3)
    per_column: dict = {}
    for table, column, samples in fake.calls:
        assert len(samples) <= 5
        assert len(set(samples)) == len(samples)
        per_column.setdefault((table, column), []).extend(samples)
    assert all(len(values) <= 15 for values in per_column.values())
    assert all(len(set(values)) == len(values) for values in per_column.values())


def test_agreement_threshold_decides_whether_a_column_is_flagged(engine):
    def votes(n_yes):
        counter = {"seen": 0}

        def rule(table, column, samples):
            if column != "full_name":
                return None
            counter["seen"] += 1
            return "person_name" if counter["seen"] <= n_yes else None

        return FakeClassifier(rule)

    two_of_three, _ = add_llm_findings(engine, [], votes(2))
    assert [(f.column, round(f.confidence, 2)) for f in two_of_three if f.source == "llm"] == [
        ("full_name", 0.67)
    ]
    one_of_three, _ = add_llm_findings(engine, [], votes(1))
    assert not [f for f in one_of_three if f.source == "llm"]


def test_unusable_replies_are_counted_and_do_not_count_as_agreement(engine):
    def rule(table, column, samples):
        if column == "full_name":
            raise LlmResponseError("garbage")

    merged, unusable = add_llm_findings(engine, [], FakeClassifier(rule))
    assert unusable == 3
    assert not [f for f in merged if f.source == "llm"]


def test_columns_without_values_are_skipped(engine):
    fake = says_name_for()
    add_llm_findings(engine, [Finding("x", "y", "email", 1.0, 1)], fake)
    assert all(samples for _, _, samples in fake.calls)


def test_a_perfect_model_closes_the_name_gap(engine):
    merged, _ = add_llm_findings(engine, scan(engine), says_name_for(*NAME_COLUMNS))
    report = evaluate(merged, synthetic.GROUND_TRUTH)
    scores = {s.pii_type: s for s in report.by_type}
    assert scores["person_name"].recall == 1.0
    assert report.overall.fp == 0


def test_a_model_that_misses_one_name_shape_loses_recall(engine):
    merged, _ = add_llm_findings(engine, scan(engine), says_name_for("full_name", "first_name"))
    person = {s.pii_type: s for s in evaluate(merged, synthetic.GROUND_TRUTH).by_type}[
        "person_name"
    ]
    assert person.recall == pytest.approx(2 / 3)
    assert person.precision == 1.0


def test_evaluation_punishes_a_model_fooled_by_lookalike_columns(engine):
    """The decoys exist for this: companies, products, carriers and sites read like surnames."""
    fooled = says_name_for(*NAME_COLUMNS, *DECOY_COLUMNS)
    merged, _ = add_llm_findings(engine, scan(engine), fooled)
    report = evaluate(merged, synthetic.GROUND_TRUTH)
    person = {s.pii_type: s for s in report.by_type}["person_name"]
    assert person.fp == 4
    assert person.precision == pytest.approx(3 / 7)


# --- command line -------------------------------------------------------------------------


@pytest.fixture
def db_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'cli.db'}"
    synthetic.write_database(url, synthetic.generate(rows=100))
    return url


@pytest.fixture
def fake_model(monkeypatch):
    fake = says_name_for(*NAME_COLUMNS)
    monkeypatch.setattr("data_warden.cli.OllamaClassifier", lambda *a, **k: fake)
    return fake


def test_scan_with_llm_shows_the_source_column(db_url, fake_model):
    result = runner.invoke(app, ["scan", "--url", db_url, "--llm", "--llm-model", "m"])
    assert result.exit_code == 0, result.output
    line = next(ln for ln in result.output.splitlines() if "customers.full_name" in ln)
    assert "person_name" in line and "llm" in line


def test_evaluate_with_llm_prints_both_reports(db_url, fake_model, tmp_path):
    truth = tmp_path / "truth.json"
    synthetic.write_ground_truth(truth)
    args = ["evaluate", "--url", db_url, "--truth", str(truth), "--llm", "--llm-model", "m"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert result.output.index("RULES ONLY") < result.output.index("RULES + LLM")
    import json

    data = json.loads(runner.invoke(app, [*args, "--json"]).output)
    before = {s["type"]: s["recall"] for s in data["rules"]["scores"]}
    after = {s["type"]: s["recall"] for s in data["rules_and_llm"]["scores"]}
    assert before["person_name"] == 0.0 and after["person_name"] == 1.0


def test_llm_flag_without_a_model_name_is_a_clear_error(db_url):
    result = runner.invoke(app, ["scan", "--url", db_url, "--llm"])
    assert result.exit_code == 2
    assert "--llm-model" in result.output


def test_remote_model_url_is_refused_by_default(db_url):
    args = ["scan", "--url", db_url, "--llm", "--llm-model", "m", "--llm-url", "http://example.com"]
    result = runner.invoke(app, args)
    assert result.exit_code == 2
    assert "not a local address" in result.output
