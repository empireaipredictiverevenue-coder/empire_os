"""Independent original PostgreSQL 18 first-party cost-settlement canary.

Creates and DESTROYS only a new tempdir-local PG18 instance on a Unix socket.
Never connects to production and never modifies the pinned release SQL.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import subprocess
import tempfile

import psycopg

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "docs/release_candidates/empire_data_cloud_meter_pg18_review_only_20261107.sql"
BIN = Path("/usr/lib/postgresql/18/bin")
NO_PAID_REF = "empire_fabric_direct_public_no_paid_api_v1"


def run(*args: str) -> str:
    p = subprocess.run(
        [str(arg) for arg in args], check=True,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=25,
    )
    return p.stdout


def main() -> None:
    assert SQL.is_file()
    assert (BIN / "pg_ctl").exists()
    with tempfile.TemporaryDirectory(prefix="empire_data_pg18_cost_") as temp:
        base = Path(temp)
        data = base / "data"
        sock = base / "sock"
        sock.mkdir()
        run(BIN / "initdb", "-D", data, "-U", "isolated_postgres",
            "-A", "trust", "--no-instructions")
        started = False
        try:
            # Socket-only, NO TCP or production database connection.
            # -l is essential: an inherited stdout pipe from the postgres
            # daemon would otherwise keep subprocess.communicate waiting.
            started = True
            run(BIN / "pg_ctl", "-D", data, "-l", base / "postgres.log",
                "-o", f"-c listen_addresses='' -c unix_socket_directories={sock} -p 55473",
                "-w", "start")
            with closing(psycopg.connect(
                host=str(sock), port=55473, dbname="postgres",
                user="isolated_postgres", autocommit=True,
            )) as admin:
                admin.execute("CREATE DATABASE empiredb")
            run(BIN / "psql", "-X", "-v", "ON_ERROR_STOP=1",
                "-h", sock, "-p", "55473", "-U", "isolated_postgres",
                "-d", "empiredb", "-f", SQL)

            with closing(psycopg.connect(
                host=str(sock), port=55473, dbname="empiredb",
                user="isolated_postgres", autocommit=True,
            )) as db:
                def seed(tenant: str, key: str) -> None:
                    db.execute(
                        """INSERT INTO empire_data_cloud_api.tenants
                        (tenant_id,active,held,monthly_request_cap,
                         monthly_cost_cap_micros,search_cost_ceiling_micros,
                         audit_cost_ceiling_micros,allowed_operations,allowed_hosts)
                        VALUES (%s,true,false,10,5000,500,500,
                                ARRAY['search'],ARRAY[]::text[])""",
                        (tenant,),
                    )
                    db.execute(
                        """INSERT INTO empire_data_cloud_api.api_keys
                        (token_sha256,tenant_id,active,expires_at)
                        VALUES (%s,%s,true,now()+interval '1 hour')""",
                        (key,tenant),
                    )

                def book(key: str, idempotency: str) -> int:
                    return db.execute(
                        """SELECT empire_data_cloud_api.reserve(
                         %s,'search',%s,%s,NULL)""",
                        (key,idempotency,"c"*64),
                    ).fetchone()[0]

                seed("synthetic_free_source", "a"*64)
                first=book("a"*64,"free-success-0001")
                status=db.execute(
                    "SELECT empire_data_cloud_api.settle(%s,%s,'completed',0,%s)",
                    ("a"*64,first,NO_PAID_REF),
                ).fetchone()[0]
                assert status=="completed",status
                second=book("a"*64,"free-error-00001")
                error_state=db.execute(
                    "SELECT empire_data_cloud_api.settle(%s,%s,'provider_error',0,%s)",
                    ("a"*64,second,NO_PAID_REF),
                ).fetchone()[0]
                assert error_state=="provider_error",error_state
                held=db.execute(
                    "SELECT held FROM empire_data_cloud_api.tenants WHERE tenant_id=%s",
                    ("synthetic_free_source",),
                ).fetchone()[0]
                assert held is False
                seed("synthetic_missing_evidence", "b"*64)
                third=book("b"*64,"null-evidence-0001")
                hold_state=db.execute(
                    """SELECT empire_data_cloud_api.settle(
                    %s,%s,'provider_error',NULL,NULL)""",
                    ("b"*64,third),
                ).fetchone()[0]
                assert hold_state=="cost_integrity_hold",hold_state
                held_missing=db.execute(
                    "SELECT held FROM empire_data_cloud_api.tenants WHERE tenant_id=%s",
                    ("synthetic_missing_evidence",),
                ).fetchone()[0]
                assert held_missing is True
                print("ISOLATED_PG18_ORIGINAL_SQL_FIRST_PARTY_COST_CANARY_PASS")
                print("SUCCESS_ZERO_EXTERNAL_PROVIDER_FEE_SETTLED=completed")
                print("FAILED_FREE_FETCH_SETTLED=provider_error")
                print("NO_FALSE_TENANT_HOLD_ON_FREE_FETCH=true")
                print("ORIGINAL_NULL_COST_MAINTAINS_COST_INTEGRITY_HOLD=true")
                print("PRODUCTION_DATABASE_CONNECTIONS=0")
                print("PRODUCTION_DATABASE_WRITES=0")
        finally:
            if started:
                try:
                    run(BIN / "pg_ctl", "-D", data, "-m", "immediate", "-w", "stop")
                except subprocess.CalledProcessError:
                    # If startup never succeeded, there is no server to stop.
                    pass


if __name__ == "__main__":
    main()
