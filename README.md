# data-warden

Scan databases for personal data (PII, personally identifiable information), generate a catalog
and data contracts, and fail the build when governance policies are broken.

> Status: Phases 0 to 2 done. Phase 3 (optional local LLM for person names) is implemented and
> tested with a fake model; results with a real model are pending.

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
uv run data-warden generate-contracts   # writes starter contracts/ (never overwrites)
uv run data-warden check                # exits 1 if scan and contracts disagree
uv run data-warden catalog              # writes catalog/catalog.md and catalog.json
uv run pytest
```

Example `scan` output:

```
COLUMN                      TYPE            CONFIDENCE  SOURCE  SAMPLES
customers.col7              email           100%        rules   200
customers.iban_raw          iban            100%        rules   200
customers.phone             phone           100%        rules   200
employees.ref_code          national_id     100%        rules   20
orders.notes                free_text_pii   13%         rules   400
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

## Optional: a local LLM for person names

Rules cannot recognise names, so `--llm` asks a model running on your machine (through
[Ollama](https://ollama.com)) about every text column the rules did not flag:

```bash
ollama pull <model>                                   # any chat model you have
uv run data-warden scan --llm --llm-model <model>
uv run data-warden evaluate --llm --llm-model <model>  # rules alone vs rules + model
```

What to know before using it:

- **It has to see the values.** Masking names would defeat the purpose. Instead, the model address
  must be local (non-local addresses are refused), redirects and proxies are ignored, and at most
  15 distinct values per column are shown.
- **It never feeds `check` or `catalog`.** A gate that can fail differently on every run gets
  switched off. Model findings are marked `llm` in the SOURCE column.
- **It can be wrong, and the demo data tries to catch that:** `company_name` and `product_name`
  look like surnames but are not personal data.
- Design notes: [decision 0007](docs/decisions/0007-local-llm.md).

## Contracts and the check gate

`generate-contracts` writes one small YAML file per table that holds personal data. A human fills in
the owner and retention period and adds columns rules cannot detect (like names). `check` then
compares the scanner with the contracts and fails the build when they disagree:

```yaml
table: customers
owner: customer-data-team
retention_days: 730
pii_columns:
  col7: email
  full_name: person_name   # declared by a human, rules cannot detect names
```

| Situation | Result |
| --- | --- |
| Scanner finds PII the contract does not declare | error |
| Contract declares a different type than the scanner found | error |
| Table with PII has no contract, owner or retention | error |
| Contract declares a column the scanner did not detect | warning |

Exit codes: 0 passed, 1 violations, 2 unreadable contract or policy. Working examples live in
[`examples/`](examples/), and CI runs `check` against them
([decision 0005](docs/decisions/0005-contracts-and-checks.md)).

## Catalog

`catalog` joins the live schema, the scanner and the contracts into a readable page and a JSON
file. It documents and never fails the build; `check` is the gate. Output has no timestamps, so
it only changes when something real changed. See [`examples/catalog/catalog.md`](examples/catalog/catalog.md)
([decision 0006](docs/decisions/0006-catalog.md)).

## Known limitations

- Only text columns are scanned, and values are sampled with `LIMIT`, not randomly
  ([decision 0002](docs/decisions/0002-sampling.md)). A clean scan is evidence, not proof.
- Validators cover Spanish IDs and a dozen European IBAN lengths; other formats are not recognized.

## Roadmap

- [x] Phase 0: skeleton, CI, messy demo data with an answer key
- [x] Phase 1: detection core with precision/recall metrics
- [x] Phase 2: data contracts, policy checks, catalog
- [ ] Phase 3: local LLM second opinion (implemented, real-model results pending)
- [ ] Phase 4: Airflow scheduling and drift alerts
- [ ] Phase 5: Terraform deployment on Azure

Design decisions live in [`docs/decisions/`](docs/decisions/).
