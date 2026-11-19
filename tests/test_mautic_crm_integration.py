"""End-to-end synthetic Mautic webhook -> existing Smart CRM journey projection.

In-process HTTP, authenticated with real HMAC over Mautic-shaped payloads.
The journal uses an isolated private temp folder and is reopened to test
durability. No external Mautic, customer, production, DB, mail or payment IO.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.mautic_crm_integration import (
    MauticSource, MauticIntegrationError, SqliteMauticReceiptJournal,
    create_mautic_crm_preview_router,
)
from empire_os.revenue_crm_api import create_revenue_crm_router

TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"
PROSPECT = "00000000-0000-0000-0000-000000000201"
NOW = datetime(2026, 11, 19, 11, tzinfo=timezone.utc)
SECRET = b"correct-signature-in-isolated-test-only"
ENDPOINT = "/v1/revenue-crm/integrations/mautic/mautic-test/events/preview"


class SyntheticCRM:
    tenant_id = TENANT
    rows = {
        PROSPECT: {
            "tenant_id": TENANT, "prospect_id": PROSPECT, "niche": "solar",
            "prospect_status": "suppressed",
            "conversation_id": "00000000-0000-0000-0000-000000000301",
            "conversation_state": "engaged",
            "conversation_updated_at": NOW - timedelta(days=3),
        }
    }

    def prospect(self, prospect_id):
        return self.rows.get(prospect_id)

    def prospects(self, *, limit):
        return list(self.rows.values())[:limit]

    def buyers(self, *, limit):
        return []


def signed(payload, secret=SECRET):
    data = json.dumps(payload, separators=(",", ":")).encode()
    signature = base64.b64encode(hmac.new(secret, data, hashlib.sha256).digest()).decode()
    return data, {"Content-Type": "application/json", "Webhook-Signature": signature}


def event(status="unsubscribed", contact_id=42):
    return {"contact": {"id": contact_id, "email": "private@example.test"},
            "channel": "email", "new_status": status, "old_status": "contactable",
            "timestamp": NOW.isoformat()}


def source():
    return MauticSource(
        source_id="mautic-test", tenant_id=TENANT,
        webhook_secret=SECRET,
        contact_bindings={42: {"tenant_id": TENANT, "prospect_id": PROSPECT}},
    )


def make_app(journal, *, source_resolver=None, repo_resolver=None, allow_test=True):
    app = FastAPI()
    crm = SyntheticCRM()
    app.include_router(create_revenue_crm_router(repository=crm))
    app.include_router(create_mautic_crm_preview_router(
        resolve_source=source_resolver or (lambda name: source() if name == "mautic-test" else None),
        resolve_tenant_reader=repo_resolver or (lambda tenant: crm if tenant == TENANT else None),
        receipt_journal=journal,
        allow_synthetic_test_reader=allow_test,
        now_provider=lambda: NOW,
    ))
    return TestClient(app)


@pytest.fixture
def journal(tmp_path):
    # Ownership is private by default in pytest, explicitly tighten anyway.
    os.chmod(tmp_path, 0o700)
    return SqliteMauticReceiptJournal(tmp_path / "receipts.sqlite3")


def test_authenticated_unsubscribe_routes_to_existing_crm_hold_not_send(journal):
    client = make_app(journal)
    body, headers = signed({"mautic.lead_channel_subscription_changed": [event()]})
    response = client.post(ENDPOINT, data=body, headers=headers)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["new_events"] == 1
    assert result["received_events"] == 1
    assert result["duplicate_events"] == 0
    assert result["canonical_crm_written"] is False
    assert result["workflow_server_execution"] is False
    assert result["execution_authority"] == "none"
    review = result["journey_reviews"][0]
    assert review["canonical_journey_segment"] == "contact_hold"
    assert "OBSERVED_CONTACT_HOLD" in review["canonical_journey_blockers"]
    assert review["signal"] == "SUPPRESSION_REVIEW_REQUIRED"
    assert review["channel_actions"]["email"] == "BLOCKED_NO_SEND"
    assert "private@example.test" not in response.text
    existing = client.get(f"/v1/revenue-crm/prospects/{PROSPECT}/journey-preview")
    assert existing.status_code == 200
    assert existing.json()["segment"] == "contact_hold"


def test_replay_rejected_after_reopening_durable_journal(journal, tmp_path):
    body, headers = signed({"mautic.lead_channel_subscription_changed": [event()]})
    assert make_app(journal).post(ENDPOINT, data=body, headers=headers).json()["new_events"] == 1
    reopened = SqliteMauticReceiptJournal(tmp_path / "receipts.sqlite3")
    replay = make_app(reopened).post(ENDPOINT, data=body, headers=headers)
    assert replay.status_code == 200
    assert replay.json()["new_events"] == 0
    assert replay.json()["duplicate_events"] == 1
    assert replay.json()["journey_reviews"] == []


def test_unbound_contact_does_not_create_crm_or_receipt(journal):
    body, headers = signed({"mautic.lead_channel_subscription_changed": [event(contact_id=99)]})
    result = make_app(journal).post(ENDPOINT, data=body, headers=headers)
    assert result.status_code == 200
    assert result.json()["unbound_events"] == 1
    assert result.json()["new_events"] == 0
    assert result.json()["canonical_crm_written"] is False


def test_spoofed_tenant_header_never_changes_authenticated_scope(journal):
    body, headers = signed({"mautic.lead_channel_subscription_changed": [event()]})
    headers["X-Tenant-ID"] = OTHER
    result = make_app(journal).post(ENDPOINT, data=body, headers=headers)
    assert result.status_code == 200
    assert result.json()["tenant_id"] == TENANT


def test_cross_tenant_source_binding_rejected(journal):
    bad = MauticSource(
        source_id="mautic-test", tenant_id=TENANT, webhook_secret=SECRET,
        contact_bindings={42: {"tenant_id": OTHER, "prospect_id": PROSPECT}},
    )
    body, headers = signed({"mautic.lead_channel_subscription_changed": [event()]})
    result = make_app(journal, source_resolver=lambda _name: bad).post(
        ENDPOINT, data=body, headers=headers,
    )
    assert result.status_code == 401
    assert result.json()["detail"] == "mautic_webhook_invalid"


def test_signed_source_requires_canonical_tenant_reader(journal):
    body, headers = signed({"mautic.lead_channel_subscription_changed": [event()]})
    resp = make_app(journal, repo_resolver=lambda _id: None).post(
        ENDPOINT, data=body, headers=headers,
    )
    assert resp.status_code == 503


def test_synthetic_repo_refused_by_default_for_real_deployment(journal):
    body, headers = signed({"mautic.lead_channel_subscription_changed": [event()]})
    resp = make_app(journal, allow_test=False).post(
        ENDPOINT, data=body, headers=headers,
    )
    assert resp.status_code == 503


def test_signature_missing_modified_or_wrong_secret_rejected(journal):
    body, headers = signed({"mautic.lead_channel_subscription_changed": [event()]})
    client = make_app(journal)
    assert client.post(ENDPOINT, data=body, headers={"content-type": "application/json"}).status_code == 401
    assert client.post(ENDPOINT, data=body+b" ", headers=headers).status_code == 401
    body2, headers2 = signed({"mautic.lead_channel_subscription_changed": [event()]}, b"wrong-test-secret")
    assert client.post(ENDPOINT, data=body2, headers=headers2).status_code == 401


def test_unsupported_source_type_and_large_payload(journal):
    client = make_app(journal)
    body, headers = signed({"mautic.lead_channel_subscription_changed": [event()]})
    assert client.post(ENDPOINT.replace("mautic-test", "unconfigured"), data=body, headers=headers).status_code == 404
    wrong_ct = dict(headers)
    wrong_ct["Content-Type"] = "text/plain"
    assert client.post(ENDPOINT, data=body, headers=wrong_ct).status_code == 415
    oversized = b"x" * 131073
    assert client.post(ENDPOINT, data=oversized, headers=headers).status_code == 413


def test_batch_signals_and_isolated_event_dedup(journal):
    payload = {
        "mautic.lead_channel_subscription_changed": [event()],
        "mautic.form_on_submit": [{
            "submission": {"id": 55, "lead": {"id": 42},
                           "results": {"private": "do not disclose"}},
            "timestamp": NOW.isoformat(),
        }],
        "mautic.email_on_open": [{"contact": {"id": 42}, "timestamp": NOW.isoformat()}],
    }
    body, headers = signed(payload)
    result = make_app(journal).post(ENDPOINT, data=body, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["new_events"] == 3
    assert "do not disclose" not in result.text
    assert {item["signal"] for item in result.json()["journey_reviews"]} == {
        "SUPPRESSION_REVIEW_REQUIRED", "FORM_SUBMISSION_REVIEW_NOT_CONSENT",
        "LOW_CONFIDENCE_EMAIL_OPEN_REVIEW",
    }


def test_in_batch_duplicate_is_not_reported_twice(journal):
    payload = {"mautic.lead_channel_subscription_changed": [event(), event()]}
    body, headers = signed(payload)
    result = make_app(journal).post(ENDPOINT, data=body, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["new_events"] == 1
    assert result.json()["duplicate_events"] == 1


def test_replay_journal_rejects_non_private_directory(tmp_path):
    os.chmod(tmp_path, 0o755)
    with pytest.raises(MauticIntegrationError, match="private"):
        SqliteMauticReceiptJournal(tmp_path / "unsafe.sqlite3")


def test_receipt_journal_is_owner_private_and_atomic_across_threads(journal):
    import stat
    from concurrent.futures import ThreadPoolExecutor
    assert stat.S_IMODE(journal._path.stat().st_mode) == 0o600

    def insert_once(_index):
        return journal.reserve_new(
            tenant_id=TENANT, source_id="mautic-test",
            evidence_hmacs=["a" * 64], now=NOW,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(insert_once, range(8)))
    assert sum(len(result) for result in responses) == 1


def test_private_receipt_journal_refuses_insecure_existing_file(tmp_path):
    os.chmod(tmp_path, 0o700)
    insecure = tmp_path / "public.sqlite3"
    insecure.write_bytes(b"")
    os.chmod(insecure, 0o644)
    with pytest.raises(MauticIntegrationError, match="private"):
        SqliteMauticReceiptJournal(insecure)


def test_orphan_canonical_prospect_fails_closed_without_acknowledging_event(journal):
    body, headers = signed({"mautic.lead_channel_subscription_changed": [event()]})

    class MissingProspect(SyntheticCRM):
        def prospect(self, prospect_id):
            return None

    client = make_app(journal, repo_resolver=lambda _tenant: MissingProspect())
    assert client.post(ENDPOINT, data=body, headers=headers).status_code == 503
    # With a valid bound CRM reader the event must not be mistaken for a replay.
    assert make_app(journal).post(ENDPOINT, data=body, headers=headers).json()["new_events"] == 1
