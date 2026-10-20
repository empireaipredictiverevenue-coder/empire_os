"""Offline management authentication, tenant isolation and audit regression tests."""
from datetime import datetime, timedelta, timezone
import time

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.inbound_access_audit import RecoveryAccessAudit
from empire_os.inbound_management_api import create_inbound_management_router
from empire_os.inbound_management_auth import (
    AUDIENCE, ISSUER, RecoveryAccessDenied, RecoveryActor,
    authenticate_recovery_reader,
)
from empire_os.inbound_recovery_store import OfflineRecoveryStore
from empire_os.inbound_revenue_recovery import RecoveryEvent
from empire_os.inbound_tenant_directory import (
    OfflineTenantDirectory, RecoveryTenant,
)

SECRET = "empire-management-test-key-only-1234567890-do-not-deploy"
AUDIT_KEY = "test-management-audit-key-minimum-32-bytes-abc"


def token(*, tenant="alpha", scopes=None, duration=600, issued=None,
          key=SECRET, audience=AUDIENCE, issuer=ISSUER):
    t = int(time.time()) if issued is None else issued
    claims = {
        "iss": issuer, "aud": audience, "tenant_id": tenant,
        "sub": "reviewer-1", "jti": "test-authentication-nonce",
        "iat": t, "nbf": t, "exp": t + duration,
        "scopes": scopes if scopes is not None
        else ["recovery:read", "recovery:queue", "recovery:patterns"],
    }
    return "Bearer " + jwt.encode(claims, key, algorithm="HS256")


def missed_event(tenant, event_id, call_id):
    return RecoveryEvent(
        tenant_id=tenant, event_id=event_id, call_id=call_id,
        occurred_at="2026-10-20T09:00:00+00:00",
        kind="unanswered", origin="provider", verified=True, synthetic=False,
    )


@pytest.fixture()
def config(tmp_path, monkeypatch):
    db = tmp_path / "tenant.db"
    evidence = tmp_path / "evidence.db"
    audit = tmp_path / "audit.db"
    with OfflineTenantDirectory(db) as directory:
        directory.register_offline(RecoveryTenant(
            "alpha", "Alpha Roofing", "Europe/London",
            state="approved", reporting_approved=True,
        ))
        directory.register_offline(RecoveryTenant(
            "beta", "Beta Plumbing", "America/New_York",
            state="approved", reporting_approved=True,
        ))
        directory.register_offline(RecoveryTenant(
            "pending", "Pending Account", "Europe/London",
            state="draft", reporting_approved=False,
        ))
    with OfflineRecoveryStore(evidence) as store:
        store.append_offline(missed_event("alpha", "alpha-event", "alpha-call"))
        store.append_offline(missed_event("beta", "beta-event", "beta-call"))
    monkeypatch.setenv("EMPIRE_INBOUND_MANAGER_TENANT_DB", str(db))
    monkeypatch.setenv("EMPIRE_INBOUND_MANAGER_EVIDENCE_DB", str(evidence))
    monkeypatch.setenv("EMPIRE_INBOUND_MANAGER_AUDIT_DB", str(audit))
    monkeypatch.setenv("EMPIRE_INBOUND_MANAGER_JWT_KEY", SECRET)
    monkeypatch.setenv("EMPIRE_INBOUND_MANAGER_AUDIT_KEY", AUDIT_KEY)
    monkeypatch.setenv("EMPIRE_INBOUND_MANAGER_ENABLED", "true")
    app = FastAPI()
    app.include_router(create_inbound_management_router())
    yield TestClient(app), audit, evidence


def get(client, endpoint, authorization=None, **params):
    headers = {"Authorization": authorization} if authorization else {}
    return client.get(
        "/v1/inbound-recovery/management/" + endpoint,
        params=params or None, headers=headers,
    )


def test_management_is_dark_by_default(config, monkeypatch):
    client, audit, _ = config
    monkeypatch.delenv("EMPIRE_INBOUND_MANAGER_ENABLED")
    response = get(client, "scorecard", token())
    assert response.status_code == 404
    assert not audit.exists()


