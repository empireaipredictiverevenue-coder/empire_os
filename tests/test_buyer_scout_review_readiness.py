from empire_os.buyer_scout_review_readiness import (
    materialize_review_readiness,
    review_readiness,
)


def candidate(**overrides):
    row = {
        "id": "candidate-1",
        "domain": "buyer.example",
        "business_name": "Buyer Co",
        "website": "https://buyer.example",
        "reconciliation_state": "NEW_EXTERNAL_BUYER_CANDIDATE",
        "review_state": "discovered",
        "target_buyer_pools": ["local_and_smb_buyers"],
        "query_evidence": [{"query": "roofing local business"}],
        "site_evidence": {
            "site_evidence_score": 0.8,
            "first_party_email_count": 1,
            "first_party_phone_count": 0,
            "people_count": 0,
        },
        "explicit_direct_buyer_evidence": False,
    }
    row.update(overrides)
    return row


def test_local_smb_candidate_can_be_review_ready_without_direct_buyer_claim():
    assert review_readiness(candidate()) == (True, "review_ready")


def test_direct_demand_candidate_requires_explicit_buying_evidence():
    row = candidate(
        target_buyer_pools=["direct_demand_buyers"],
        explicit_direct_buyer_evidence=False,
    )
    assert review_readiness(row) == (
        False,
        "direct_buyer_evidence_missing",
    )


def test_first_party_contact_path_is_required():
    row = candidate(
        site_evidence={
            "site_evidence_score": 0.9,
            "first_party_email_count": 0,
            "first_party_phone_count": 0,
            "people_count": 0,
        }
    )
    assert review_readiness(row) == (
        False,
        "first_party_contact_path_missing",
    )


def test_materializer_only_updates_holding_review_state():
    calls = []

    result = materialize_review_readiness(
        [candidate()],
        patch_call=lambda method, path, body: calls.append(
            (method, path, body)
        ) or [],
    )

    assert result["review_ready_count"] == 1
    assert result["canonical_promotion_performed"] is False
    assert result["outbound_sent"] is False
    method, path, body = calls[0]
    assert method == "PATCH"
    assert "buyer_scout_candidates" in path
    assert body["review_state"] == "review_ready"
    assert body["reconciliation_state"] == "REVIEW_READY"
