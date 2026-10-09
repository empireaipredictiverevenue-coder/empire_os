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


def test_official_registry_search_must_match_first_party_company_identity():
    row = candidate(
        business_name="Harvey",
        website="https://harvey.ai/",
        domain="harvey.ai",
        query_evidence=[{
            "query": '"HARVEY HVAC SERVICES LLC" TX',
            "source_refs": ["official:texas_tdlr_ac:118954"],
        }],
        site_evidence={
            "business_name_source": "first_party_site_identity",
            "site_business_names": ["Harvey", "Harvey AI"],
            "site_evidence_score": 0.8,
            "first_party_email_count": 1,
        },
    )
    assert review_readiness(row) == (False, "official_registry_identity_mismatch")


def test_matching_official_registry_first_party_identity_can_progress():
    row = candidate(
        business_name="True North HVAC Services",
        query_evidence=[{
            "query": '"TRUE NORTH HVAC SERVICES LLC" TX',
            "source_refs": ["official:texas_tdlr_ac:12345"],
        }],
        site_evidence={
            "business_name_source": "first_party_site_identity",
            "site_business_names": ["True North HVAC Services"],
            "site_evidence_score": 0.8,
            "first_party_email_count": 1,
        },
    )
    assert review_readiness(row) == (True, "review_ready")


def test_historical_official_mismatch_quarantine_is_idempotent_and_bounded():
    from empire_os.buyer_scout_review_readiness import quarantine_stale_official_readiness

    bad = candidate(
        id="false-ready", review_state="review_ready",
        reconciliation_state="REVIEW_READY",
        canonical_prospect_id=None, canonical_buyer_id=None,
        query_evidence=[{
            "query": '"HARVEY HVAC SERVICES LLC" TX',
            "source_refs": ["official:texas_tdlr_ac:118954"],
        }],
        site_evidence={
            "business_name_source": "first_party_site_identity",
            "site_business_names": ["Harvey AI"],
        },
        business_name="Harvey",
    )
    good = dict(bad, id="matched-ready", business_name="Harvey HVAC Services LLC")
    good["site_evidence"] = dict(bad["site_evidence"], site_business_names=[
        "Harvey HVAC Services LLC"
    ])
    writes = []
    def patch(_method, path, body):
        writes.append((path, body))
        return [{"id": "false-ready"}]

    preview = quarantine_stale_official_readiness([bad, good])
    assert preview["mismatch_ids"] == ["false-ready"]
    assert preview["database_write_performed"] is False
    assert writes == []

    fixed = quarantine_stale_official_readiness([bad, good], patch_call=patch)
    assert fixed["quarantined_count"] == 1
    assert fixed["database_write_performed"] is True
    assert len(writes) == 1
    assert "id=eq.false-ready" in writes[0][0]
    assert "review_state=eq.review_ready" in writes[0][0]
    assert "canonical_prospect_id=is.null" in writes[0][0]
    from empire_os.sb import _table_request_parts, _equality_match
    quarantine_match = _equality_match(
        _table_request_parts(writes[0][0])[2], allow_null=True,
    )
    assert quarantine_match == {
        "id": "false-ready",
        "review_state": "review_ready",
        "reconciliation_state": "REVIEW_READY",
        "canonical_prospect_id": None,
        "canonical_buyer_id": None,
    }
    assert writes[0][1]["review_state"] == "discovered"
    assert writes[0][1]["reconciliation_state"] == "NEW_EXTERNAL_BUYER_CANDIDATE"


def test_existing_readiness_runner_quarantines_only_mismatched_registry_row(monkeypatch):
    from scripts import materialize_buyer_scout_review_readiness as worker

    bad = candidate(
        id="bad-ready", business_name="Harvey",
        review_state="review_ready", reconciliation_state="REVIEW_READY",
        canonical_prospect_id=None, canonical_buyer_id=None,
        query_evidence=[{
            "query": '"HARVEY HVAC SERVICES LLC" TX',
            "source_refs": ["official:texas_tdlr_ac:118954"],
        }],
        site_evidence={
            "business_name_source": "first_party_site_identity",
            "site_business_names": ["Harvey AI"],
        },
    )
    requests = []
    def fake_request(method, path, payload=None, prefer=None):
        requests.append((method, path, payload, prefer))
        if method == "GET":
            return [bad]
        return [{"id": "bad-ready"}]

    monkeypatch.setattr(worker, "request_json", fake_request)
    preview = worker._audit_stale_ready(limit=200, observe_only=True)
    assert preview["mismatch_ids"] == ["bad-ready"]
    assert [r[0] for r in requests] == ["GET"]
    fixed = worker._audit_stale_ready(limit=200, observe_only=False)
    assert fixed["quarantined_count"] == 1
    assert [r[0] for r in requests] == ["GET", "GET", "PATCH"]
    assert requests[-1][3] == "return=representation"


