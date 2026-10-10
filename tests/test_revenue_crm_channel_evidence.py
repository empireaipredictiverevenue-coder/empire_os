"""Independent fail-closed CRM contact/channel proof tests.

No database connection, raw PII, sender, webhook, SMS, push or browser storage.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.revenue_crm_api import create_revenue_crm_router
from empire_os.revenue_crm_channel_evidence import (
    ChannelEvidenceError, TrustedChannelEvidence, review_channel_evidence,
)

TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"
PROSPECT = "00000000-0000-0000-0000-000000000201"
NOW = datetime(2026, 10, 10, 21, 0, tzinfo=timezone.utc)


def row(**kwargs):
    return {
        "tenant_id": TENANT, "prospect_id": PROSPECT, "prospect_status": "new",
        **kwargs,
    }


def proof(**kwargs):
    values = {
        "tenant_id": TENANT, "prospect_id": PROSPECT, "channel": "email",
        "identity_bound": True, "consent_state": "verified_opt_in",
        "suppression_state": "not_found",
        "consent_evidence_ref": "canonical-consent-001",
        "suppression_evidence_ref": "canonical-suppression-check-001",
        "observed_at": NOW - timedelta(minutes=2),
    }
    values.update(kwargs)
    return TrustedChannelEvidence(**values)


def assert_no_action(result):
    assert result["mode"] == "OBSERVE"
    assert result["send_authorized"] is False
    assert result["followup_authorized"] is False
    assert result["subscription_created"] is False
    assert result["marketing_eligibility_proven"] is False
    assert result["contact_fields_disclosed"] is False
    assert result["execution_authority"] == "none"
    assert "@" not in str(result)
    assert "canonical-consent-001" not in str(result)


def test_missing_proof_is_hold_for_every_channel():
    for channel in ("email", "sms", "web_push"):
        result = review_channel_evidence(row(), channel=channel, evidence=None, now=NOW)
        assert result["review_status"] == "HOLD_MISSING_EVIDENCE"
        assert result["channel_consent_state"] == "unknown"
        assert result["canonical_suppression_state"] == "unknown"
        assert "CANONICAL_SUPPRESSION_UNKNOWN" in result["blockers"]
        assert "EXPLICIT_CHANNEL_CONSENT_UNVERIFIED" in result["blockers"]
        assert_no_action(result)


@pytest.mark.parametrize("changes,expected", [
    ({"suppression_state": "suppressed"}, "CANONICAL_SUPPRESSION_MATCH"),
    ({"consent_state": "opted_out"}, "EXPLICIT_CHANNEL_OPT_OUT"),
])
def test_block_verified_bounce_or_optout_even_with_consent(changes, expected):
    result = review_channel_evidence(row(), channel="email", evidence=proof(**changes), now=NOW)
    assert result["review_status"] == "BLOCKED_BY_EVIDENCE"
    assert expected in result["blockers"]
    assert_no_action(result)


def test_customer_level_suppressed_status_blocks_missing_contact_data():
    result = review_channel_evidence(
        row(prospect_status="suppressed"), channel="sms", evidence=None, now=NOW
    )
    assert result["review_status"] == "BLOCKED_BY_EVIDENCE"
    assert "CRM_CONTACT_HOLD" in result["blockers"]
    assert_no_action(result)


def test_all_preconditions_proven_is_still_only_operator_review():
    result = review_channel_evidence(row(), channel="email", evidence=proof(), now=NOW)
    assert result["review_status"] == "REVIEW_ONLY_EVIDENCE_PRESENT"
    assert result["consent_suppression_review_preconditions_met"] is True
    assert result["canonical_suppression_state"] == "not_found"
    assert_no_action(result)


@pytest.mark.parametrize("changes,missing", [
    ({"identity_bound": False}, "CHANNEL_CONTACT_BINDING_UNVERIFIED"),
    ({"consent_state": "unknown"}, "EXPLICIT_CHANNEL_CONSENT_UNVERIFIED"),
    ({"suppression_state": "unknown"}, "CANONICAL_SUPPRESSION_UNKNOWN"),
    ({"consent_evidence_ref": None}, "NO_CANONICAL_CONSENT_RECEIPT"),
    ({"suppression_evidence_ref": None}, "NO_CANONICAL_SUPPRESSION_CHECK_RECEIPT"),
    ({"observed_at": NOW - timedelta(hours=25)}, "CHANNEL_EVIDENCE_MISSING_OR_STALE"),
    ({"observed_at": NOW + timedelta(seconds=1)}, "CHANNEL_EVIDENCE_MISSING_OR_STALE"),
])
def test_partial_or_stale_proof_fails_closed(changes, missing):
    result = review_channel_evidence(row(), channel="email", evidence=proof(**changes), now=NOW)
    assert result["review_status"] == "HOLD_MISSING_EVIDENCE"
    assert missing in result["blockers"]
    assert_no_action(result)


@pytest.mark.parametrize("changes", [
    {"tenant_id": OTHER}, {"prospect_id": "00000000-0000-0000-0000-000000000299"},
    {"channel": "sms"}, {"source": "client_supplied"},
    {"consent_state": "yes"}, {"suppression_state": "clear"},
    {"observed_at": NOW.replace(tzinfo=None)},
    {"consent_evidence_ref": "x@example.com"},
])
def test_mismatched_or_forged_evidence_rejected(changes):
    with pytest.raises(ChannelEvidenceError):
        review_channel_evidence(row(), channel="email", evidence=proof(**changes), now=NOW)


def test_invalid_prospect_or_time_rejected():
    with pytest.raises(ChannelEvidenceError):
        review_channel_evidence(row(tenant_id=OTHER, prospect_id="not-uuid"),
                                channel="email", evidence=None, now=NOW)
    with pytest.raises(ChannelEvidenceError):
        review_channel_evidence(row(), channel="fax", evidence=None, now=NOW)
    with pytest.raises(ChannelEvidenceError):
        review_channel_evidence(row(), channel="email", evidence=None,
                                now=NOW.replace(tzinfo=None))


class FakeRepository:
    tenant_id = TENANT
    def __init__(self, source): self.source = source
    def prospect(self, prospect_id):
        return self.source if prospect_id == PROSPECT else None
    def prospects(self, *, limit): return [self.source][:limit]
    def buyers(self, *, limit): return []


def client(source=None):
    app = FastAPI()
    app.include_router(create_revenue_crm_router(
        FakeRepository(source if source is not None else row())
    ))
    return TestClient(app)


def test_crm_route_reuses_authenticated_scope_never_uses_spoofed_client_consent():
    c = client()
    response = c.get(
        f"/v1/revenue-crm/prospects/{PROSPECT}/channel-evidence-preview",
        headers={"X-Consent":"true", "X-Suppression-Cleared":"true",
                 "X-Tenant-ID": OTHER, "X-Send-Authorized": "true"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == TENANT
    assert body["send_authorized"] is False
    for channel in ("email", "sms", "web_push"):
        assert_no_action(body["channels"][channel])
        assert body["channels"][channel]["review_status"] == "HOLD_MISSING_EVIDENCE"
    assert c.get("/v1/revenue-crm/prospects/missing/channel-evidence-preview").status_code == 404


def test_crm_route_blocks_cross_tenant_record_and_unavailable_pilot():
    c = client(row(tenant_id=OTHER))
    response = c.get(f"/v1/revenue-crm/prospects/{PROSPECT}/channel-evidence-preview")
    assert response.status_code == 503
    disabled = FastAPI()
    disabled.include_router(create_revenue_crm_router())
    assert TestClient(disabled).get(
        f"/v1/revenue-crm/prospects/{PROSPECT}/channel-evidence-preview"
    ).status_code == 503


def test_untrusted_channel_resolver_cannot_be_registered_without_tenant_auth():
    with pytest.raises(ValueError, match="authenticated CRM tenant resolver"):
        create_revenue_crm_router(
            resolve_authenticated_channel_evidence=lambda *_: proof()
        )

def test_separately_authenticated_reader_proofs_are_status_only_without_contacts():
    from empire_os.revenue_crm_api import (
        AuthenticatedRevenueCrmRead, create_revenue_crm_router,
    )
    from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository
    repo = PostgresRevenueCrmRepository(
        "TEST_DSN_NO_CONNECTION", tenant_id=TENANT,
        connect_factory=lambda *_: None
    )
    repo.prospect = lambda target: row() if target == PROSPECT else None
    access = AuthenticatedRevenueCrmRead(tenant_id=TENANT, repository=repo)
    app = FastAPI()
    calls = []
    def channel_reader(request, target, channel):
        calls.append((target, channel))
        if channel == "email":
            return proof(suppression_state="suppressed")
        if channel == "sms":
            return proof(channel="sms", consent_state="unknown",
                         suppression_state="unknown")
        return None
    app.include_router(create_revenue_crm_router(
        resolve_authenticated_read=lambda _: access,
        resolve_authenticated_channel_evidence=channel_reader,
    ))
    response = TestClient(app).get(
        f"/v1/revenue-crm/prospects/{PROSPECT}/channel-evidence-preview",
        headers={"X-Suppression-Cleared": "true", "X-Consent": "true"}
    )
    assert response.status_code == 200, response.text
    d = response.json()
    assert d["channels"]["email"]["review_status"] == "BLOCKED_BY_EVIDENCE"
    assert "CANONICAL_SUPPRESSION_MATCH" in d["channels"]["email"]["blockers"]
    assert d["channels"]["sms"]["review_status"] == "HOLD_MISSING_EVIDENCE"
    assert d["channels"]["web_push"]["review_status"] == "HOLD_MISSING_EVIDENCE"
    assert len(calls) == 3
    assert "@" not in response.text
    assert d["send_authorized"] is False
    assert d["execution_authority"] == "none"


def test_reader_exception_or_tenant_mismatch_never_yields_channel_clearance():
    from empire_os.revenue_crm_api import AuthenticatedRevenueCrmRead
    from empire_os.revenue_crm_transport import PostgresRevenueCrmRepository
    repo = PostgresRevenueCrmRepository(
        "TEST_DSN_NO_CONNECTION", tenant_id=TENANT,
        connect_factory=lambda *_: None
    )
    repo.prospect = lambda target: row() if target == PROSPECT else None
    scope = AuthenticatedRevenueCrmRead(tenant_id=TENANT, repository=repo)
    for reader in (
        lambda *_: proof(tenant_id=OTHER),
        lambda *_: proof(source="caller-supplied"),
    ):
        app = FastAPI()
        app.include_router(create_revenue_crm_router(
            resolve_authenticated_read=lambda _: scope,
            resolve_authenticated_channel_evidence=reader,
        ))
        response = TestClient(app).get(
            f"/v1/revenue-crm/prospects/{PROSPECT}/channel-evidence-preview"
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "crm_channel_reader_unavailable"
