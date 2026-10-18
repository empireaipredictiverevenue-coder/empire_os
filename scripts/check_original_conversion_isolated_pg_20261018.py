#!/usr/bin/env python3
"""Manual, self-contained PG18 registry proof. ONLY ephemeral, Unix-socket test DB."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import subprocess
import tempfile
import psycopg

from empire_os.predictive_calibration import prepare_prospective_conversion_prediction
from empire_os.original_conversion_registry_transport import PostgresOriginalConversionRegistry

ROOT = Path(__file__).resolve().parents[1]
DDL = ROOT / "docs/commercial/STAGED_ORIGINAL_CONVERSION_REGISTRY_20261018.sql"
BIN = Path("/usr/lib/postgresql/18/bin")
TENANT_A = "11111111-1111-4111-8111-111111111111"
TENANT_B = "22222222-2222-4222-8222-222222222222"

def command(*args):
    result = subprocess.run(args, check=False, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"isolated command failed: {args[0]}: {result.stdout[-2400:]} {result.stderr[-2400:]}")
    return result.stdout

def denied(fn, phrase=None):
    try:
        fn()
    except Exception as error:
        if phrase and phrase not in str(error):
            raise AssertionError(f"expected {phrase}: {type(error).__name__}: {error}") from error
        return
    raise AssertionError("Expected security denial")

@contextmanager
def isolated_cluster():
    with tempfile.TemporaryDirectory(prefix="empconvpg-", dir="/tmp") as home:
        tmp = Path(home)
        data, socket = tmp/"data", tmp/"socket"
        socket.mkdir(mode=0o700)
        command(str(BIN/"initdb"), "-D", str(data), "--auth-local=trust",
                "--encoding=UTF8", "--no-instructions")
        opts = f"-c listen_addresses='' -c unix_socket_directories={socket} -p 65493 -c fsync=off"
        command(str(BIN/"pg_ctl"), "-D", str(data), "-l", str(tmp/"postgres.log"), "-o", opts, "-w", "start")
        try:
            root_dsn = f"host={socket} port=65493 dbname=postgres user=ubuntu"
            with psycopg.connect(root_dsn, autocommit=True) as db:
                db.execute("CREATE DATABASE empiredb")
            admin = root_dsn.replace("dbname=postgres", "dbname=empiredb")
            with psycopg.connect(admin, autocommit=True) as db:
                db.execute("CREATE ROLE empiredb_migrator NOLOGIN")
                db.execute("CREATE ROLE service_role NOLOGIN")
                db.execute("GRANT CREATE ON SCHEMA public TO empiredb_migrator")
                db.execute("SET ROLE empiredb_migrator")
                db.execute("""CREATE TABLE public.empire_tenant_role_bindings(
                    role_name name PRIMARY KEY, tenant_id uuid NOT NULL,
                    active boolean NOT NULL DEFAULT true)""")
                db.execute("""CREATE FUNCTION public.empire_current_tenant_id()
                    RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER
                    SET search_path=pg_catalog,public AS $$
                    SELECT b.tenant_id FROM public.empire_tenant_role_bindings b
                    WHERE b.role_name=session_user AND b.active LIMIT 1 $$""")
                db.execute("REVOKE ALL ON FUNCTION public.empire_current_tenant_id() FROM PUBLIC")
                db.execute("RESET ROLE")
                db.execute("CREATE ROLE conv_test_a LOGIN")
                db.execute("CREATE ROLE conv_test_b LOGIN")
                db.execute("SET ROLE empiredb_migrator")
                db.execute("INSERT INTO public.empire_tenant_role_bindings VALUES (%s,%s,true)",
                           ("conv_test_a", TENANT_A))
                db.execute("INSERT INTO public.empire_tenant_role_bindings VALUES (%s,%s,true)",
                           ("conv_test_b", TENANT_B))
                db.execute("RESET ROLE")
            command("/usr/bin/psql", "-X", "-v", "ON_ERROR_STOP=1", "-h",
                    str(socket), "-p", "65493", "-U", "ubuntu",
                    "-d", "empiredb", "-f", str(DDL))
            with psycopg.connect(admin, autocommit=True) as db:
                db.execute("GRANT empire_original_conversion_prediction_writer TO conv_test_a")
                db.execute("GRANT empire_original_conversion_prediction_reader TO conv_test_a")
                db.execute("GRANT empire_original_conversion_prediction_reader TO conv_test_b")
            yield socket, admin
        finally:
            command(str(BIN/"pg_ctl"), "-D", str(data), "-m", "immediate", "-w", "stop")

def user_dsn(socket, who):
    return f"host={socket} port=65493 dbname=empiredb user={who}"

def main():
    print("ISOLATED_PG18: new disposable cluster; Unix socket only; no TCP")
    with isolated_cluster() as (socket, admin):
        for user in ("conv_test_a", "conv_test_b"):
            with psycopg.connect(user_dsn(socket, user)) as conn:
                denied(lambda: conn.execute(
                    "SELECT * FROM public.original_conversion_predictions"),
                    "permission denied")
        now = datetime.now(timezone.utc)
        candidate = prepare_prospective_conversion_prediction(
            tenant_id=TENANT_A, opportunity_key="solar_case_1",
            predicted_probability=0.6, predicted_at=now.isoformat(),
            horizon_until=(now+timedelta(days=14)).isoformat(),
            evidence_refs=["empire:source1","empire:source2"],
            model_name="empire_quant", model_version="v1", assessed_at=now)
        transport = PostgresOriginalConversionRegistry(
            writer_dsn=user_dsn(socket,"conv_test_a"),
            reader_dsn=user_dsn(socket,"conv_test_a"), enabled=True)
        receipt = transport.register(candidate, as_of=now)
        assert receipt["status"] == "recorded"
        assert transport.register(candidate, as_of=now)["status"] == "existing"
        row = transport.readback(
            tenant_id=TENANT_A, prediction_ref=candidate["candidate_prediction_ref"])
        assert row and row["prediction"]["predicted_probability"] == 0.6
        assert row["recorded_at"] == receipt["recorded_at"]
        assert transport.register_review(candidate, as_of=now)["eligible_for_calibration"] is False
        print("ISOLATED_REGISTRATION_PASS: idempotent insert and readback; learning held")
        other = PostgresOriginalConversionRegistry(
            writer_dsn=user_dsn(socket,"conv_test_b"),
            reader_dsn=user_dsn(socket,"conv_test_b"), enabled=True)
        assert other.readback(
            tenant_id=TENANT_A, prediction_ref=candidate["candidate_prediction_ref"]) is None
        denied(lambda: other.register(candidate, as_of=now))
        print("ISOLATED_CROSS_TENANT_PASS")
        forged = dict(candidate, proposed_prediction=dict(candidate["proposed_prediction"]))
        forged["proposed_prediction"]["predicted_probability"] = .95
        denied(lambda: transport.register(forged, as_of=now))
        with psycopg.connect(admin, autocommit=True) as db:
            denied(lambda: db.execute(
                "UPDATE public.original_conversion_predictions SET model_version='changed'"),
                "CONV_REG_APPEND_ONLY")
            denied(lambda: db.execute(
                "DELETE FROM public.original_conversion_predictions"),
                "CONV_REG_APPEND_ONLY")
        print("ISOLATED_APPEND_ONLY_PASS")

        # Database-side checks: invalid clocks, changed identity, and tenant
        # mismatches are rejected by PostgreSQL, not just Python preflight.
        import json
        from hashlib import sha256
        def try_write(who, tenant, payload):
            with psycopg.connect(user_dsn(socket, who), autocommit=True) as db:
                db.execute("SET ROLE empire_original_conversion_prediction_writer")
                encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
                digest = sha256(encoded.encode()).hexdigest()
                return db.execute(
                    "SELECT public.record_original_conversion_prediction_v1(%s,%s,%s::jsonb,%s)",
                    (tenant, payload["prediction_ref"], encoded, digest)
                ).fetchone()[0]

        with psycopg.connect(admin, autocommit=True) as db:
            db.execute("GRANT empire_original_conversion_prediction_writer TO conv_test_b")
        denied(lambda: try_write("conv_test_b", TENANT_A,
                                candidate["proposed_prediction"]),
               "CONV_REG_TENANT_NOT_AUTHENTICATED")
        changed = dict(candidate["proposed_prediction"])
        changed["predicted_probability"] = .9
        denied(lambda: try_write("conv_test_a", TENANT_A, changed),
               "CONV_REG_IMMUTABLE_IDENTITY_COLLISION")
        too_old = dict(candidate["proposed_prediction"])
        too_old["predicted_at"] = (now-timedelta(minutes=10)).isoformat()
        denied(lambda: try_write("conv_test_a", TENANT_A, too_old),
               "CONV_REG_NOT_PROSPECTIVE")
        too_future = dict(candidate["proposed_prediction"])
        too_future["predicted_at"] = (now+timedelta(minutes=5)).isoformat()
        denied(lambda: try_write("conv_test_a", TENANT_A, too_future),
               "CONV_REG_NOT_PROSPECTIVE")
        print("ISOLATED_DATABASE_VALIDATION_PASS: timestamps, tenant and collision")

        # Parallel same-identity registration should yield one recorded row
        # and stable idempotent successes for all workers.
        from concurrent.futures import ThreadPoolExecutor
        parallel = prepare_prospective_conversion_prediction(
            tenant_id=TENANT_A, opportunity_key="solar_case_concurrent",
            predicted_probability=0.67, predicted_at=now.isoformat(),
            horizon_until=(now+timedelta(days=7)).isoformat(),
            evidence_refs=["empire:source3"], model_name="empire_quant",
            model_version="v1", assessed_at=now)
        with ThreadPoolExecutor(max_workers=3) as pool:
            receipts = list(pool.map(
                lambda _: transport.register(parallel, as_of=now), range(3)))
        assert sorted(row["status"] for row in receipts) == [
            "existing", "existing", "recorded"], receipts
        assert len({row["recorded_at"] for row in receipts}) == 1
        print("ISOLATED_CONCURRENCY_PASS: no duplicate prediction records")
    print("ISOLATED_CLUSTER_DESTROYED: no production database accessed")

if __name__ == "__main__":
    main()
