"""Policy as code: the rules a contract must satisfy, kept in a reviewable file."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

REQUIRABLE_FIELDS = ("owner", "retention_days")


class PolicyError(ValueError):
    """The policy file is unreadable or has the wrong shape."""


@dataclass(frozen=True)
class Policy:
    # Contract fields that every table holding personal data must fill in.
    pii_tables_require: tuple[str, ...] = REQUIRABLE_FIELDS


def load_policy(path: Path | None) -> Policy:
    if path is None:
        return Policy()
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as error:
        raise PolicyError(f"{path}: invalid YAML ({error})") from error
    if not isinstance(data, dict) or set(data) - {"pii_tables_require"}:
        raise PolicyError(f"{path}: only `pii_tables_require` is supported")
    required = data.get("pii_tables_require", list(REQUIRABLE_FIELDS))
    if not isinstance(required, list) or any(item not in REQUIRABLE_FIELDS for item in required):
        raise PolicyError(f"{path}: `pii_tables_require` may only contain {REQUIRABLE_FIELDS}")
    return Policy(tuple(required))
