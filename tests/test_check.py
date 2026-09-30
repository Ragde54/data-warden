import pytest

from data_warden.check import run_checks
from data_warden.contracts import Contract
from data_warden.policy import Policy, PolicyError, load_policy
from data_warden.scan import Finding


def finding(column, pii_type="email", table="t"):
    return Finding(table, column, pii_type, 1.0, 10)


def good(**overrides):
    base = {"owner": "team", "retention_days": 30, "pii_columns": {"a": "email"}}
    return Contract("t", **{**base, **overrides})


def rules(violations):
    return [(v.severity, v.rule) for v in violations]


def test_matching_scan_and_contract_is_clean():
    assert run_checks([finding("a")], {"t": good()}, Policy()) == []


def test_table_without_contract_is_an_error():
    assert rules(run_checks([finding("a")], {}, Policy())) == [("error", "missing_contract")]


def test_undeclared_pii_column_is_an_error():
    found = [finding("a"), finding("b", "phone")]
    violations = run_checks(found, {"t": good()}, Policy())
    assert rules(violations) == [("error", "undeclared_pii")]
    assert violations[0].column == "b"


def test_wrong_declared_type_is_an_error():
    violations = run_checks([finding("a", "phone")], {"t": good()}, Policy())
    assert rules(violations) == [("error", "pii_type_mismatch")]


def test_declared_but_undetected_is_only_a_warning():
    contract = good(pii_columns={"a": "email", "name": "person_name"})
    assert rules(run_checks([finding("a")], {"t": contract}, Policy())) == [
        ("warning", "declared_not_detected")
    ]


@pytest.mark.parametrize("missing", ["owner", "retention_days"])
def test_required_fields_are_enforced(missing):
    violations = run_checks([finding("a")], {"t": good(**{missing: None})}, Policy())
    assert rules(violations) == [("error", "missing_field")]
    assert missing in violations[0].message


def test_policy_can_relax_required_fields():
    contract = good(retention_days=None)
    assert run_checks([finding("a")], {"t": contract}, Policy(("owner",))) == []


def test_tables_without_personal_data_need_no_contract():
    assert run_checks([], {}, Policy()) == []
    assert run_checks([], {"t": Contract("t")}, Policy()) == []


def test_errors_sort_before_warnings():
    contract = good(owner=None, pii_columns={"a": "email", "name": "person_name"})
    order = [v.severity for v in run_checks([finding("a")], {"t": contract}, Policy())]
    assert order == ["error", "warning"]


def test_policy_file_loading(tmp_path):
    assert load_policy(None) == Policy()
    path = tmp_path / "policy.yaml"
    path.write_text("pii_tables_require: [owner]\n")
    assert load_policy(path) == Policy(("owner",))
    path.write_text("pii_tables_require: [salary]\n")
    with pytest.raises(PolicyError):
        load_policy(path)
    path.write_text("something_else: 1\n")
    with pytest.raises(PolicyError):
        load_policy(path)
