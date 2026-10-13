from empire_os.aceleads_preflight import preflight

BASE = {
    "vertical": "commercial_roofing",
    "property_type": "warehouse",
    "postcode": "BL1 3PW",
    "work_required": "roof replacement",
    "decision_maker_role": "facilities manager",
    "source_url": "https://example.invalid/roofing",
    "source_type": "first_party_organic",
    "consent_text_version": "draft-v1",
    "privacy_notice_version": "draft-v1",
    "consent_timestamp": "2026-10-13T10:00:00Z",
    "consent_source_url": "https://example.invalid/roofing",
    "buyer_brief_id": "synthetic-draft",
    "synthetic": True,
    "mode": "OBSERVE",
    "execution_authority": "NONE",
    "buyer_terms_approved": False,
    "buyer_approved": False,
    "consent_verified": False,
    "suppression_verified": False,
    "lead_delivery_authorized": False,
}


def test_pending_buyer_and_consent_fail_closed():
    result = preflight(BASE)
    assert not result["review_ready"]
    assert not result["delivery_authorized"]
    assert "buyer_not_approved" in result["blockers"]
    assert "consent_not_verified" in result["blockers"]


def test_complete_synthetic_review_never_authorizes_delivery():
    p = {**BASE, "buyer_terms_approved": True, "buyer_approved": True,
         "consent_verified": True, "suppression_verified": True}
    result = preflight(p)
    assert result["review_ready"]
    assert result["delivery_authorized"] is False


def test_rejects_non_synthetic_and_live_delivery():
    p = {**BASE, "synthetic": False, "lead_delivery_authorized": True}
    result = preflight(p)
    assert "synthetic_only" in result["blockers"]
    assert "delivery_must_remain_disabled" in result["blockers"]


def test_rejects_missing_evidence_and_invalid_postcode():
    p = {**BASE, "postcode": "12345", "consent_source_url": ""}
    result = preflight(p)
    assert "invalid_uk_postcode" in result["blockers"]
    assert "missing_consent_source_url" in result["blockers"]
