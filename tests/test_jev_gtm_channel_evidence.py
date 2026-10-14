"""Canonical CRM evidence bridge must never invent email send clearance."""
from datetime import datetime, timezone, timedelta
import pytest

from empire_os.jev_gtm_channel_evidence import outreach_from_canonical_channel_evidence
from empire_os.revenue_crm_channel_evidence import TrustedChannelEvidence, ChannelEvidenceError

NOW = datetime(2026, 10, 14, 9, tzinfo=timezone.utc)
TENANT = "00000000-0000-4000-8000-000000000001"
PROSPECT = "00000000-0000-4000-8000-000000000002"


def prospect():
    return {"tenant_id": TENANT, "prospect_id": PROSPECT, "prospect_status": "new"}


def evidence(**changes):
    row = {
        "tenant_id": TENANT, "prospect_id": PROSPECT, "channel": "email",
        "identity_bound": True, "consent_state": "verified_opt_in",
        "suppression_state": "not_found",
        "consent_evidence_ref": "consent:proof:1",
        "suppression_evidence_ref": "suppress:proof:1",
        "observed_at": NOW,
    }
    row.update(changes)
    return TrustedChannelEvidence(**row)


def review(item):
    return outreach_from_canonical_channel_evidence(prospect(), evidence=item, as_of=NOW)


def test_full_canonical_preconditions_still_never_authorize_send():
    row = review(evidence())
    assert row["suppression_checked"] is True
    assert row["suppression_state"] == "CLEAR"
    assert row["send_authorized"] is False
    assert row["execution_authority"] == "none"


def test_existing_hit_only_unknown_is_not_clear():
    row = review(evidence(
        consent_state="unknown", suppression_state="unknown",
        identity_bound=False, consent_evidence_ref=None, suppression_evidence_ref=None,
    ))
    assert row["suppression_checked"] is False
    assert row["suppression_state"] == "UNKNOWN"
    assert row["send_authorized"] is False


def test_suppression_hit_is_blocked():
    row = review(evidence(suppression_state="suppressed"))
    assert row["suppressed"] is True
    assert row["do_not_contact"] is True
    assert row["send_authorized"] is False


def test_opt_out_is_blocked():
    row = review(evidence(consent_state="opted_out"))
    assert row["do_not_contact"] is True


def test_stale_channel_evidence_is_not_clear():
    row = review(evidence(observed_at=NOW - timedelta(days=3)))
    assert row["suppression_checked"] is False


def test_cross_tenant_proof_rejected():
    with pytest.raises(ChannelEvidenceError, match="cross-tenant"):
        review(evidence(tenant_id="00000000-0000-4000-8000-000000000099"))


def test_no_evidence_returns_unknown():
    row = review(None)
    assert row["suppression_state"] == "UNKNOWN"
    assert row["canonical_readback_verified"] is False
