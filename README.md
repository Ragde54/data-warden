# data-warden

Scan databases for personal data (PII, personally identifiable information), generate a catalog
and data contracts, and fail the build when governance policies are broken.

> Status: Phase 1 in progress. Detection works for emails, IBANs, Spanish national IDs, phone
> numbers, and personal data embedded in free text. Person names are not detected yet.

## Why

Personal data hides behind bad column names. Rules that live in a wiki get ignored; rules that
fail a pull request do not.

## Quickstart

```bash
uv sync
docker compose up -d postgres
uv run data-warden seed          # loads messy demo data, writes ground_truth.json
uv run data-warden scan          # lists columns that look like personal data
uv run pytest
```

Example output:

```
COLUMN                      TYPE            CONFIDENCE  SAMPLES
customers.col7              email           100%        200
customers.iban_raw          iban            100%        200
customers.phone             phone           100%        200
employees.ref_code          national_id     100%        20
orders.notes                free_text_pii   18%         400
```

For `free_text_pii`, the percentage is the share of rows that contain personal data, and the bar
to be flagged is much lower (5%) than for whole-value types (80%): one leaking row in twenty is
already a leak.

Detection is based on values, not column names: `col7` is found because its contents are emails.
Validators check real structure where it exists (IBAN checksum, DNI/NIE check letter).

## Known limitations

- Only text columns are scanned, and values are sampled with `LIMIT`, not randomly
  ([decision 0002](docs/decisions/0002-sampling.md)). A clean scan is evidence, not proof.
- Rules cannot recognize person names. That is what the LLM (large language model) phase is for.
- Results above come from synthetic data. Precision and recall metrics are coming with `evaluate`.

## Roadmap

- [x] Phase 0: skeleton, CI, messy demo data with an answer key
- [ ] Phase 1: detection core with precision/recall metrics (detectors done except free text)
- [ ] Phase 2: catalog, data contracts, policy checks
- [ ] Phase 3: local LLM second opinion
- [ ] Phase 4: Airflow scheduling and drift alerts
- [ ] Phase 5: Terraform deployment on Azure

Design decisions live in [`docs/decisions/`](docs/decisions/).
