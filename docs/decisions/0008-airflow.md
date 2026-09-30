# 0008: Nightly runs on plain Apache Airflow

Status: accepted. The DAG was run end to end with Airflow 3.3.2 (catalog, diff, check, including a
failing day). The Docker image and compose file are written to the same commands but were not
built in the environment where this was developed.

- **Plain Airflow, no vendor distribution.** The official `apache/airflow` image, a DAG file, and
  a compose file. Anyone with Docker can run it, and nothing in it is tied to a platform.
- **`airflow standalone`, not the multi-service compose.** One container, SQLite, one process.
  Cost: it is not production-grade, and the README says so. Benefit: a reader can run the demo
  in minutes, and the DAG file is identical on a real cluster.
- **data-warden lives in its own virtualenv, called through `BashOperator`.** Airflow pins its
  dependencies tightly, and a tool that shares its environment inherits those pins (and can
  break Airflow when it upgrades). With a separate venv, each upgrades on its own. Cost: one more
  venv in the image, and commands instead of Python calls. The CLI's exit codes map directly onto
  task success and failure.
- **The alarm is `check`, not a snapshot diff.** `check` compares the live database with the
  contracts, needs no stored state, and encodes a judgement (this PII is acceptable, that is
  not). A plain before/after diff cannot know whether a change is acceptable, and storing the
  previous state adds something to keep consistent.
- **`diff` is the audit trail.** Every run writes `<history>/<run time>/catalog.json`, and `diff`
  compares with the newest earlier folder. It is informational and never fails. The previous
  folder is "the latest earlier one", not "yesterday", so skipped days and manual runs still work.
- **Run folders are named by the DAG run's start time, not by `ds`.** In Airflow 3 a manual run can
  have no logical date, so `ds` may be missing. The start time exists for every run, is the same for
  every task and retry of that run, and sorts as plain text.
- **`start_date` is in the past on purpose.** In testing, a start date a few minutes in the future
  made a manual trigger create a run with no tasks, silently. `catchup=False` prevents backfilling.
- **`check` is not retried, `catalog` is.** A database that is briefly down deserves a retry. A
  governance failure does not get better by trying again.
- **Alert delivery is left to Airflow.** Email and chat notifiers already exist there. The DAG
  ships a failure hook that writes a loud log line and is the place to plug one in.
- **No language model in the DAG.** Same reason as the gate: a nightly control that can disagree
  with itself between runs gets ignored.
- **Testing:** `tests/test_airflow_dag.py` needs Airflow and a migrated metadata database, so it
  is skipped in the normal suite. `tests/test_drift.py` reproduces the whole scenario (run, add a
  column, run again) with the same commands and needs only this project.