def test_rejects_missing_wrong_and_badly_signed_credentials(config):
    client, audit, _ = config
    assert get(client, "scorecard").status_code == 401
    assert get(client, "scorecard", token(key="wrong-test-signing-key-0123456789")).status_code == 401
    assert get(client, "scorecard", token(audience="wrong-audience")).status_code == 401
    assert get(client, "scorecard", token(issuer="wrong-issuer")).status_code == 401
    assert not audit.exists()


def test_short_lived_token_has_scope_and_tenant(config):
    client, audit, _ = config
    result = get(client, "scorecard", token(tenant="alpha"))
    assert result.status_code == 200, result.text
    assert result.headers["cache-control"] == "no-store"
    body = result.json()
    assert body["tenant_id"] == "alpha"
    assert body["missed_calls"] == 1
    assert body["evidence_level"] == "offline_not_a_live_revenue_claim"
    assert "beta-call" not in result.text
    assert "alpha-call" not in result.text  # Scorecard excludes caller-specific IDs.
    assert audit.is_file()


def test_queue_is_tenant_scoped_and_never_authorizes_calls(config):
    client, audit, _ = config
    result = get(client, "opportunities", token(tenant="alpha"),
                 as_of="2026-10-20T09:20:00+00:00")
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["queue_total"] == 1
    assert body["tickets"][0]["call_id"] == "alpha-call"
    assert "beta-call" not in result.text
    assert body["customer_contact_authorized"] is False


def test_reporting_timezone_comes_from_stored_tenant_not_client(config):
    client, _, _ = config
    result = get(
        client, "patterns", token(tenant="beta"),
        as_of="2026-10-20T10:00:00+00:00",
    )
    assert result.status_code == 200, result.text
    assert result.json()["timezone"] == "America/New_York"
    assert result.json()["sample_size"] == 1


def test_missing_scope_blocked_by_endpoint(config):
    client, audit, _ = config
    limited = token(scopes=["recovery:read"])
    assert get(client, "scorecard", limited).status_code == 200
    assert get(client, "opportunities", limited).status_code == 401
    assert get(client, "patterns", limited).status_code == 401
    with RecoveryAccessAudit(audit, audit_key=AUDIT_KEY) as log:
        assert log.row_count() == 1
        assert log.verify_chain()


def test_expired_long_lived_and_unapproved_tenants_denied(config):
    client, audit, _ = config
    assert get(client, "scorecard", token(issued=int(time.time()) - 1800)).status_code == 401
    assert get(client, "scorecard", token(duration=3600)).status_code == 401
    assert get(client, "scorecard", token(tenant="pending")).status_code == 403
    assert get(client, "scorecard", token(tenant="absent")).status_code == 403
    assert not audit.exists()


def test_clock_and_claim_flags_fail_closed():
    with pytest.raises(RecoveryAccessDenied):
        authenticate_recovery_reader(
            token(duration=3600), signing_secret=SECRET,
            required_scope="recovery:read",
        )
    with pytest.raises(RecoveryAccessDenied):
        authenticate_recovery_reader(
            token(scopes=["recovery:read", "something:else"]),
            signing_secret=SECRET, required_scope="recovery:read",
        )


def test_evidence_db_missing_fails_closed_not_empty(config, monkeypatch):
    client, audit, _ = config
    monkeypatch.setenv("EMPIRE_INBOUND_MANAGER_EVIDENCE_DB", "/nonexistent/untrusted.db")
    assert get(client, "scorecard", token()).status_code == 503
    with RecoveryAccessAudit(audit, audit_key=AUDIT_KEY) as log:
        assert log.verify_chain()
        assert log.row_count() == 1


def test_audit_failure_blocks_reporting(config, monkeypatch):
    client, audit, _ = config
    monkeypatch.setenv("EMPIRE_INBOUND_MANAGER_AUDIT_KEY", "weak")
    assert get(client, "scorecard", token()).status_code == 503
    assert not audit.exists()


