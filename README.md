# data-warden

Scan databases for personal data (PII), generate a catalog and data contracts, and fail the build
when governance policies are broken.

> Status: Phase 0 (skeleton and messy demo data). Detection is not built yet.

## Why

Personal data hides behind bad column names. Rules that live in a wiki get ignored; rules that
fail a pull request do not.

## Quickstart

```bash
uv sync
docker compose up -d postgres
uv run data-warden seed          # loads demo data, writes ground_truth.json
uv run pytest
```

## Roadmap

- [x] Phase 0: skeleton, CI, messy demo data with an answer key
- [ ] Phase 1: detection core with precision/recall metrics
- [ ] Phase 2: catalog, data contracts, policy checks
- [ ] Phase 3: local LLM second opinion
- [ ] Phase 4: Airflow scheduling and drift alerts
- [ ] Phase 5: Terraform deployment on Azure

Design decisions live in [`docs/decisions/`](docs/decisions/).
