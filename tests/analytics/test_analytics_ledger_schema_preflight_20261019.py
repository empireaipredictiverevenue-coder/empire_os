"""Prepared-only immutable migration source audit and denied apply flags."""
import json
import pytest

from scripts import review_analytics_ledger_schema_20261019 as module


def test_known_exact_schema_candidate_checked_without_db_connection():
    result=module.audit()
    assert result["status"]=="ANALYTICS054_SCHEMA_STAGED_FOUNDER_DB_APPROVAL_REQUIRED"
    assert result["migration_source_integrity_verified"] is True
    for field in (
      "migration_applied_to_production_verified","schema_activation_authorised",
      "runtime_ingest_role_granted","public_collector_active",
      "website_analytics_consent_verified","data_retention_and_erasure_policy_approved",
      "real_visitor_sessions_verified","crm_attribution_verified",
      "realised_revenue_verified","database_connections_opened","database_writes",
      "services_restarted","public_website_changed",
    ):
        assert result[field] is False
    assert result["execution_authority"]=="NONE"


def test_tampered_or_symlink_source_cannot_be_reported_ready(tmp_path):
    source=module.MIGRATION.read_bytes()
    broken=tmp_path/"altered.sql"
    assert b"REVOKE ALL ON TABLE" in source
    broken.write_bytes(source.replace(b"REVOKE ALL ON TABLE",b"GRANT ALL ON TABLE ",1))
    assert module.audit(broken)["status"]=="HELD_ANALYTICS054_SCHEMA_SOURCE_CHANGED"
    alias=tmp_path/"alias.sql"
    alias.symlink_to(module.MIGRATION)
    assert module.audit(alias)["status"]=="HELD_ANALYTICS054_SCHEMA_SOURCE_CHANGED"


def test_only_readonly_flag_accepted(capsys):
    assert module.main(["--read-only"])==0
    reported=json.loads(capsys.readouterr().out)
    assert reported["mode"]=="READ_ONLY"
    for args in ([],["--apply"],["--restart"],["--activate-collector"],
                 ["--read-only","--migrate"],["--read-only","--enable"]):
        with pytest.raises(SystemExit):
            module.main(args)