def test_audit_log_is_hmac_chained_and_tampering_detected(config):
    client, audit, _ = config
    assert get(client, "scorecard", token()).status_code == 200
    assert get(client, "scorecard", token(tenant="beta")).status_code == 200
    with RecoveryAccessAudit(audit, audit_key=AUDIT_KEY) as log:
        assert log.row_count() == 2
        assert log.verify_chain()
        log.db.execute("UPDATE access_audit SET operation='forged' WHERE seq=1")
        log.db.commit()
        assert not log.verify_chain()


def test_tenant_directory_read_only(config, monkeypatch):
    _, _, _ = config
    path = monkeypatch.getenv("EMPIRE_INBOUND_MANAGER_TENANT_DB") if hasattr(monkeypatch, "getenv") else None
    # Access paths are resolved from server configuration, never URL params.
    from os import environ
    with OfflineTenantDirectory(environ["EMPIRE_INBOUND_MANAGER_TENANT_DB"], read_only=True) as directory:
        assert directory.get("alpha").may_review
        assert not directory.get("pending").may_review
        with pytest.raises(ValueError, match="read_only"):
            directory.register_offline(RecoveryTenant("gamma", "Gamma", "Europe/London"))


def test_tenant_profile_is_derived_from_token_and_records_audit(config):
    client, audit, _ = config
    reply = get(client, "profile", token(tenant="beta"))
    assert reply.status_code == 200
    body = reply.json()
    assert body["tenant_id"] == "beta"
    assert body["business_name"] == "Beta Plumbing"
    assert body["timezone"] == "America/New_York"
    assert body["live_telephony"] == "not_configured_by_this_api"
    assert reply.headers["cache-control"] == "no-store"
    with RecoveryAccessAudit(audit, audit_key=AUDIT_KEY) as log:
        assert log.row_count() == 1
        assert log.verify_chain()


def test_existing_audit_tamper_blocks_next_read(config):
    client, audit, _ = config
    assert get(client, "scorecard", token()).status_code == 200
    with RecoveryAccessAudit(audit, audit_key=AUDIT_KEY) as log:
        log.db.execute("UPDATE access_audit SET tenant_id='intruder' WHERE seq=1")
        log.db.commit()
        assert not log.verify_chain()
    result = get(client, "profile", token())
    assert result.status_code == 503


def test_management_never_accepts_client_supplied_tenant_switch(config):
    client, _, _ = config
    result = get(client, "scorecard", token(tenant="alpha"), tenant_id="beta")
    assert result.status_code == 200
    assert result.json()["tenant_id"] == "alpha"


def test_no_reporting_if_directory_downgraded(config, monkeypatch):
    client, _, _ = config
    from os import environ
    with OfflineTenantDirectory(environ["EMPIRE_INBOUND_MANAGER_TENANT_DB"]) as directory:
        directory.register_offline(RecoveryTenant(
            "alpha", "Alpha Roofing", "Europe/London",
            state="suspended", reporting_approved=False,
        ))
    assert get(client, "scorecard", token(tenant="alpha")).status_code == 403


def test_knowledge_status_is_tenant_scoped_and_requires_scope(config, monkeypatch, tmp_path):
    from empire_os.inbound_knowledge_store import OfflineKnowledgeRepository
    from empire_os.inbound_tenant_knowledge import TenantKnowledgePack, KnowledgeFact

    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    path = tmp_path / "knowledge.db"
    fact = KnowledgeFact(
        tenant_id="alpha", fact_id="f1",
        question="Do you fit solar panels",
        answer="We fit solar systems.",
        source_ref="reviewed-policy-a", reviewed_by="client-admin",
        reviewed_at=(now - timedelta(days=1)).isoformat(),
        expires_at=(now + timedelta(days=30)).isoformat(),
        topic="services", approved=True, synthetic=False,
    )
    pack = TenantKnowledgePack(
        tenant_id="alpha", business_name="Alpha Roofing",
        version=1, facts=(fact,), activated=False,
    )
    with OfflineKnowledgeRepository(path) as repo:
        repo.store_draft_offline(pack)
        repo.activate_offline("alpha", 1, as_of=now)
    monkeypatch.setenv("EMPIRE_INBOUND_MANAGER_KNOWLEDGE_DB", str(path))
    client, audit, _ = config

    assert get(client, "knowledge-status", token(tenant="alpha")).status_code == 401
    allowed_alpha = get(
        client, "knowledge-status",
        token(tenant="alpha", scopes=["recovery:knowledge"]),
    )
    assert allowed_alpha.status_code == 200, allowed_alpha.text
    assert allowed_alpha.json()["active_version"] == 1
    assert allowed_alpha.json()["approved_facts"] == 1
    assert allowed_alpha.json()["live_knowledge_serving_enabled"] is False
    assert "We fit solar systems" not in allowed_alpha.text

    allowed_beta = get(
        client, "knowledge-status",
        token(tenant="beta", scopes=["recovery:knowledge"]),
    )
    assert allowed_beta.status_code == 200
    assert allowed_beta.json()["active_version"] is None
    with RecoveryAccessAudit(audit, audit_key=AUDIT_KEY) as log:
        assert log.row_count() == 2
        assert log.verify_chain()


