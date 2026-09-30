import pytest

from data_warden.contracts import (
    Contract,
    ContractError,
    contracts_from_findings,
    load_contracts,
    parse_contract,
    render_contract,
    write_missing_contracts,
)
from data_warden.scan import Finding


def test_render_then_load_round_trips(tmp_path):
    original = Contract("customers", "data-team", 365, {"email": "email", "phone": "phone"})
    (tmp_path / "customers.yaml").write_text(render_contract(original))
    assert load_contracts(tmp_path) == {"customers": original}


def test_generated_skeleton_leaves_owner_and_retention_empty():
    findings = [Finding("t", "b", "email", 1.0, 5), Finding("t", "a", "phone", 1.0, 5)]
    (contract,) = contracts_from_findings(findings)
    assert contract == Contract("t", None, None, {"a": "phone", "b": "email"})


def test_existing_contract_files_are_never_overwritten(tmp_path):
    (tmp_path / "t.yaml").write_text("sentinel")
    created, skipped = write_missing_contracts([Contract("t"), Contract("new")], tmp_path)
    assert [p.name for p in created] == ["new.yaml"]
    assert [p.name for p in skipped] == ["t.yaml"]
    assert (tmp_path / "t.yaml").read_text() == "sentinel"


def test_table_names_are_made_safe_for_filenames(tmp_path):
    created, _ = write_missing_contracts([Contract("a/b c")], tmp_path)
    assert created[0].parent == tmp_path


@pytest.mark.parametrize(
    "data",
    [
        "just a string",
        {"owner": "x"},  # no table
        {"table": "t", "retention_day": 5},  # typo must fail loudly
        {"table": "t", "retention_days": 0},
        {"table": "t", "retention_days": True},
        {"table": "t", "retention_days": "30"},
        {"table": "t", "owner": 7},
        {"table": "t", "pii_columns": ["email"]},
        {"table": "t", "pii_columns": {"a": 1}},
    ],
)
def test_malformed_contracts_are_rejected(data):
    with pytest.raises(ContractError):
        parse_contract(data, "file.yaml")


def test_invalid_yaml_and_duplicate_tables_are_rejected(tmp_path):
    (tmp_path / "a.yaml").write_text("table: t\n")
    (tmp_path / "b.yml").write_text("table: t\n")
    with pytest.raises(ContractError, match="twice"):
        load_contracts(tmp_path)
    (tmp_path / "b.yml").write_text("table: [unclosed")
    with pytest.raises(ContractError, match="invalid YAML"):
        load_contracts(tmp_path)
