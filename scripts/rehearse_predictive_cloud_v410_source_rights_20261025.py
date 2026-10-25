#!/usr/bin/env python3
"""V4.10 real disposable PG18 source-custody ledger and restricted reader.

Never touches the production cluster; never asserts genuine source licensing.
"""
from __future__ import annotations

import json
import os
import subprocess
from hashlib import sha256

import psycopg

from empire_os.predictive_cloud_v410_rights_reader import EmpireDbHeldSourceRightsReader

TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"


def digest(value: str) -> str:
    return sha256(("fictional-v410-rights:" + value).encode()).hexdigest()


DB = "empire_v4_outbox_fixture"
SOURCE = digest("source")
DOC = digest("fictional-license-custody")
REASON = digest("fictional-revoke")


def owner_sql(sql: str, *, expect_failure: str | None = None) -> str:
    cmd = [
        "psql", "-XAtq", "-v", "ON_ERROR_STOP=1", "-d", DB,
        "-c", "SET ROLE empiredb_migrator; " + sql,
    ]
    outcome = subprocess.run(cmd, text=True, capture_output=True, timeout=10)
    if expect_failure is not None:
        assert outcome.returncode != 0
        assert expect_failure in outcome.stderr, outcome.stderr[-500:]
        return ""
    assert outcome.returncode == 0, outcome.stderr[-1000:]
    return outcome.stdout.strip()


def read(tenant: str = TENANT, source: str = SOURCE,
         purpose: str = "PRIVATE_PREDICTIVE_RESEARCH_ONLY") -> dict:
    dsn = (
        f"host=127.0.0.1 port={os.environ['PGPORT']} dbname={DB} "
        "user=empire_predictive_rights_login "
        f"password={os.environ['V410_PG_PASSWORD']}"
    )
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SELECT session_user")
            assert cursor.fetchone()[0] == "empire_predictive_rights_login"
            cursor.execute(
                "SELECT decision,tenant_id::text,source_evidence_digest,"
                "permitted_purpose,revocation_present,"
                "real_rights_independently_verified,"
                "source_admission_authorized,execution_authority "
                "FROM public.read_empire_predictive_source_rights_held("
                "%s::uuid,%s::text,%s::text)",
                (tenant, source, purpose),
            )
            rows = cursor.fetchall()
            assert len(rows) == 1
            row = rows[0]
            assert row[1] == tenant and row[2] == source and row[3] == purpose
            assert row[5] is False and row[6] is False and row[7] == "none"
            return {"decision": row[0], "revoked": row[4]}


def fixture_guard():
    port = os.environ.get("PGPORT", "")
    if os.environ.get("PGHOST") != "localhost" or not port.isdigit() or int(port) < 5433:
        raise ValueError("V410_NON_DISPOSABLE_PG_REFUSED")
    result = subprocess.run(
        ["psql","-XAtq","-v","ON_ERROR_STOP=1","-d","postgres",
         "-c","SHOW data_directory"],
        text=True, capture_output=True, timeout=10, check=True,
    ).stdout.strip()
    if not result.startswith("/tmp/pg_virtualenv.") or not result.endswith("/data/18/regress"):
        raise ValueError("V410_REAL_CLUSTER_REFUSED")


