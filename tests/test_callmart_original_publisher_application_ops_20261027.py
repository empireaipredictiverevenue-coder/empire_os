"""Callmart receipt is submission proof, never buyer acceptance or revenue."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import copy
import json
import os

import pytest

from empire_os.commercial_buyer_source_health import inspect_original_callmart_publisher_receipt

NOW = datetime(2026, 10, 27, 14, 5, tzinfo=timezone.utc)


def source():
    return {
        "schema_version": "empire.callmart.publisher_application_external_receipt.v1",
        "observed_at_utc": "2026-10-27T14:03:32.162527+00:00",
        "status": "EXTERNAL_APPLICATION_HTTP_SUCCESS_REVIEW_PENDING",
        "http_status": 200,
        "company": "Empire AI",
        "form_url": "https://app.callmart.io/apply/publisher",
        "provider_acknowledgement": "Application received. Our team will review it and follow up if it is a fit.",
        "daily_live_insurance_call_volume": 0,
        "corporate_website_only_not_live_insurance_landing": True,
        "original_application_fields_sha256": "a" * 64,
        "applicant_approved": False, "traffic_enabled": False,
        "buyer_terms_verified": False, "outbound_sent": False,
        "execution_authority": "none",
        "applicant_personal_email": "PRIVATE_DO_NOT_EXPOSE@example.invalid",
    }


def place(tmp_path, data=None):
    p = tmp_path / "runtime/buyer_network_intelligence/callmart_publisher_application_20261027.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data if data is not None else source()))
    os.chmod(p, 0o600)
    return p


def test_submitted_receipt_does_not_promote_to_accepted_buyer_or_paid_call(tmp_path):
    p = place(tmp_path)
    before = p.read_bytes()
    r = inspect_original_callmart_publisher_receipt(tmp_path, now=NOW)
    assert p.read_bytes() == before
    assert r["status"] == "APPLICATION_SUBMITTED_AWAITING_CALLMART_REVIEW"
    assert r["application_submitted"] is True
    assert r["review_pending"] is True
    assert r["verified_insurance_call_volume"] == 0
    assert r["buyer_acceptance_verified"] is False
    assert r["buyer_terms_verified"] is False
    assert r["verified_revenue_cents"] is None
    assert r["outbound_authorized"] is False
    assert "PRIVATE_DO_NOT_EXPOSE" not in str(r)


@pytest.mark.parametrize("field, value", [
    ("status", "APPLICATION_APPROVED"),
    ("http_status", 409),
    ("applicant_approved", True),
    ("traffic_enabled", True),
    ("buyer_terms_verified", True),
    ("daily_live_insurance_call_volume", 100),
    ("corporate_website_only_not_live_insurance_landing", False),
    ("outbound_sent", True),
])
def test_untrusted_receipt_fails_closed(tmp_path, field, value):
    d = source()
    d[field] = value
    place(tmp_path, d)
    result = inspect_original_callmart_publisher_receipt(tmp_path, now=NOW)
    assert result["status"] == "APPLICATION_RECEIPT_REQUIRES_OWNER_REVIEW"
    assert result["application_submitted"] is None
    assert result["verified_revenue_cents"] is None


def test_missing_and_unprotected_receipts_are_not_confirmations(tmp_path):
    assert inspect_original_callmart_publisher_receipt(tmp_path, now=NOW)["application_submitted"] is None
    p = place(tmp_path)
    os.chmod(p, 0o644)
    assert inspect_original_callmart_publisher_receipt(tmp_path, now=NOW)["application_submitted"] is None


def test_old_receipt_requires_original_owner_review(tmp_path):
    place(tmp_path)
    report = inspect_original_callmart_publisher_receipt(tmp_path, now=NOW + timedelta(days=32))
    assert report["status"] == "APPLICATION_RECEIPT_REQUIRES_OWNER_REVIEW"
    assert report["application_submitted"] is None
