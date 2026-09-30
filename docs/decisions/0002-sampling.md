# 0002: Sampling strategy

Status: accepted (revisit in Phase 4)

- Sample with `WHERE col IS NOT NULL AND col != '' LIMIT n`.
- **Tradeoff:** `LIMIT` without `ORDER BY` is not random. Databases usually return the oldest
  rows first, so PII that only appears in recent rows can be missed.
- **Why accepted:** random sampling (`ORDER BY random()`, `TABLESAMPLE`) is slow or unsupported
  on large tables and differs per database. Predictable and cheap wins for now.
- **Consequence:** a clean scan is evidence, not proof. The README says so.
- **Text columns only:** PII stored in numeric columns (for example a phone number as an integer)
  is not detected yet.