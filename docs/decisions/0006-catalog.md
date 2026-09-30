# 0006: The catalog documents, `check` enforces

Status: accepted

- **Two outputs from one model:** `catalog.md` for people, `catalog.json` for tools.
- **The catalog never fails the build.** A document that can break CI gets ignored or disabled.
  Enforcement stays in `check`; the catalog shows the same violations per table.
- **Deterministic output, no timestamp.** Regenerating changes the file only when something real
  changed, so it can be committed and reviewed in pull requests.
- **The declared type wins over the detected one** in the "Personal data" column. A human made that
  call. The mismatch still appears as an error in `check`.
- **Declared columns missing from the database are shown** as "not found in database" instead of
  being dropped. A stale contract should be visible, not silently hidden.
- **No golden-file test for the shipped example.** Column type strings can differ between
  SQLAlchemy versions, so a byte-for-byte comparison would fail for reasons that are not bugs.
  Tradeoff: `examples/catalog/` can go stale, so regenerate it when detection changes.