def test_knowledge_status_fails_closed_without_configured_db(config):
    client, audit, _ = config
    result = get(
        client, "knowledge-status",
        token(tenant="alpha", scopes=["recovery:knowledge"]),
    )
    assert result.status_code == 503


def test_workflow_status_is_tenant_scoped_and_scope_protected(config, monkeypatch, tmp_path):
    from empire_os.inbound_booking_store import OfflineBookingWorkflowStore
    from empire_os.inbound_booking_workflow import InboundWorkflowEvent
    from empire_os.inbound_contact_identity import pseudonymise_inbound_contact

    key = "management-workflow-test-contact-key-32-bytes"
    def make_event(tenant, call):
        return InboundWorkflowEvent(
            tenant_id=tenant, event_id="workflow-" + tenant,
            call_id=call, contact_key=pseudonymise_inbound_contact(
                "+442071234567", tenant_id=tenant, signing_key=key,
            ),
            kind="callback_requested",
            occurred_at="2026-10-20T09:00:00+00:00",
            origin="operator_review", evidence_ref="operator-evidence-" + tenant,
            verified=True, synthetic=False,
        )

    file = tmp_path / "workflow.db"
    with OfflineBookingWorkflowStore(file) as store:
        store.append_offline(make_event("alpha", "alpha-workflow"))
        store.append_offline(make_event("beta", "beta-workflow"))
    monkeypatch.setenv("EMPIRE_INBOUND_MANAGER_WORKFLOW_DB", str(file))
    client, audit, _ = config
    unauthorized = get(client, "workflow", token(tenant="alpha"),
                       as_of="2026-10-20T10:00:00Z")
    assert unauthorized.status_code == 401
    granted = get(client, "workflow",
                  token(tenant="alpha", scopes=["recovery:workflow"]),
                  as_of="2026-10-20T10:00:00Z", tenant_id="beta")
    assert granted.status_code == 200, granted.text
    body = granted.json()
    assert body["tenant_id"] == "alpha"
    assert body["call_workflows_total"] == 1
    assert body["workflows"][0]["call_id"] == "alpha-workflow"
    assert "beta-workflow" not in granted.text
    assert body["outbound_sent"] is False
    assert body["contact_keys_returned"] is False
    assert granted.headers["cache-control"] == "no-store"
    with RecoveryAccessAudit(audit, audit_key=AUDIT_KEY) as log:
        assert log.row_count() == 1
        assert log.verify_chain()


def test_workflow_status_requires_existing_private_store(config):
    client, audit, _ = config
    result = get(client, "workflow",
                 token(tenant="alpha", scopes=["recovery:workflow"]),
                 as_of="2026-10-20T10:00:00Z")
    assert result.status_code == 503
    with RecoveryAccessAudit(audit, audit_key=AUDIT_KEY) as log:
        assert log.verify_chain()


def test_workflow_manager_disabled_mode_never_reads_or_logs(config, monkeypatch):
    client, audit, _ = config
    monkeypatch.delenv("EMPIRE_INBOUND_MANAGER_ENABLED")
    result = get(client, "workflow", token(scopes=["recovery:workflow"]))
    assert result.status_code == 404
    assert not audit.exists()
