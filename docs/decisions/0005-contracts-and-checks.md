# 0005: Data contracts and the `check` gate

Status: accepted

- **Minimal custom YAML, not an existing standard** (for example the Open Data Contract Standard).
  A contract here has four fields: `table`, `owner`, `retention_days`, `pii_columns`. A standard
  brings many fields this tool would leave empty, and is harder to explain in one README screen.
  Cost: no interoperability with other tooling. Revisit if someone needs to consume these files.
- **Contracts list only the personal-data columns, and only for tables that have some.**
  Full schemas would be noise and would duplicate what the database already knows.
- **Two sources of truth on purpose.** The scanner says what it found, the contract says what
  the team declared, and `check` fails when they disagree. That is the control.
- **`generate-contracts` never overwrites.** It writes starters, leaves `owner` and
  `retention_days` empty (a tool cannot know who is responsible), and skips existing files so
  human edits are safe.
- **Undetected-but-declared columns are a warning, not an error.** Person names cannot be found
  by rules, so a human declaring them is the intended way to cover the gap.
- **Unknown contract fields are an error.** A typo such as `retention_day` would otherwise read
  as "retention missing" or, worse, be silently ignored.
- **Exit codes:** 0 passed, 1 violations, 2 unreadable input. CI can tell a failed policy from a
  broken config.
- **The policy file has one knob** (`pii_tables_require`). More rules, for example forbidding
  personal data in an analytics schema, come when there is a second real use for them.
