#!/usr/bin/env python3
"""One-shot READ-ONLY BSC financial operator admission preflight.

Run on EmpireOS: sudo -n -u postgres /srv/empire_os/.venv/bin/python
scripts/inspect_bsc_payment_operator_readiness.py

Does NOT authenticate a financial operator, create role passwords, grant roles,
modify HBA, or activate checkout. No secrets are printed.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

from empire_os.bsc_payment_operator_readiness import inspect_catalog

SOCKET = "/var/run/postgresql"
DSN = "host=/var/run/postgresql port=5432 dbname=empiredb user=postgres connect_timeout=5"
CREDENTIAL_VAULT = Path("/var/lib/empire-bsc-payment-operators")


def main() -> int:
    if sys.argv[1:] not in ([], ["--preflight"]):
        print(json.dumps({"status":"BLOCKED_READONLY_ONLY"}))
        return 3
    try:
        import psycopg
        report = inspect_catalog(
            lambda: psycopg.connect(DSN),
            vault_exists=CREDENTIAL_VAULT.exists() or CREDENTIAL_VAULT.is_symlink(),
        )
        print(json.dumps(report,sort_keys=True))
        return 0
    except Exception:
        print(json.dumps({
            "schema_version":"empire.bsc-two-financial-operator-readiness.v1",
            "status":"BLOCKED_AUTH_CATALOG_UNAVAILABLE",
            "mode":"READ_ONLY",
            "payment_collection_authorized":False,
            "roles_created":0,
            "database_mutations":0,
        },sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
