"""Nightly personal-data governance for one database, using plain Apache Airflow.

catalog -> diff -> check

- catalog: scan the live database and write <history>/<run time>/catalog.json and catalog.md.
  Every run keeps its own folder, so the folders are the audit trail.
- diff:    what changed since the previous run (informational, never fails).
- check:   the alarm. Fails the run when the live database and the data contracts disagree,
  for example when someone adds a column full of email addresses and nobody declares it.

data-warden runs from its own virtualenv (DATA_WARDEN_BIN) so its dependencies never touch
Airflow's. The language-model option is deliberately not used here: a gate must not change
its mind between runs.
"""

from __future__ import annotations

import logging
import os
import shlex
from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

# Paths come from the environment so the same file works in Docker and in tests.
DW = shlex.quote(os.environ.get("DATA_WARDEN_BIN", "/home/airflow/dw/bin/data-warden"))
HISTORY = os.environ.get("DATA_WARDEN_HISTORY", "/opt/airflow/history")
CONTRACTS = shlex.quote(os.environ.get("DATA_WARDEN_CONTRACTS", "/opt/airflow/contracts"))
POLICY = shlex.quote(os.environ.get("DATA_WARDEN_POLICY", "/opt/airflow/policy.yaml"))

# One folder per DAG run, named by the run's start time. It sorts as plain text, is identical for
# every task and retry of the same run, and exists for manual runs too (they have no logical date).
RUN_DIR = HISTORY + "/{{ dag_run.start_date.strftime('%Y-%m-%dT%H%M%SZ') }}"

log = logging.getLogger(__name__)


def log_failure(context) -> None:
    """Failure hook: a loud line in the logs. Send it further with an Airflow notifier.

    Email and chat alerts are Airflow's job, not data-warden's: configure `email_on_failure` or
    swap this function for a notifier from your provider package (Slack, Teams, PagerDuty...).
    """
    ti = context["task_instance"]
    log.error(
        "data-warden: task %r failed in DAG %r, run %r. Read this task's log for the violations.",
        ti.task_id,
        ti.dag_id,
        context.get("run_id", "?"),
    )


with DAG(
    dag_id="pii_drift",
    description="Nightly scan for personal data, change report, and contract check.",
    schedule="0 3 * * *",
    start_date=datetime(2026, 1, 1),  # in the past on purpose; catchup=False means no backfill
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(hours=1),
    default_args={"retries": 0, "on_failure_callback": log_failure},
    tags=["governance", "pii"],
    doc_md=__doc__,
) as dag:
    catalog = BashOperator(
        task_id="catalog",
        bash_command=f'{DW} catalog --dir {CONTRACTS} --policy {POLICY} --out "{RUN_DIR}"',
        retries=2,  # the database may be briefly unavailable; a governance failure is not retried
        retry_delay=timedelta(minutes=5),
    )
    diff = BashOperator(
        task_id="diff",
        bash_command=f'{DW} diff "{RUN_DIR}/catalog.json"',
    )
    check = BashOperator(
        task_id="check",
        bash_command=f"{DW} check --dir {CONTRACTS} --policy {POLICY}",
    )

    catalog >> diff >> check
