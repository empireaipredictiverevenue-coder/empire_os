"""Exact-commit, read-only release gate for STAGED original conversion registry.

This tool never connects to EmpireDB, runs DDL, provisions roles or concludes
a prior operator read was source-signed. All live deployment gates stay CLOSED.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

OWNER = Path("/home/ubuntu/empire_agents/predictive_decision_control_20261018")
SCHEMA="empire.predictive_revenue.original_conversion_dba_release_candidate.v1"
FILES=(
    "docs/commercial/STAGED_ORIGINAL_CONVERSION_REGISTRY_20261018.sql",
    "empire_os/original_conversion_registry.py",
    "empire_os/original_conversion_registry_transport.py",
    "empire_os/predictive_original_conversion_catalogue.py",
    "scripts/check_original_conversion_isolated_pg_20261018.py",
    "scripts/run_guarded_conversion_catalogue_readonly_20261021.sh",
)
REQUIRED={
    FILES[0]:(
        "STAGED ONLY",
        "CONV_REG_MIGRATOR_AUTHORITY_DRIFT",
        "CONV_REG_TENANT_RESOLVER_AUTHORITY_DRIFT",
        "CONV_REG_CLIENT_HASH_MISMATCH",
        "pg_catalog.sha256(pg_catalog.convert_to(p_payload_text,'UTF8'))",
        "server_payload_sha256",
        "original_conversion_prediction_truncate_guard",
        "FORCE ROW LEVEL SECURITY",
        "REVOKE ALL ON FUNCTION",
        "NOLOGIN NOINHERIT",
        "text,text,text,text",
    ),
    FILES[2]:(
        "original_conversion_prediction_v1(",
        "%s,%s,%s::text,%s",
        "enabled: bool = False",
    ),
    FILES[3]:(
        "original_conversion_prediction_v1(text,text,text,text)",
        "original_conversion_prediction_truncate_guard",
        "server_payload_sha256",
    ),
    FILES[4]:(
        "ISOLATED_RAW_CLIENT_HASH_VERIFICATION_PASS",
        "CONV_REG_CLIENT_HASH_MISMATCH",
        "ISOLATED_CLUSTER_DESTROYED: no production database accessed",
    ),
    FILES[5]:(
        "set -euo pipefail",
        "--run-read-only",
        "PGPASSFILE=",
    ),
}


class ReleaseCandidateHold(ValueError):
    pass


def _git(commit: str,path: str) -> bytes:
    try:
        result=subprocess.run(
            ["git","-c",f"safe.directory={OWNER}","-C",str(OWNER),
             "show",f"{commit}:{path}"],
            capture_output=True,check=True,timeout=8,
        )
        return result.stdout
    except (OSError,subprocess.SubprocessError):
        raise ReleaseCandidateHold("pinned original source unavailable") from None


def review(commit: str) -> dict:
    if type(commit) is not str or re.fullmatch("[0-9a-f]{40}",commit) is None:
        raise ReleaseCandidateHold("full immutable release SHA required")
    entries=[]
    for path in FILES:
        raw=_git(commit,path)
        current=(OWNER/path).read_bytes()
        if raw!=current or not raw or len(raw)>150_000:
            raise ReleaseCandidateHold("original source diverges from release commit")
        try:
            text=raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ReleaseCandidateHold("original source is not UTF-8") from None
        if any(token not in text for token in REQUIRED.get(path,())):
            raise ReleaseCandidateHold("source security contract missing")
        entries.append({
            "source_path":path,
            "sha256":sha256(raw).hexdigest(),
            "bytes":len(raw),
        })
    sql=(OWNER/FILES[0]).read_text()
    if ("CREATE TABLE public.original_conversion_predictions"
            not in sql or
            "CREATE ROLE empire_original_conversion_prediction_writer"
            not in sql or
            "CREATE ROLE empire_original_conversion_prediction_reader"
            not in sql or
            "GRANT empire_original_conversion_prediction_writer TO " in sql or
            "GRANT empire_original_conversion_prediction_reader TO " in sql):
        raise ReleaseCandidateHold("migration scope changed")
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":"DBA_REVIEW_CANDIDATE_NOT_AUTHORIZED_TO_DEPLOY",
        "source_commit":commit,
        "source_files":entries,
        "candidate_manifest_sha256":sha256(json.dumps(
            entries,sort_keys=True,separators=(",",":")
        ).encode()).hexdigest(),
        "canonical_database":"EmpireDB",
        "operator_console_status_reported":"DEDICATED_ORIGINAL_CONVERSION_REGISTRY_NOT_INSTALLED",
        "production_status_cryptographically_attested_by_this_check":False,
        "existing_directional_registry_is_not_a_substitute":True,
        "isolated_postgresql_executed_by_this_check":False,
        "isolated_postgresql_requires_separate_pass_receipt":True,
        "authenticated_production_metadata_requires_owner_recheck":True,
        "original_db_backup_and_point_in_time_recovery_reviewed":False,
        "tenant_resolver_dba_approval_verified":False,
        "security_definer_approval_verified":False,
        "original_migration_exact_commit_approved":False,
        "new_role_memberships_or_credentials_approved":False,
        "payment_outbound_or_customer_forecast_approved":False,
        "commercial_outcome_evidence_verified":False,
        "astra_independent_gpt6_review_verified":False,
        "scientific_training_authorized":False,
        "database_writes":False,
        "ddl_executed":False,
        "execution_authority":"none",
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only",required=True,action="store_true")
    parser.add_argument("--commit",required=True)
    args=parser.parse_args(argv)
    try:
        result=review(args.commit)
        code=0
    except (ReleaseCandidateHold,ValueError,OSError):
        code=2
        result={
            "schema_version":SCHEMA,
            "mode":"OBSERVE",
            "status":"DBA_RELEASE_CANDIDATE_SOURCE_INTEGRITY_HELD",
            "execution_authority":"none",
            "database_writes":False,
            "ddl_executed":False,
            "customer_forecast_approved":False,
        }
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return code


if __name__=="__main__":
    raise SystemExit(main())
