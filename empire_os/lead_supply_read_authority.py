"""Canonical, dedicated, local EmpireDB lead-census reader identity contract.

No sessions, credentials or privileges are created by this module.
"""
from __future__ import annotations

from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict


DEDICATED_READER_LOGIN = "empire_lead_supply_reader_login"
LOCAL_DB_HOSTS = frozenset((
    "127.0.0.1", "localhost", "::1", "/var/run/postgresql"
))


def validate_reader_identity(dsn: str) -> tuple[bool, str]:
    """No password/conninfo returned, even for malformed strings."""
    try:
        cfg = conninfo_to_dict(dsn)
    except (ValueError, TypeError, ProgrammingError):
        return False, "INVALID_CONNECTION_CONFIGURATION"
    if str(cfg.get("dbname") or "") != "empiredb":
        return False, "NONCANONICAL_DATABASE"
    if str(cfg.get("host") or "") not in LOCAL_DB_HOSTS:
        return False, "NONLOCAL_DATABASE_ENDPOINT"
    if str(cfg.get("user") or "") != DEDICATED_READER_LOGIN:
        return False, "NONDEDICATED_READER_LOGIN"
    return True, "DEDICATED_LOCAL_EMPIREDB_READER_IDENTITY"
