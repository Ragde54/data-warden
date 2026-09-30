# 0001: Tooling and layout

Status: accepted

- **uv** for environments and lockfile: one fast tool, reproducible installs (`uv.lock` is committed).
- **src layout**: tests import the installed package, not the working folder, so packaging bugs show up early.
- **Typer** for the CLI: type hints become the interface, less boilerplate than argparse.
- **SQLAlchemy** for introspection: one API across Postgres and (later) Snowflake.
- **Synthetic data with an answer key**: you cannot claim a detection rate without knowing the truth.
- **Ruff** for lint and formatting: one tool instead of three.
