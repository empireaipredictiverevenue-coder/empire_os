#!/usr/bin/env python3
"""Read-only live EmpireDB Analytics054/055 object and role catalogue review.

Must be run as the OS 'postgres' peer (not root, not an app account),
against a FIXED local UNIX socket and FIXED EmpireDB dbname. No DSN,
password, HBA modification, customer rows, migrations, grants, or output
of any database contents beyond restricted catalogue booleans.
"""
from __future__ import annotations

import argparse
import json
import os
import pwd

from empire_os.analytics.catalog_readiness import _held, inspect_connection


def inspect(*, connector=None, peer_uid=None, postgres_uid=None):
    if peer_uid is None:
        peer_uid=os.geteuid()
    if postgres_uid is None:
        try:
            postgres_uid=pwd.getpwnam("postgres").pw_uid
        except KeyError:
            return _held("HELD_POSTGRES_OS_ACCOUNT_NOT_AVAILABLE")
    if peer_uid != postgres_uid:
        return _held("HELD_EXACT_LOCAL_POSTGRES_PEER_REQUIRED")
    if connector is None:
        import psycopg
        connector=psycopg.connect
    try:
        with connector(
            host="/var/run/postgresql",port=5432,dbname="empiredb",
            user="postgres",connect_timeout=4,autocommit=True,
            options="-c default_transaction_read_only=on "
                    "-c statement_timeout=4000 -c lock_timeout=1000",
        ) as conn:
            return inspect_connection(conn,expected_db="empiredb")
    except Exception:
        return _held("HELD_LOCAL_EMPIREDB_READONLY_CONNECTION_UNAVAILABLE")


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only",required=True,action="store_true")
    parser.parse_args(argv)
    report=inspect()
    print(json.dumps(report,sort_keys=True))
    return 0 if report["database_catalog_observed"] is True else 2

if __name__=="__main__":
    raise SystemExit(main())
