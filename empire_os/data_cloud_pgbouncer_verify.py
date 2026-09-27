"""Read-only verification for the private EmpireDB PgBouncer endpoint."""
from __future__ import annotations

import json
import os

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo


def pooled_dsn(dsn: str) -> str:
    params = conninfo_to_dict(dsn)
    params["host"] = "127.0.0.1"
    params["port"] = "6432"
    return make_conninfo(**params)


def main() -> int:
    dsn = os.environ.get("EMPIREDB_DSN")
    if not dsn:
        raise RuntimeError("EMPIREDB_DSN is required")

    with psycopg.connect(
        pooled_dsn(dsn),
        connect_timeout=5,
        application_name="empiredb-pgbouncer-verify",
    ) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        row = connection.execute(
            """
            SELECT current_database(),
                   current_user,
                   inet_server_addr()::text,
                   inet_server_port(),
                   pg_is_in_recovery(),
                   (SELECT count(*) FROM public.prospects)
            """
        ).fetchone()

    report = {
        "schema_version": "empire.pgbouncer-verify.v1",
        "database": row[0],
        "user": row[1],
        "backend_host": row[2],
        "backend_port": row[3],
        "in_recovery": bool(row[4]),
        "prospects_visible": int(row[5]),
        "pool_host": "127.0.0.1",
        "pool_port": 6432,
        "read_only_verification": True,
        "verified": (
            row[0] == "empiredb"
            and row[3] == 5432
            and not bool(row[4])
            and int(row[5]) == 32899
        ),
    }
    print(json.dumps(report, sort_keys=True))
    if not report["verified"]:
        raise RuntimeError("PgBouncer verification failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
