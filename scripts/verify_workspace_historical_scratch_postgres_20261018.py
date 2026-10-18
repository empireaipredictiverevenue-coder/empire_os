"""Local TEMPORARY PostgreSQL 18 verification; never connects to EmpireDB production.

Creates an isolated Unix-socket-only cluster under /tmp; no DNS or TCP
listener. The dummy 'empiredb' name exists ONLY in this scratch cluster.
"""
from __future__ import annotations
import os
import pathlib
import pwd
import re
import shutil
import subprocess
import tempfile

import psycopg

BIN="/usr/lib/postgresql/18/bin"
ROOT=pathlib.Path("/srv/empire_os")
MIGRATION=ROOT/"migrations/empiredb/052_workspace_historical_send_receipts_observe_only.sql"
PORT="59543"


def run(*args, must=True, cwd=None):
    if str(args[0]).endswith("/pg_ctl"):
        # The daemon inherits stdio; captured pipes make subprocess.run hang.
        result=subprocess.run(args,cwd=cwd,stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL,text=True,timeout=60)
    else:
        result=subprocess.run(args,cwd=cwd,capture_output=True,text=True,timeout=60)
    if must and result.returncode:
        print("COMMAND_FAILED",args[0],result.returncode,
              (result.stderr or "")[-1800:],flush=True)
        raise AssertionError("SCRATCH_CLUSTER_COMMAND_FAILED")
    return result


def main():
    assert os.geteuid()!=0, "SCRATCH_MUST_RUN_AS_UNPRIVILEGED_USER"
    assert MIGRATION.is_file()
    root=pathlib.Path(tempfile.mkdtemp(prefix="empire_hist052_scratch_"))
    data=root/"db"
    sock=root/"socket"
    sock.mkdir(mode=0o700)
    user=pwd.getpwuid(os.geteuid()).pw_name
    assert re.fullmatch(r"[a-z_][a-z0-9_]*", user), "SAFE_TEST_OS_ROLE_REQUIRED"
    started=False
    try:
        run(f"{BIN}/initdb","-D",str(data),"-U",user,
            "--auth-local=trust","--auth-host=reject","--no-instructions")
        run(f"{BIN}/pg_ctl","-D",str(data),"-o",
            f"-c listen_addresses= -c unix_socket_directories={sock} -p {PORT}",
            "-w","start")
        started=True
        prefix=["/usr/bin/psql","-X","-v","ON_ERROR_STOP=1",
                "-h",str(sock),"-p",PORT,"-U",user]
        run(*prefix,"-d","postgres","-c","CREATE DATABASE empiredb;")
        run(*prefix,"-d","empiredb","-c",
            "CREATE ROLE empiredb_migrator NOLOGIN;"
            " CREATE ROLE empire_closer_observer NOLOGIN NOSUPERUSER NOBYPASSRLS;"
            " CREATE ROLE postgres LOGIN SUPERUSER;"
            f" GRANT empiredb_migrator TO {user};"
            " GRANT CREATE ON SCHEMA public TO empiredb_migrator;"
            " GRANT USAGE ON SCHEMA public TO empire_closer_observer;")
        print("SCRATCH_CLUSTER_ONLY=true TCP_LISTENER=false")
        done=run(*prefix,"-d","empiredb","-f",str(MIGRATION))
        print("MIGRATION_052_APPLIES_IN_SCRATCH=true")
        replay=run(*prefix,"-d","empiredb","-f",str(MIGRATION),must=False)
        assert replay.returncode!=0 and "HIST052_EXISTING_OBJECT_REVIEW_REQUIRED" in replay.stderr
        print("MIGRATION_052_DUPLICATE_REJECTED=true")

        from scripts.import_workspace_historical_sent_receipts_20261018 import (
            load_private_custody,import_exact_six_receipts
        )
        manifest=load_private_custody()
        assert manifest["evidence_count"]==6
        from empire_os.workspace_solar_historical_status import (
            review_six_historical_receipt_admission,
        )
        observer_dsn=f"host={sock} port={PORT} dbname=empiredb user={user}"
        before=review_six_historical_receipt_admission(
            connect_factory=psycopg.connect,dsn=observer_dsn
        )
        assert before["status"]=="SCHEMA_ACTIVE_NO_HISTORICAL_RECEIPTS"
        assert before["database_historical_receipts_verified"]==0
        print("REAL_POSTGRES_PRIVATE_FOUNDER_READ_BEFORE=0")
        connstr=f"host={sock} port={PORT} dbname=empiredb user=postgres"
        first=import_exact_six_receipts(manifest,connect_factory=psycopg.connect,dsn=connstr)
        assert first["new_receipts"]==6 and first["crm_rows_created"]==0
        second=import_exact_six_receipts(manifest,connect_factory=psycopg.connect,dsn=connstr)
        assert second["new_receipts"]==0 and second["replayed_identical_receipts"]==6
        after=review_six_historical_receipt_admission(
            connect_factory=psycopg.connect,dsn=observer_dsn
        )
        assert after["status"]=="SIX_HISTORICAL_RECEIPTS_VERIFIED_IN_EMPIREDB"
        assert after["database_historical_receipts_verified"]==6
        assert after["crm_records_created"]==0 and after["outbound_sent"] is False
        print("REAL_POSTGRES_IMPORT_FIRST=6 REPLAY_INSERTS=0")
        print("REAL_POSTGRES_PRIVATE_FOUNDER_READ_AFTER=6")


        with psycopg.connect(connstr,autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*),bool_and(historical_approval_attested=false),"
                            "bool_and(crm_contact_bound=false),"
                            "bool_and(customer_revenue_verified=false)"
                            " FROM public.workspace_historical_sent_receipts")
                n,approval,crm,revenue=cur.fetchone()
                assert (n,approval,crm,revenue)==(6,True,True,True)
                cur.execute("SET ROLE empire_closer_observer")
                cur.execute("SELECT count(*) FROM public.workspace_historical_sent_receipts")
                assert cur.fetchone()[0]==6
                try:
                    cur.execute("DELETE FROM public.workspace_historical_sent_receipts")
                    raise AssertionError("READ_ONLY_ROLE_DELETED")
                except psycopg.errors.InsufficientPrivilege:
                    pass
                cur.execute("RESET ROLE")
                print("READONLY_OBSERVER_COUNT=6 OBSERVER_DELETE_DENIED=true")

                def must_fail(sql,cls):
                    try:
                        cur.execute(sql)
                    except cls:
                        return True
                    raise AssertionError("UNSAFE_SQL_ACCEPTED")
                assert must_fail(
                    "UPDATE public.workspace_historical_sent_receipts "
                    "SET linkage_state='UNBOUND_EXTERNAL_SENT_OBSERVED'",
                    psycopg.errors.RaiseException
                )
                assert must_fail(
                    "DELETE FROM public.workspace_historical_sent_receipts",
                    psycopg.errors.RaiseException
                )
                assert must_fail(
                    "UPDATE public.workspace_historical_sent_receipts SET historical_approval_attested=true",
                    psycopg.errors.RaiseException
                )
                print("IMMUTABLE_UPDATE_DELETE_BLOCKED=true FALSE_APPROVAL_BLOCKED=true")

        print("SCRATCH_ONLY_DB_CLEANUP_PENDING=true")
    finally:
        if started:
            run(f"{BIN}/pg_ctl","-D",str(data),"-m","immediate","-w","stop")
        shutil.rmtree(root)
        print("ISOLATED_POSTGRES_CLUSTER_STOPPED_AND_REMOVED=true")


if __name__=="__main__":
    main()
