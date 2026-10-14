"""Exact-record canonical repair for one externally verified stop-contact reply."""
import json
from copy import deepcopy

import pytest
from scripts import recover_single_tarrytown_stop_20261014 as recovery


def record(**kwargs):
    result = {
        "reply_id": recovery.REPLY_ID,
        "intent_id": recovery.INTENT_ID,
        "provider_id": recovery.PROVIDER_ID,
        "sender": recovery.CONTACT,
        "recipient": recovery.CONTACT,
        "subject": recovery.SUBJECT,
        "date_utc": recovery.ORIGINAL_DATE,
        "body_state": "PLACEHOLDER",
        "classification": "unclassified",
        "intent_status": "replied",
        "provider": "resend",
        "body_unavailable": "true",
        "suppression_count": 0,
    }
    result.update(kwargs)
    return result


def test_verified_provider_and_canonical_id_are_both_required():
    proof = recovery.check_proof(record())
    assert proof["provider_identity_verified"] is True
    assert proof["ready_for_exact_recovery"] is True
    assert proof["canonical_suppression_verified"] is False


@pytest.mark.parametrize("bad", [
    {"reply_id":"11111111-1111-4111-8111-111111111111"},
    {"intent_id":"11111111-1111-4111-8111-111111111111"},
    {"provider_id":"someone-elses-message"},
    {"recipient":"original-recipient@example.com"},
    {"sender":"another-person@example.com"},
    {"subject":"Re: unrelated conversation"},
    {"date_utc":"2026-09-24"},
    {"body_state":"UNEXPECTED"},
    {"classification":"positive"},
    {"intent_status":"approved"},
    {"provider":"other"},
    {"body_unavailable":"false"},
    {"suppression_count":2},
])
def test_malformed_or_wrong_record_fails_closed(bad):
    with pytest.raises(recovery.RecoveryHeld):
        recovery.check_proof(record(**bad))


def test_partial_prior_update_requires_manual_reconciliation():
    with pytest.raises(recovery.RecoveryHeld, match="PARTIALLY_RECOVERED"):
        recovery.check_proof(record(body_state="STOP", classification="unclassified"))


def test_sql_targets_one_known_message_only_and_governed_classifier():
    sql = recovery._apply_sql()
    assert "SET LOCAL ROLE empire_reply_ingest" in sql
    assert sql.count("UPDATE public.outbound_replies") == 1
    assert "PERFORM public.classify_outbound_reply" in sql
    assert recovery.REPLY_ID in sql
    assert recovery.INTENT_ID in sql
    assert recovery.PROVIDER_ID in sql
    assert "r.body_text IS DISTINCT FROM '[provider body unavailable]'" in sql
    assert "r.normalized_recipient" in sql
    assert "r.normalized_from_contact" in sql
    assert "unquoted_visible_reply_only" in sql
    assert "BEGIN;" in sql and "COMMIT;" in sql
    assert "send_email" not in sql


def test_default_requires_exact_flags(capsys):
    assert recovery.main([]) == 2
    assert "CHOOSE_REVIEW_OR_EXACT_APPROVED_APPLY" in capsys.readouterr().out
    assert recovery.main(["--apply"]) == 2
    assert "EXACT_RECIPIENT_APPROVAL_REQUIRED" in capsys.readouterr().out


def test_non_root_has_no_db_access(monkeypatch):
    monkeypatch.setattr(recovery.os, "geteuid", lambda: 1000)
    with pytest.raises(recovery.RecoveryHeld, match="ROOT_REQUIRED"):
        recovery.restore(apply=False)


def test_review_only_no_mutations(monkeypatch):
    monkeypatch.setattr(recovery.os, "geteuid", lambda: 0)
    monkeypatch.setattr(recovery, "_read", lambda: record())
    monkeypatch.setattr(
        recovery, "_psql",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("REVIEW_MUST_NOT_MUTATE")),
    )
    result = recovery.restore(apply=False)
    assert result["status"] == "REVIEW_ONLY"
    assert result["body_state_before"] == "PLACEHOLDER"
    assert result["database_writes"] is False
    assert result["email_sent"] is False


def test_approved_apply_updates_only_once_then_checks_suppression(monkeypatch):
    monkeypatch.setattr(recovery.os, "geteuid", lambda: 0)
    rows = iter([
        record(),
        record(body_state="STOP", classification="unsubscribe",
               body_unavailable="false", suppression_count=1, intent_status="suppressed"),
    ])
    monkeypatch.setattr(recovery, "_read", lambda: next(rows))
    writes = []
    monkeypatch.setattr(recovery, "_psql", lambda sql, **kw: writes.append(sql) or "")
    result = recovery.restore(apply=True)
    assert len(writes) == 1
    assert "UPDATE public.outbound_replies" in writes[0]
    assert result["status"] == "WOLFGANG_STOP_RECOVERED_AND_SUPPRESSED"
    assert result["no_contact_enforced"] is True
    assert result["database_writes"] is True
    assert result["email_sent"] is False


def test_recovery_idempotence_has_no_duplicate_classification(monkeypatch):
    monkeypatch.setattr(recovery.os, "geteuid", lambda: 0)
    already = record(body_state="STOP", classification="unsubscribe",
                     body_unavailable="false", suppression_count=1,
                     intent_status="suppressed")
    monkeypatch.setattr(recovery, "_read", lambda: already)
    monkeypatch.setattr(
        recovery, "_psql",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("SECOND_WRITE")),
    )
    result = recovery.restore(apply=True)
    assert result["database_writes"] is False


