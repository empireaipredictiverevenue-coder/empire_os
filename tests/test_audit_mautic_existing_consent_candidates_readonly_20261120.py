"""Canonical consent audit is read-only and cannot promote response consent."""
from __future__ import annotations

import json
from subprocess import CompletedProcess

from scripts import audit_mautic_existing_consent_candidates_readonly_20261120 as audit


def test_zero_marketing_consent_does_not_authorise_source_or_customer():
    result = CompletedProcess(
        args=[], returncode=0,
        stdout=json.dumps({
            "consent_evidence_rows": 3,
            "ongoing_marketing_claim_true_rows": 0,
            "response_only_consent_rows": 3,
            "ongoing_marketing_claim_rows_with_prospect_id": 0,
            "first_party_commercial_marketing_claim_true": 0,
        }),
    )
    packet = audit.classify(result)
    assert packet["status"] == "CENSUS_COMPLETE_CLAIMS_ONLY_NOT_CONTACT_AUTHORITY"
    assert packet["counts"]["ongoing_marketing_claim_true_rows"] == 0
    assert packet["counts"]["response_only_consent_rows"] == 3
    assert packet["marketing_consent_verified"] is False
    assert packet["source_mapping_authorized"] is False
    assert packet["mautic_contacts_created"] is False
    assert packet["outbound_authorized"] is False


def test_untrusted_query_or_schema_error_fails_closed():
    for bad in (
        None,
        CompletedProcess(args=[], returncode=1, stdout="{}"),
        CompletedProcess(args=[], returncode=0, stdout='{"contact_email": "foo@example.com"}'),
        CompletedProcess(args=[], returncode=0, stdout='{"consent_evidence_rows": true}'),
    ):
        result = audit.classify(bad)
        assert result["status"] == "CANONICAL_SOURCE_NOT_READABLE_HOLD"
        assert result["marketing_consent_verified"] is False
        assert result["outbound_authorized"] is False


def test_readonly_db_sql_and_root_access_are_guarded(monkeypatch):
    assert "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY" in audit.SQL
    assert "ROLLBACK" in audit.SQL
    assert "statement_timeout" in audit.SQL
    assert not any(x in audit.SQL.upper() for x in (
        "INSERT INTO", "UPDATE PUBLIC.", "DELETE FROM", "CREATE TABLE",
        "DROP TABLE", "ALTER TABLE", "COMMIT;",
    ))
    monkeypatch.setattr(audit.os, "geteuid", lambda: 1000)
    assert audit.run()["status"] == "CANONICAL_SOURCE_NOT_READABLE_HOLD"
