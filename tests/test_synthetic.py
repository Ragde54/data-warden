import json
import re

from sqlalchemy import create_engine, text
from typer.testing import CliRunner

from data_warden import __version__, synthetic
from data_warden.cli import app

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def test_generation_is_deterministic():
    assert synthetic.generate(seed=1, rows=20) == synthetic.generate(seed=1, rows=20)


def test_ground_truth_covers_every_column():
    data = synthetic.generate(rows=10)
    columns = {f"{table}.{col}" for table, rows in data.items() for col in rows[0]}
    assert columns == set(synthetic.GROUND_TRUTH)


def test_hidden_email_column_really_holds_emails():
    customers = synthetic.generate(rows=30)["customers"]
    assert all(EMAIL.match(row["col7"]) for row in customers)


def test_dni_check_letter_is_valid():
    for row in synthetic.generate(rows=50)["employees"]:
        number, letter = int(row["ref_code"][:-1]), row["ref_code"][-1]
        assert synthetic.DNI_LETTERS[number % 23] == letter


def test_seed_command_writes_database_and_answer_key(tmp_path):
    db = tmp_path / "demo.db"
    truth = tmp_path / "truth.json"
    result = CliRunner().invoke(
        app, ["seed", "--url", f"sqlite:///{db}", "--rows", "10", "--truth-out", str(truth)]
    )
    assert result.exit_code == 0, result.output
    with create_engine(f"sqlite:///{db}").connect() as conn:
        assert conn.execute(text("select count(*) from customers")).scalar() == 10
    assert json.loads(truth.read_text())["customers.col7"] == "email"


def test_version_command():
    result = CliRunner().invoke(app, ["version"])
    assert result.output.strip() == __version__
