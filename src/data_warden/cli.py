"""Command line entry point."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import create_engine

from data_warden import __version__
from data_warden.catalog import build_catalog, render_markdown, to_dict
from data_warden.check import run_checks
from data_warden.contracts import (
    ContractError,
    contracts_from_findings,
    load_contracts,
    write_missing_contracts,
)
from data_warden.evaluate import Report, evaluate, load_ground_truth
from data_warden.introspect import all_columns
from data_warden.llm import DEFAULT_URL as DEFAULT_LLM_URL
from data_warden.llm import LlmError, OllamaClassifier, add_llm_findings
from data_warden.policy import PolicyError, load_policy
from data_warden.scan import DEFAULT_THRESHOLD, scan

app = typer.Typer(help="Find personal data in databases and govern it as code.")

DEFAULT_URL = "postgresql+psycopg://warden:warden@localhost:5432/demo"

UrlOption = Annotated[str, typer.Option(envvar="DATA_WARDEN_DB_URL", help="Database to use.")]


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


@app.command()
def seed(
    url: UrlOption = DEFAULT_URL,
    rows: Annotated[int, typer.Option(help="Number of customers; other tables scale.")] = 200,
    seed_value: Annotated[
        int, typer.Option("--seed", help="Random seed; same seed, same data.")
    ] = 42,
    truth_out: Annotated[Path, typer.Option(help="Where to write the answer key.")] = Path(
        "ground_truth.json"
    ),
) -> None:
    """Load messy demo data into a database and write the answer key."""
    from data_warden import synthetic

    data = synthetic.generate(seed=seed_value, rows=rows)
    synthetic.write_database(url, data)
    synthetic.write_ground_truth(truth_out)
    typer.echo(f"Seeded {sum(len(r) for r in data.values())} rows; answer key: {truth_out}")


LimitOption = Annotated[int, typer.Option(help="Max values sampled per column.")]
ThresholdOption = Annotated[
    float, typer.Option(min=0.0, max=1.0, help="Minimum match share to flag a column.")
]
JsonOption = Annotated[bool, typer.Option("--json", help="Print machine-readable JSON only.")]
LlmOption = Annotated[
    bool,
    typer.Option(
        "--llm", help="Also ask a local model about columns the rules did not flag (slower)."
    ),
]
LlmModelOption = Annotated[
    str | None,
    typer.Option(envvar="DATA_WARDEN_LLM_MODEL", help="Name of a model you have pulled in Ollama."),
]
LlmUrlOption = Annotated[
    str, typer.Option(envvar="DATA_WARDEN_LLM_URL", help="Where Ollama is listening.")
]
AllowRemoteOption = Annotated[
    bool,
    typer.Option(
        "--allow-remote-llm",
        help="Allow a non-local model server. Column values will leave this machine.",
    ),
]


def _with_llm(engine, findings, model, llm_url, allow_remote, limit):
    """Add the local model's findings, or exit with code 2 and a clear message."""
    if not model:
        typer.echo("error: --llm needs --llm-model (or DATA_WARDEN_LLM_MODEL)", err=True)
        raise typer.Exit(2)
    try:
        classifier = OllamaClassifier(model, llm_url, allow_remote=allow_remote)
        merged, unusable = add_llm_findings(engine, findings, classifier, limit=limit)
    except LlmError as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(2) from error
    if unusable:
        typer.echo(f"warning: {unusable} model reply(ies) were unusable and ignored", err=True)
    return merged


@app.command(name="scan")
def scan_command(
    url: UrlOption = DEFAULT_URL,
    limit: LimitOption = 1000,
    threshold: ThresholdOption = DEFAULT_THRESHOLD,
    as_json: JsonOption = False,
    llm: LlmOption = False,
    llm_model: LlmModelOption = None,
    llm_url: LlmUrlOption = DEFAULT_LLM_URL,
    allow_remote_llm: AllowRemoteOption = False,
) -> None:
    """Scan a database and list columns that look like personal data."""
    engine = create_engine(url)
    findings = scan(engine, limit=limit, threshold=threshold)
    if llm:
        findings = _with_llm(engine, findings, llm_model, llm_url, allow_remote_llm, limit)
    if as_json:
        typer.echo(json.dumps([asdict(f) for f in findings], indent=2))
        return
    if not findings:
        typer.echo(
            f"No personal data found at threshold {threshold:.0%}. "
            "A clean scan is evidence, not proof."
        )
        return
    typer.echo(f"{'COLUMN':<28}{'TYPE':<16}{'CONFIDENCE':<12}{'SOURCE':<8}SAMPLES")
    for f in findings:
        typer.echo(
            f"{f.table + '.' + f.column:<28}{f.pii_type:<16}{f.confidence:<12.0%}"
            f"{f.source:<8}{f.sample_size}"
        )


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def _report_to_dict(report: Report) -> dict:
    rows = [*report.by_type, report.overall]
    return {
        "unlabeled": report.unlabeled,
        "scores": [
            {
                "type": s.pii_type,
                "tp": s.tp,
                "fp": s.fp,
                "fn": s.fn,
                "precision": s.precision,
                "recall": s.recall,
            }
            for s in rows
        ],
    }


def _print_report(report: Report) -> None:
    typer.echo(f"{'TYPE':<16}{'TP':>4}{'FP':>4}{'FN':>4}  {'PRECISION':<11}RECALL")
    for s in [*report.by_type, report.overall]:
        typer.echo(
            f"{s.pii_type:<16}{s.tp:>4}{s.fp:>4}{s.fn:>4}  "
            f"{_percent(s.precision):<11}{_percent(s.recall)}"
        )
    if report.unlabeled:
        typer.echo(
            f"\n{report.unlabeled} flagged column(s) are not in the answer key and were ignored."
        )