def test_no_false_success_when_postcommit_suppression_missing(monkeypatch):
    monkeypatch.setattr(recovery.os, "geteuid", lambda: 0)
    rows = iter([record(), record(body_state="STOP", classification="unclassified",
                                  suppression_count=0, body_unavailable="false")])
    monkeypatch.setattr(recovery, "_read", lambda: next(rows))
    monkeypatch.setattr(recovery, "_psql", lambda *_a, **_kw: "")
    with pytest.raises(recovery.RecoveryHeld):
        recovery.restore(apply=True)

@pytest.fixture(autouse=True)
def no_network_in_unit_tests(monkeypatch):
    monkeypatch.setattr(
        recovery, "_probe_live_receiving_credential",
        lambda: "RECEIVING_CREDENTIAL_UNAUTHORIZED",
    )


def test_mismatched_live_provider_proof_blocks_even_valid_database_record(monkeypatch):
    monkeypatch.setattr(recovery.os, "geteuid", lambda: 0)
    monkeypatch.setattr(recovery, "_read", lambda: record())
    monkeypatch.setattr(
        recovery, "_probe_live_receiving_credential",
        lambda: "RECEIVED_PROVIDER_BODY_OR_IDENTITY_CONFLICT",
    )
    with pytest.raises(recovery.RecoveryHeld, match="LIVE_PROVIDER_RECORD_CONFLICT"):
        recovery.restore(apply=True)


def test_limited_live_provider_credentials_do_not_discard_connected_account_evidence(monkeypatch):
    monkeypatch.setattr(recovery.os, "geteuid", lambda: 0)
    monkeypatch.setattr(recovery, "_read", lambda: record())
    result = recovery.restore(apply=False)
    assert result["live_inbound_receiving_probe"] == "RECEIVING_CREDENTIAL_UNAUTHORIZED"
    assert result["source"] == "SIGNED_CANONICAL_REPLY_PLUS_CONNECTED_PROVIDER_GET"
    assert result["email_sent"] is False


def test_review_and_atomic_guard_accept_same_existing_suppressed_states():
    # Regression for 14 Oct live PostgreSQL failure: read-only evidence
    # accepted suppressed/preclassified rows while the DO block rejected them.
    sql = recovery._apply_sql()
    assert "r.classification NOT IN ('unclassified','unsubscribe')" in sql
    assert "r.status NOT IN ('sent','delivered','replied','suppressed')" in sql
    assert "existing_suppression<>1" in sql
    assert "SELECT count(*) INTO existing_suppression" in sql
    assert "IF r.classification='unclassified' OR r.status<>'suppressed' THEN" in sql
    assert "IS DISTINCT FROM" in sql
    assert "ERRCODE='P1001'" in sql
    assert "ERRCODE='P1002'" in sql
    assert "ERRCODE='P1003'" in sql
    accepted = recovery.check_proof(record(
        classification="unsubscribe",
        intent_status="suppressed",
        suppression_count=1,
    ))
    assert accepted["ready_for_exact_recovery"] is True
    assert accepted["classification"] == "unsubscribe"
    assert accepted["intent_status"] == "suppressed"


def test_preclassified_without_actual_suppression_is_held():
    with pytest.raises(
        recovery.RecoveryHeld,
        match="PRECLASSIFIED_OPT_OUT_WITHOUT_CANONICAL_SUPPRESSION",
    ):
        recovery.check_proof(record(
            classification="unsubscribe", intent_status="suppressed",
            suppression_count=0,
        ))


@pytest.mark.parametrize("sqlstate", ["P1001", "P1002", "P1003", "42703", "42501"])
def test_real_psql_error_state_reported_without_postgres_stderr(monkeypatch, sqlstate):
    monkeypatch.setattr(recovery.os, "geteuid", lambda: 0)
    class SimulatedPsql:
        returncode = 3
        stderr = f"ERROR:  {sqlstate}\nSTATEMENT: PRIVATE_CREDENTIAL_AND_EMAIL"
        stdout = ""
    monkeypatch.setattr(recovery.subprocess, "run", lambda *a, **kw: SimulatedPsql())
    with pytest.raises(
        recovery.RecoveryHeld,
        match="CANONICAL_POSTGRES_SQLSTATE_" + sqlstate,
    ) as captured:
        recovery._psql("SELECT 1;", read_output=True)
    assert "PRIVATE_CREDENTIAL_AND_EMAIL" not in str(captured.value)


def test_atomic_failure_has_distinct_reason_and_cannot_falsely_report_recovery(monkeypatch):
    monkeypatch.setattr(recovery.os, "geteuid", lambda: 0)
    monkeypatch.setattr(recovery, "_read", lambda: record())
    def fail(_query, *, read_output):
        assert read_output is False
        raise recovery.RecoveryHeld("CANONICAL_POSTGRES_SQLSTATE_P1003")
    monkeypatch.setattr(recovery, "_psql", fail)
    with pytest.raises(
        recovery.RecoveryHeld,
        match="ATOMIC_RECOVERY_CANONICAL_POSTGRES_SQLSTATE_P1003",
    ):
        recovery.restore(apply=True)


def test_postcommit_intent_still_replied_cannot_claim_completed(monkeypatch):
    monkeypatch.setattr(recovery.os, "geteuid", lambda: 0)
    calls = iter([
        record(),
        record(
            body_state="STOP", classification="unsubscribe",
            body_unavailable="false", suppression_count=1,
            intent_status="replied",
        ),
    ])
    monkeypatch.setattr(recovery, "_read", lambda: next(calls))
    monkeypatch.setattr(recovery, "_psql", lambda *_a, **_kw: "")
    with pytest.raises(recovery.RecoveryHeld, match="CANONICAL_POSTCOMMIT_RECOVERY_UNVERIFIED"):
        recovery.restore(apply=True)
