# data-warden

Scan databases for personal data (PII, personally identifiable information), generate a catalog
and data contracts, and fail the build when governance policies are broken.

> Status: Phase 1 done (detection and evaluation). Next: catalog, data contracts and policy checks.

## Why

Personal data hides behind bad column names. Rules that live in a wiki get ignored; rules that
fail a pull request do not.

## Quickstart

```bash
uv sync
docker compose up -d postgres
uv run data-warden seed          # loads messy demo data, writes ground_truth.json
uv run data-warden scan          # lists columns that look like personal data
uv run data-warden scan --json   # same, machine-readable
uv run data-warden evaluate      # scores the scan against the answer key
uv run pytest
```

Example `scan` output:

```
COLUMN                      TYPE            CONFIDENCE  SAMPLES
customers.col7              email           100%        200
customers.iban_raw          iban            100%        200
customers.phone             phone           100%        200
employees.ref_code          national_id     100%        20
orders.notes                free_text_pii   18%         400
```

Detection is based on values, not column names: `col7` is found because its contents are emails.
Validators check real structure where it exists (IBAN checksum, DNI/NIE check letter).
For `free_text_pii`, confidence is the share of values that *contain* personal data, which is why
it is much lower ([decision 0003](docs/decisions/0003-free-text.md)).

## Results on the demo data

```
TYPE              TP  FP  FN  PRECISION  RECALL
email              1   0   0  100%       100%
free_text_pii      1   0   0  100%       100%
iban               1   0   0  100%       100%
national_id        1   0   0  100%       100%
person_name        0   0   1  n/a        0%
phone              1   0   0  100%       100%
overall            5   0   1  100%       83%
```

Read this with care: the demo data is synthetic, written by the same author as the detectors, and
has only six labeled personal-data columns. It proves the scanner does what it claims, not that it
works on real databases. Person names are the known gap: they have no checksum or fixed shape, so
rules cannot find them. That is what the LLM (large language model) phase is for
([how scoring works](docs/decisions/0004-evaluation.md)).

## Known limitations

- Only text columns are scanned, and values are sampled with `LIMIT`, not randomly
  ([decision 0002](docs/decisions/0002-sampling.md)). A clean scan is evidence, not proof.
- Validators cover Spanish IDs and a dozen European IBAN lengths; other formats are not recognized.

## Roadmap

- [x] Phase 0: skeleton, CI, messy demo data with an answer key
- [x] Phase 1: detection core with precision/recall metrics
- [ ] Phase 2: catalog, data contracts, policy checks
- [ ] Phase 3: local LLM second opinion
- [ ] Phase 4: Airflow scheduling and drift alerts
- [ ] Phase 5: Terraform deployment on Azure

Design decisions live in [`docs/decisions/`](docs/decisions/).
