from datetime import datetime, timezone

from empire_os.gtm_standing_bridge import run_standing_bridge


REVIEW_ID = "00000000-0000-0000-0000-000000000701"


class FakeRequest:
    def __init__(self, *, invalid_person=False):
        self.invalid_person = invalid_person
        self.calls = []

    def __call__(self, method, path, payload=None, **_kwargs):
        self.calls.append((method, path, payload))

        if method == "GET" and path.startswith(
            "/rest/v1/buyer_candidate_reviews?"
        ):
            return [{
                "id": REVIEW_ID,
                "status": "pending",
                "offer_key": "managed_service",
            }]

        if path.endswith("/auto_review_buyer_candidate"):
            return {
                "decision": "approved",
                "review_id": REVIEW_ID,
                "status": "approved",
            }

        if path.endswith("/list_buyer_reviews_for_outbound"):
            return [{
                "id": REVIEW_ID,
                "contact_name": (
                    "Your Referral Program"
                    if self.invalid_person
                    else "Jane Smith"
                ),
                "contact_title": "Owner",
                "contact_email": "jane@example.com",
                "evidence": {
                    "business_name": "Acme Roofing",
                    "metro": "Austin, TX",
                },
            }]

        if path.endswith("/propose_reviewed_outbound_intent"):
            return {
                "decision": "proposed",
                "intent_id": "00000000-0000-0000-0000-000000000801",
            }

        raise AssertionError((method, path, payload))


def test_bridge_reviews_then_proposes_governed_outbound():
    request = FakeRequest()
    result = run_standing_bridge(
        request,
        review_limit=20,
        outbound_limit=20,
        daily_cap=10,
        now=datetime(
            2026, 9, 22, 15, 0, tzinfo=timezone.utc
        ),
    )

    assert result.pending_seen == 1
    assert result.auto_reviewed == 1
    assert result.approved_ready == 1
    assert result.outbound_proposed == 1
    assert result.skipped_invalid_person == 0
    assert result.review_errors == ()
    assert result.outbound_errors == ()

    proposal = next(
        payload
        for method, path, payload in request.calls
        if path.endswith("/propose_reviewed_outbound_intent")
    )
    assert proposal["p_review_id"] == REVIEW_ID
    assert proposal["p_subject"] == "Jane — quick idea for Acme Roofing"
    assert "Worth sending over?" in proposal["p_body_text"]
    assert "31 St Thomas St, Bolton, BL1 2QR, UK" in (
        proposal["p_body_text"]
    )
    assert "opt out" in proposal["p_body_text"].lower()
    assert proposal["p_metadata"]["automatic_send"] is False


def test_bridge_does_not_propose_for_pseudo_person():
    request = FakeRequest(invalid_person=True)
    result = run_standing_bridge(request)

    assert result.auto_reviewed == 1
    assert result.approved_ready == 1
    assert result.outbound_proposed == 0
    assert result.skipped_invalid_person == 1
    assert not any(
        path.endswith("/propose_reviewed_outbound_intent")
        for _method, path, _payload in request.calls
    )


def test_bridge_uses_bounded_standing_authority_cap():
    request = FakeRequest()
    run_standing_bridge(
        request,
        daily_cap=500,
    )

    approval = next(
        payload
        for method, path, payload in request.calls
        if path.endswith("/auto_review_buyer_candidate")
    )
    assert approval["p_daily_cap"] == 50
