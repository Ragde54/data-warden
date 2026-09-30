# Nightly governance with plain Apache Airflow

A DAG (a scheduled workflow) that watches one database every night:

```
catalog  ->  diff  ->  check
```

| Task | What it does | Fails the run? |
| --- | --- | --- |
| `catalog` | Scans the live database and writes `catalog.md` and `catalog.json` into a new folder named by the run's start time | only if the database is unreachable (retried twice) |
| `diff` | Lists what changed since the previous run's folder: new tables and columns, new or changed personal data | never |
| `check` | Compares the live database with the data contracts | yes, on any policy error. **This is the alarm** |

The folders under the history volume are the audit trail: they answer *when did this column first
show up*. The alarm needs no stored state, because the contracts are the baseline
([decision 0008](../docs/decisions/0008-airflow.md)).

## Try it

Needs Docker. From this folder:

```bash
docker compose up -d --build
docker compose exec airflow /home/airflow/dw/bin/data-warden seed      # demo data into the watched database
docker compose exec airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated   # login: admin
docker compose exec airflow airflow dags trigger pii_drift
```

Open http://localhost:8080, log in, and open the `pii_drift` DAG. The first run is green: `diff` says
`baseline`, `check` passes with warnings for the person-name columns that rules cannot detect.

Now play the careless developer and add a column full of email addresses:

```bash
docker compose exec source-db psql -U warden demo -c \
  "ALTER TABLE customers ADD COLUMN contact_email text;
   UPDATE customers SET contact_email = 'person' || id || '@example.com';"
docker compose exec airflow airflow dags trigger pii_drift
```

The second run turns red at `check`. Open the task log: it lists `customers.contact_email` as
`undeclared_pii`, and the `diff` log shows `pii_added` for the same column. To make it green again,
declare the column in `examples/contracts/customers.yaml` (`contact_email: email`) and trigger again.

Clean up with `docker compose down -v`.

## Point it at your own database

- Set `DATA_WARDEN_DB_URL` in `docker-compose.yml` (or remove `source-db` and use your own).
- Replace the mounted `examples/contracts` folder with your contracts
  (`data-warden generate-contracts` writes starters).
- The UI is published on `127.0.0.1` only. Keep it that way unless you add real authentication.

## Getting the alert somewhere people will see it

A red DAG run is an alert only if someone looks. Airflow already knows how to tell people, so this
project does not reinvent it: enable `email_on_failure` with SMTP settings, or replace `log_failure`
in `dags/pii_drift.py` with a notifier from your provider package (Slack, Microsoft Teams, PagerDuty).

## Limits of this setup

- `airflow standalone` runs everything in one container with SQLite. It is for learning and demos.
  For production use the official Docker Compose or Helm chart with Postgres and a real executor.
- Run folders are never deleted. Each one is a few kilobytes, but add a retention job if you scan
  hundreds of tables.
- The language-model option (`--llm`) is deliberately not used here: a gate must not change its
  mind between runs.

## Tests

`tests/test_airflow_dag.py` checks the DAG's structure. It is skipped unless Airflow is installed,
because Airflow is not a dependency of the project. The end-to-end behaviour (add a column, get an
alert) is also covered without Airflow by `tests/test_drift.py`.
