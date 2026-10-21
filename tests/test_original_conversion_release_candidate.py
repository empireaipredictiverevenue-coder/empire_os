"""Exact-commit original-registry DBA packet fails closed and never deploys."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

import scripts.review_original_conversion_release_candidate_20261021 as gate

COMMIT="a"*40


def fixture(monkeypatch,tmp_path):
    orig=gate.OWNER
    for filename in gate.FILES:
        dst=tmp_path/filename
        dst.parent.mkdir(parents=True,exist_ok=True)
        dst.write_bytes((orig/filename).read_bytes())
    monkeypatch.setattr(gate,"OWNER",tmp_path)
    monkeypatch.setattr(
        gate,"_git",lambda commit,path: (tmp_path/path).read_bytes()
    )
    return tmp_path


def test_readonly_packet_never_authorizes_ddl(monkeypatch,tmp_path):
    fixture(monkeypatch,tmp_path)
    result=gate.review(COMMIT)
    assert result["status"]=="DBA_REVIEW_CANDIDATE_NOT_AUTHORIZED_TO_DEPLOY"
    assert result["source_commit"]==COMMIT
    assert len(result["source_files"])==len(gate.FILES)
    assert len(result["candidate_manifest_sha256"])==64
    for prop in (
        "production_status_cryptographically_attested_by_this_check",
        "isolated_postgresql_executed_by_this_check",
        "original_db_backup_and_point_in_time_recovery_reviewed",
        "tenant_resolver_dba_approval_verified",
        "security_definer_approval_verified",
        "original_migration_exact_commit_approved",
        "new_role_memberships_or_credentials_approved",
        "payment_outbound_or_customer_forecast_approved",
        "commercial_outcome_evidence_verified",
        "astra_independent_gpt6_review_verified",
        "scientific_training_authorized",
        "database_writes","ddl_executed",
    ):
        assert result[prop] is False
    assert result["execution_authority"]=="none"


def test_candidate_refuses_migration_source_drift(monkeypatch,tmp_path):
    fixture(monkeypatch,tmp_path)
    first=gate.FILES[0]
    original=(tmp_path/first).read_bytes()
    monkeypatch.setattr(
        gate,"_git",
        lambda commit,path: original if path==first
        else (tmp_path/path).read_bytes()
    )
    (tmp_path/first).write_bytes(original+b"\n-- unreviewed code")
    with pytest.raises(gate.ReleaseCandidateHold,match="diverges"):
        gate.review(COMMIT)


def test_candidate_refuses_removed_client_hash_binding(monkeypatch,tmp_path):
    fixture(monkeypatch,tmp_path)
    first=gate.FILES[0]
    raw=(tmp_path/first).read_text().replace("CONV_REG_CLIENT_HASH_MISMATCH","UNSAFE_REMOVED")
    (tmp_path/first).write_text(raw)
    with pytest.raises(gate.ReleaseCandidateHold,match="contract"):
        gate.review(COMMIT)


@pytest.mark.parametrize("invalid",["a","a"*39,"a"*41,"0"*39+"g",None,123])
def test_bad_full_sha_held_without_fetch(monkeypatch,tmp_path,invalid):
    fixture(monkeypatch,tmp_path)
    with pytest.raises(gate.ReleaseCandidateHold):
        gate.review(invalid)


def test_cli_source_hold_safe_without_side_effects(capsys):
    assert gate.main(["--read-only","--commit","b"*40])==2
    output=capsys.readouterr().out
    assert "DBA_RELEASE_CANDIDATE_SOURCE_INTEGRITY_HELD" in output
    assert '"database_writes": false' in output
    assert '"ddl_executed": false' in output


def test_raw_writer_transport_and_migration_signature_remain_aligned():
    from empire_os.original_conversion_registry_transport import WRITE_SQL
    source=(Path(__file__).resolve().parents[1]/
      "docs/commercial/STAGED_ORIGINAL_CONVERSION_REGISTRY_20261018.sql").read_text()
    assert "%s,%s,%s::text,%s" in WRITE_SQL
    assert "p_payload_text text" in source
    assert "CONV_REG_CLIENT_HASH_MISMATCH" in source
    assert "record_original_conversion_prediction_v1(\n  text,text,text,text)" in source
    assert "CONV_REG_TENANT_RESOLVER_AUTHORITY_DRIFT" in source
    assert "CONV_REG_MIGRATOR_AUTHORITY_DRIFT" in source
