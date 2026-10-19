"""Held Analytics055 provenance gate, no database connections or mutations."""
import json
import pytest
from scripts import review_analytics_erasure_preflight_20261019 as review

def test_approved_source_exact_hash_and_all_activations_held():
    d=review.audit()
    assert d["status"]=="ANALYTICS055_ERASURE_SOURCE_PREPARED_PRIVILEGED_APPROVAL_HELD"
    assert d["analytics054_parent_source_verified"] is True
    assert d["analytics055_erasure_source_verified"] is True
    for key in ("real_production_analytics054_applied_verified",
        "real_production_analytics055_applied_verified",
        "maintenance_login_provisioned_by_this_migration",
        "runtime_execute_grants_by_this_migration",
        "retention_interval_approved","consent_ui_and_lawful_basis_verified",
        "data_subject_erasure_workflow_verified",
        "privacy_recovery_and_legal_hold_review_complete",
        "public_collector_active","visitor_sessions_verified",
        "realised_revenue_verified","service_restarted",
        "database_connection_opened","database_writes","website_changed"):
        assert d[key] is False
    assert d["execution_authority"]=="NONE"

def test_mutated_erasure_policy_must_not_be_reported_ready(tmp_path):
    source=review.CURRENT.read_bytes()
    assert b"REVOKE ALL ON FUNCTION" in source
    p=tmp_path/"malicious.sql"
    p.write_bytes(source.replace(b"REVOKE ALL ON FUNCTION",b"GRANT ALL ON FUNCTION ",1))
    assert review.audit(current=p)["status"]=="HELD_ANALYTICS055_MIGRATION_SOURCE_DRIFT"

def test_mutated_parent_must_not_be_reported_ready(tmp_path):
    source=review.PREDECESSOR.read_bytes()
    assert b"FORCE ROW LEVEL SECURITY" in source
    p=tmp_path/"parent.sql"
    p.write_bytes(source.replace(b"FORCE ROW LEVEL SECURITY",b"ENABLE ROW LEVEL SECURITY",1))
    d=review.audit(predecessor=p)
    assert d["analytics054_parent_source_verified"] is False
    assert d["status"]=="HELD_ANALYTICS055_MIGRATION_SOURCE_DRIFT"

def test_symlink_source_rejected(tmp_path):
    alias=tmp_path/"link.sql"
    alias.symlink_to(review.CURRENT)
    assert review.audit(current=alias)["analytics055_erasure_source_verified"] is False

def test_cli_only_read_only(capsys):
    assert review.main(["--read-only"])==0
    d=json.loads(capsys.readouterr().out)
    assert d["database_connection_opened"] is False
    for flags in ([],["--apply"],["--activate"],["--grant"],
                  ["--read-only","--restart"],["--purge"]):
        with pytest.raises(SystemExit):
            review.main(flags)