def test_existing_readiness_runner_receipt_accounts_for_quarantine(monkeypatch, tmp_path):
    from scripts import materialize_buyer_scout_review_readiness as worker
    import json
    import sys

    bad = candidate(
        id="false-ready", business_name="Harvey",
        review_state="review_ready", reconciliation_state="REVIEW_READY",
        canonical_prospect_id=None, canonical_buyer_id=None,
        query_evidence=[{
            "query": '"HARVEY HVAC SERVICES LLC" TX',
            "source_refs": ["official:texas_tdlr_ac:118954"],
        }],
        site_evidence={
            "business_name_source": "first_party_site_identity",
            "site_business_names": ["Harvey AI"],
        },
    )
    calls = []
    def fake_request(method, path, payload=None, prefer=None):
        calls.append((method, path, payload))
        if method == "GET":
            return [bad] if "review_state=eq.review_ready" in path else []
        return [{"id": "false-ready"}]

    monkeypatch.setattr(worker, "request_json", fake_request)
    monkeypatch.setattr(
        sys, "argv", ["materialize", "--repo-root", str(tmp_path)]
    )
    assert worker.main() == 0
    receipt = json.loads(
        (tmp_path / "runtime/buyer_acquisition/review_readiness_latest.json").read_text()
    )
    assert receipt["database_write_performed"] is True
    assert receipt["review_ready_count"] == 0
    assert receipt["outbound_sent"] is False
    assert receipt["historical_official_identity_quarantine"]["quarantined_count"] == 1
    assert len([row for row in calls if row[0] == "PATCH"]) == 1


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
        patch_call=lambda method, path, body: (
            calls.append((method, path, body))
            or [{"id": "candidate-1", "review_state": "review_ready"}]
        ),
    )

    assert result["review_ready_count"] == 1
    assert result["canonical_promotion_performed"] is False
    assert result["outbound_sent"] is False
    method, path, body = calls[0]
    assert method == "PATCH"
    assert "buyer_scout_candidates" in path
    assert body["review_state"] == "review_ready"
    assert body["reconciliation_state"] == "REVIEW_READY"


def test_review_materializer_does_not_claim_ready_when_compare_and_swap_fails():
    calls = []
    result = materialize_review_readiness(
        [candidate()],
        patch_call=lambda method, path, body: (
            calls.append((method, path, body)) or []
        ),
    )
    assert result["review_ready_count"] == 0
    assert result["database_write_performed"] is False
    assert result["blocked_reason_counts"]["review_transition_unconfirmed"] == 1
    assert "reconciliation_state=eq.NEW_EXTERNAL_BUYER_CANDIDATE" in calls[0][1]
    assert "review_state=eq.discovered" in calls[0][1]
    assert "canonical_prospect_id=is.null" in calls[0][1]
    from empire_os.sb import _table_request_parts, _equality_match
    parsed = _table_request_parts(calls[0][1])
    match = _equality_match(parsed[2], allow_null=True)
    assert match == {
        "id": "candidate-1",
        "review_state": "discovered",
        "reconciliation_state": "NEW_EXTERNAL_BUYER_CANDIDATE",
        "canonical_prospect_id": None,
        "canonical_buyer_id": None,
    }


def test_generic_about_us_business_name_is_rejected():
    row = candidate(
        business_name="About us",
        site_evidence={
            "business_name_source": "first_party_business_name",
            "site_evidence_score": 0.9,
            "first_party_email_count": 1,
            "first_party_phone_count": 0,
            "people_count": 0,
        },
    )

    assert review_readiness(row) == (
        False,
        "business_name_not_verified",
    )


def test_home_title_fallback_is_rejected():
    row = candidate(
        business_name="Home - Acme Roofing",
        site_evidence={
            "business_name_source": "page_title_fallback",
            "site_evidence_score": 0.9,
            "first_party_email_count": 1,
            "first_party_phone_count": 0,
            "people_count": 0,
        },
    )

    assert review_readiness(row) == (
        False,
        "business_name_not_verified",
    )


def test_permit_buyer_requires_first_party_nyc_territory():
    row = candidate(
        target_product_codes=["permit_intelligence"],
        site_evidence={
            "business_name_source": "first_party_site_identity",
            "permit_territory_state": "NYC_NOT_OBSERVED",
            "site_evidence_score": 0.9,
            "first_party_email_count": 1,
            "first_party_phone_count": 0,
            "people_count": 0,
        },
    )
    assert review_readiness(row) == (
        False,
        "permit_territory_not_verified",
    )


def test_permit_buyer_rejects_unconfirmed_seed_identity():
    row = candidate(
        target_product_codes=["permit_intelligence"],
        site_evidence={
            "business_name_source": "canonical_prospect_seed",
            "canonical_seed_identity_corroborated": False,
            "permit_territory_state": "NYC_FIRST_PARTY_EVIDENCE",
            "site_evidence_score": 0.9,
            "first_party_email_count": 1,
            "first_party_phone_count": 0,
            "people_count": 0,
        },
    )
    assert review_readiness(row) == (
        False,
        "permit_business_identity_unconfirmed",
    )


def test_permit_buyer_can_be_review_ready_with_site_identity_and_nyc():
    row = candidate(
        business_name="VIP Fire Sprinklers Inc",
        target_product_codes=["permit_intelligence"],
        site_evidence={
            "business_name_source": "first_party_site_identity",
            "permit_territory_state": "NYC_FIRST_PARTY_EVIDENCE",
            "site_evidence_score": 0.85,
            "first_party_email_count": 1,
            "first_party_phone_count": 2,
            "people_count": 0,
        },
    )
    assert review_readiness(row) == (True, "review_ready")


def test_observe_preview_uses_same_gate_without_mutation():
    rows = [candidate(), candidate(target_buyer_pools=['direct_demand_buyers'])]
    result = materialize_review_readiness(rows)
    assert result['review_ready_count'] == 1
    assert result['blocked_count'] == 1
    assert result['database_write_performed'] is False
    assert result['canonical_promotion_performed'] is False
    assert rows[0]['review_state'] == 'discovered'
