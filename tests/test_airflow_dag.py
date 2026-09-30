"""Structure checks for the Airflow DAG. Skipped unless Airflow is installed.

Airflow is deliberately not a dependency of this project. To run these, use an environment that
has it, for example:  docker compose -f airflow/docker-compose.yml exec airflow pytest
"""

from pathlib import Path

import pytest

pytest.importorskip("airflow")

from airflow.models import DagBag  # noqa: E402

DAGS = Path(__file__).resolve().parent.parent / "airflow" / "dags"


@pytest.fixture(scope="module")
def dag():
    bag = DagBag(dag_folder=str(DAGS))
    assert bag.import_errors == {}
    return bag.get_dag("pii_drift")


def test_tasks_run_in_order(dag):
    assert [t.task_id for t in dag.topological_sort()] == ["catalog", "diff", "check"]


def test_schedule_is_nightly_and_does_not_backfill(dag):
    assert dag.catchup is False
    assert dag.max_active_runs == 1


def test_governance_check_is_never_retried(dag):
    assert dag.get_task("check").retries == 0
    assert dag.get_task("catalog").retries == 2


def test_no_task_uses_the_language_model(dag):
    commands = " ".join(t.bash_command for t in dag.tasks)
    assert "--llm" not in commands