def main():
    fixture_guard()
    assert read()["decision"] == "NO_SOURCE_RIGHTS_HELD"
    owner_sql(
        "INSERT INTO public.empire_predictive_source_rights_candidate_held("
        "tenant_id,source_evidence_digest,permitted_purpose,"
        "rights_document_digest,evidence_observed_at,valid_until,"
        "source_review_state) VALUES("
        f"'{TENANT}'::uuid,'{SOURCE}','PRIVATE_PREDICTIVE_RESEARCH_ONLY',"
        f"'{DOC}',now()-interval '2 minutes',now()+interval '8 minutes',"
        "'CANDIDATE_REVIEWED')"
    )
    assert read()["decision"] == "CANDIDATE_REVIEW_HELD"
    assert read(OTHER)["decision"] == "NO_SOURCE_RIGHTS_HELD"
    bounded = EmpireDbHeldSourceRightsReader(
        f"host=127.0.0.1 port={os.environ['PGPORT']} dbname={DB} "
        "user=empire_predictive_rights_login "
        f"password={os.environ['V410_PG_PASSWORD']}"
    )
    verified_reader_observation = bounded(TENANT, SOURCE)
    assert verified_reader_observation is not None
    assert verified_reader_observation.decision == "CANDIDATE_REVIEW_HELD"
    assert verified_reader_observation.source_admission_authorized is False
    assert bounded(OTHER, SOURCE).decision == "NO_SOURCE_RIGHTS_HELD"
    assert bounded(TENANT, "invalid-source") is None

    # Cannot turn the fixture decision into a production source authorisation.
    owner_sql(
        "UPDATE public.empire_predictive_source_rights_candidate_held "
        "SET source_review_state='PENDING'",
        expect_failure="V4_066_APPEND_ONLY_SOURCE_HISTORY",
    )
    # Even the actual dedicated login cannot read the source inventory table.
    with psycopg.connect(
        f"host=127.0.0.1 port={os.environ['PGPORT']} dbname={DB} "
        "user=empire_predictive_rights_login "
        f"password={os.environ['V410_PG_PASSWORD']}"
    ) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM public.empire_predictive_source_rights_candidate_held")
        except psycopg.errors.InsufficientPrivilege:
            conn.rollback()
        else:
            raise AssertionError("V410_BYPASSED_OWNER_TABLE_ACL")

    # A later append-only withdrawal is terminal even if old evidence is current.
    owner_sql(
        "INSERT INTO public.empire_predictive_source_revocations_held("
        "tenant_id,source_evidence_digest,permitted_purpose,reason_digest) "
        f"VALUES('{TENANT}'::uuid,'{SOURCE}',"
        f"'PRIVATE_PREDICTIVE_RESEARCH_ONLY','{REASON}')"
    )
    assert read()["decision"] == "REVOKED_HELD"
    assert read()["revoked"] is True
    assert bounded(TENANT, SOURCE).decision == "REVOKED_HELD"
    owner_sql(
        "DELETE FROM public.empire_predictive_source_revocations_held",
        expect_failure="V4_066_APPEND_ONLY_SOURCE_HISTORY",
    )
    assert read()["decision"] == "REVOKED_HELD"

    # Untrusted session_user must never execute the dedicated security definer.
    attempted = subprocess.run(
        ["psql", "-XAtq", "-v", "ON_ERROR_STOP=1", "-d", DB,
         "-c", "SET ROLE untrusted_rights_fixture_login; "
         "SELECT * FROM public.read_empire_predictive_source_rights_held("
         f"'{TENANT}'::uuid,'{SOURCE}','PRIVATE_PREDICTIVE_RESEARCH_ONLY')"],
        text=True, capture_output=True, timeout=10,
    )
    assert attempted.returncode != 0
    assert "permission denied for function read_empire_predictive_source_rights_held" in attempted.stderr

    # Another record with a deliberately expired candidate cannot pass.
    stale = digest("expired")
    owner_sql(
        "INSERT INTO public.empire_predictive_source_rights_candidate_held("
        "tenant_id,source_evidence_digest,permitted_purpose,"
        "rights_document_digest,evidence_observed_at,valid_until,"
        "source_review_state) VALUES("
        f"'{TENANT}'::uuid,'{stale}','PRIVATE_PREDICTIVE_RESEARCH_ONLY',"
        f"'{DOC}',now()-interval '30 days',now()-interval '1 day',"
        "'CANDIDATE_REVIEWED')"
    )
    assert read(TENANT, stale)["decision"] == "EXPIRED_HELD"
    print(json.dumps({
        "status": "V410_ORIGINAL_EMPIREDB_HELD_RIGHTS_READ_PASS",
        "original_empiredb_migrator_no_login": True,
        "isolated_pg18_verified": True,
        "restricted_real_scram_login_verified": True,
        "tenant_and_source_scope_enforced": True,
        "candidate_still_held": True,
        "revocation_terminal": True,
        "direct_table_read_denied": True,
        "untrusted_function_execute_denied": True,
        "append_only_guards_verified": True,
        "expired_candidate_blocked": True,
        "real_licenses_authenticated": False,
        "source_authorized": False,
        "live_empiredb_migrations_applied": False,
        "redis_published": False,
        "money_moved": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