@app.command(name="evaluate")
def evaluate_command(
    url: UrlOption = DEFAULT_URL,
    truth: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, help="Answer key written by `seed`."),
    ] = Path("ground_truth.json"),
    limit: LimitOption = 1000,
    threshold: ThresholdOption = DEFAULT_THRESHOLD,
    as_json: JsonOption = False,
    llm: LlmOption = False,
    llm_model: LlmModelOption = None,
    llm_url: LlmUrlOption = DEFAULT_LLM_URL,
    allow_remote_llm: AllowRemoteOption = False,
) -> None:
    """Score the scanner against an answer key (precision and recall per PII type).

    With --llm, prints rules alone and rules plus the local model, so the gain (or the damage)
    is visible side by side.
    """
    engine = create_engine(url)
    answer_key = load_ground_truth(truth)
    findings = scan(engine, limit=limit, threshold=threshold)
    rules_report = evaluate(findings, answer_key)
    if not llm:
        if as_json:
            typer.echo(json.dumps(_report_to_dict(rules_report), indent=2))
        else:
            _print_report(rules_report)
        return
    combined = _with_llm(engine, findings, llm_model, llm_url, allow_remote_llm, limit)
    llm_report = evaluate(combined, answer_key)
    if as_json:
        payload = {
            "rules": _report_to_dict(rules_report),
            "rules_and_llm": _report_to_dict(llm_report),
        }
        typer.echo(json.dumps(payload, indent=2))
        return
    typer.echo("RULES ONLY")
    _print_report(rules_report)
    typer.echo("\nRULES + LLM")
    _print_report(llm_report)


ContractsDirOption = Annotated[
    Path, typer.Option("--dir", help="Folder holding one contract file per table.")
]


@app.command(name="generate-contracts")
def generate_contracts_command(
    url: UrlOption = DEFAULT_URL,
    directory: ContractsDirOption = Path("contracts"),
    limit: LimitOption = 1000,
    threshold: ThresholdOption = DEFAULT_THRESHOLD,
) -> None:
    """Write a starter contract for every table with personal data. Never overwrites files."""
    findings = scan(create_engine(url), limit=limit, threshold=threshold)
    created, skipped = write_missing_contracts(contracts_from_findings(findings), directory)
    for path in created:
        typer.echo(f"created  {path}")
    for path in skipped:
        typer.echo(f"exists   {path} (left untouched)")
    if created:
        typer.echo("Fill in owner and retention_days in each file, then run `data-warden check`.")
    elif not skipped:
        typer.echo("No personal data found; no contracts needed.")


@app.command(name="check")
def check_command(
    url: UrlOption = DEFAULT_URL,
    directory: Annotated[
        Path,
        typer.Option("--dir", exists=True, file_okay=False, help="Folder with contract files."),
    ] = Path("contracts"),
    policy_file: Annotated[
        Path | None,
        typer.Option("--policy", exists=True, dir_okay=False, help="Policy file (optional)."),
    ] = None,
    limit: LimitOption = 1000,
    threshold: ThresholdOption = DEFAULT_THRESHOLD,
    as_json: JsonOption = False,
) -> None:
    """Fail (exit code 1) when the scan and the contracts disagree. Exit code 2: bad input."""
    try:
        contracts = load_contracts(directory)
        policy = load_policy(policy_file)
    except (ContractError, PolicyError) as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(2) from error
    findings = scan(create_engine(url), limit=limit, threshold=threshold)
    violations = run_checks(findings, contracts, policy)
    errors = sum(v.severity == "error" for v in violations)
    warnings = len(violations) - errors
    if as_json:
        typer.echo(
            json.dumps(
                {
                    "errors": errors,
                    "warnings": warnings,
                    "violations": [asdict(v) for v in violations],
                },
                indent=2,
            )
        )
    else:
        for v in violations:
            where = v.table if v.column is None else f"{v.table}.{v.column}"
            typer.echo(f"{v.severity.upper():<9}{where:<26}{v.rule:<24}{v.message}")
        verdict = "FAILED" if errors else "passed"
        typer.echo(f"\ncheck {verdict}: {errors} error(s), {warnings} warning(s)")
    if errors:
        raise typer.Exit(1)


@app.command(name="catalog")
def catalog_command(
    url: UrlOption = DEFAULT_URL,
    directory: Annotated[
        Path,
        typer.Option("--dir", exists=True, file_okay=False, help="Folder with contract files."),
    ] = Path("contracts"),
    out: Annotated[Path, typer.Option(help="Folder for catalog.md and catalog.json.")] = Path(
        "catalog"
    ),
    policy_file: Annotated[
        Path | None,
        typer.Option("--policy", exists=True, dir_okay=False, help="Policy file (optional)."),
    ] = None,
    limit: LimitOption = 1000,
    threshold: ThresholdOption = DEFAULT_THRESHOLD,
) -> None:
    """Write a readable catalog (catalog.md) and a machine-readable one (catalog.json).

    The catalog documents; it never fails on violations. Use `check` as the gate.
    """
    try:
        contracts = load_contracts(directory)
        policy = load_policy(policy_file)
    except (ContractError, PolicyError) as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(2) from error
    engine = create_engine(url)
    findings = scan(engine, limit=limit, threshold=threshold)
    violations = run_checks(findings, contracts, policy)
    catalog = build_catalog(all_columns(engine), findings, contracts, violations)
    out.mkdir(parents=True, exist_ok=True)
    (out / "catalog.md").write_text(render_markdown(catalog), encoding="utf-8")
    (out / "catalog.json").write_text(
        json.dumps(to_dict(catalog), indent=2) + "\n", encoding="utf-8"
    )
    typer.echo(f"wrote {out / 'catalog.md'} and {out / 'catalog.json'}")
