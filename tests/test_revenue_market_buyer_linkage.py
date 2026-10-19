"""Exact first-party buyer projection linkage: no fuzzy city or fabricated sale."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from empire_os.revenue_market_buyer_linkage import (
    MarketBuyerLinkageHold, review_existing_buyer_market_linkage,
)
from empire_os.revenue_buyer_evidence_handoff import review_one_commercial_evidence_request
from empire_os.revenue_evidence_pathways import SOURCES
from test_revenue_evidence_pathways import payloads

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def sources(tmp_path):
    rows = payloads(n=1)
    rows["radar"]["candidates"][0]["metro"] = "Little Rock, AR"
    for name, (rel, _) in SOURCES.items():
        f = tmp_path/rel
        f.parent.mkdir(parents=True,exist_ok=True)
        f.write_text(json.dumps(rows[name]))
    return review_one_commercial_evidence_request(tmp_path,as_of=NOW)


def buyer(**updates):
    row = {
        "id": "local-buyer-42",
        "buyer_name": "Acme Clean Solar",
        "niche": "Solar",
        "metro": "Little Rock, AR",
        "status": "active",
        "is_active": True,
        "daily_cap": 25,
        "reviewed_at": NOW.isoformat(),
        "destination_phone": "confidential contact 555",
        "webhook_url": "",
        "commercial_activation_state": "discovered",
        "commercial_terms_source": None,
        "commercial_terms_reference": None,
        "commercial_terms_verified_at": None,
        "capacity_verified_at": None,
        "delivery_verified_at": None,
    }
    row.update(updates)
    return row


def test_exact_niche_and_metro_uses_existing_same_record_buybox_review(tmp_path):
    prepared = sources(tmp_path)
    data = review_existing_buyer_market_linkage(
        tmp_path,prepared=prepared,as_of=NOW,
        buyer_rows=[
            buyer(),
            buyer(id="same-niche-other-market", metro="Bolton"),
            buyer(id="different-niche",niche="roofing"),
        ],
    )
    assert data["status"] == "EXACT_MARKET_BUYER_RECORDS_NEED_VERIFICATION"
    assert data["same_niche_record_count"] == 2
    assert data["same_niche_and_exact_metro_record_count"] == 1
    assert data["candidate_count"] == 1
    assert data["market_niche"] == "solar"
    assert data["market_metro"] == "little rock, ar"
    assert data["original_buyer_reply_or_authorisation_verified"] is False
    assert data["confirmed_buybox_specific_price_postcode_and_capacity"] is False
    assert data["market_match_is_buyer_intent"] is False
    assert data["quant_inputs_created"] is False
    assert data["database_writes"] is False
    detail = data["candidates"][0]
    assert detail["configured_activation_gate_passed"] is False
    assert detail["next_source_review"] in (
        "VERIFY_BUYER_CAPACITY_AGREEMENT", "VERIFY_BUYER_PRICING_AND_TERMS",
    )
    serialized = json.dumps(data)
    for private in (
        "Acme Clean Solar", "local-buyer-42", "confidential contact 555",
        "same-niche-other-market",
    ):
        assert private not in serialized


@pytest.mark.parametrize("place",["Bolton","London","Little Rock, UK","Little Rock Arkansas", "NYC"])
def test_same_niche_different_location_is_not_buyer_link(tmp_path,place):
    prepared = sources(tmp_path)
    outcome = review_existing_buyer_market_linkage(
        tmp_path,prepared=prepared,as_of=NOW,
        buyer_rows=[buyer(metro=place)],
    )
    assert outcome["same_niche_record_count"] == 1
    assert outcome["same_niche_and_exact_metro_record_count"] == 0
    assert outcome["candidate_count"] == 0
    assert outcome["status"] == "NO_EXACT_MARKET_BUYER_RECORDS_IN_PROJECTION"


def test_tenant_scoped_record_never_exposed_by_global_lookup(tmp_path):
    prepared = sources(tmp_path)
    result = review_existing_buyer_market_linkage(
        tmp_path,prepared=prepared,as_of=NOW,
        buyer_rows=[buyer(tenant_id="tenant-secret")],
    )
    assert result["tenant_scoped_records_held"] == 1
    assert result["same_niche_and_exact_metro_record_count"] == 0
    assert "tenant-secret" not in json.dumps(result)


def test_repeated_opportunity_source_cannot_be_moved_to_different_market(tmp_path):
    prepared = sources(tmp_path)
    radar = tmp_path/SOURCES["radar"][0]
    document = json.loads(radar.read_text())
    document["candidates"][0]["niche"] = "roofing"
    radar.write_text(json.dumps(document))
    with pytest.raises(MarketBuyerLinkageHold,match="drift_or_hold|exact_niche"):
        review_existing_buyer_market_linkage(
            tmp_path,prepared=prepared,as_of=NOW,
            buyer_rows=[buyer()],
        )


def test_tampered_prepared_review_rejected_without_reading_private_buyer(tmp_path):
    prepared = sources(tmp_path)
    forged = deepcopy(prepared)
    forged["buyer_contacted"] = True
    with pytest.raises(MarketBuyerLinkageHold,match="drift_or_hold"):
        review_existing_buyer_market_linkage(
            tmp_path,prepared=forged,as_of=NOW,
            buyer_rows=[buyer()],
        )


def test_duplicate_same_market_buyer_fails_closed(tmp_path):
    prepared = sources(tmp_path)
    with pytest.raises(ValueError,match="duplicate buyer identity"):
        review_existing_buyer_market_linkage(
            tmp_path,prepared=prepared,as_of=NOW,
            buyer_rows=[buyer(),buyer()],
        )


def test_unbounded_or_bad_projection_rejected(tmp_path):
    prepared = sources(tmp_path)
    with pytest.raises(MarketBuyerLinkageHold,match="untrusted_or_unbounded"):
        review_existing_buyer_market_linkage(
            tmp_path,prepared=prepared,as_of=NOW,
            buyer_rows=[buyer()]*10001,
        )
    with pytest.raises(MarketBuyerLinkageHold,match="untrusted_or_unbounded"):
        review_existing_buyer_market_linkage(
            tmp_path,prepared=prepared,as_of=NOW,
            buyer_rows=[{"id":"maybe"},None],
        )


def test_clashing_source_and_private_payload_not_leaked(tmp_path):
    prepared = sources(tmp_path)
    radar = tmp_path/SOURCES["radar"][0]
    document = json.loads(radar.read_text())
    document["candidates"][0]["metro"] = "jane@example.com / PRIVATE"
    radar.write_text(json.dumps(document))
    with pytest.raises(MarketBuyerLinkageHold,match="first_party_evidence_request_drift_or_hold"):
        review_existing_buyer_market_linkage(
            tmp_path,prepared=prepared,as_of=NOW,
            buyer_rows=[buyer()],
        )


def test_canonical_reader_unavailable_is_unknown_not_zero(tmp_path):
    from empire_os.revenue_market_buyer_linkage import inspect_existing_buyer_projection_readonly
    prepared = sources(tmp_path)
    invoked = []
    def unavailable():
        invoked.append(True)
        raise RuntimeError("DSN secret=PRIVATE_PASSWORD")
    report = inspect_existing_buyer_projection_readonly(
        tmp_path,prepared=prepared,as_of=NOW,buyer_reader=unavailable
    )
    assert invoked == [True]
    assert report["status"] == "CANONICAL_BUYER_GATEWAY_UNAVAILABLE"
    assert report["same_niche_and_exact_metro_record_count"] is None
    assert report["candidate_count"] is None
    assert "PRIVATE_PASSWORD" not in json.dumps(report)
    assert report["database_writes"] is False


def test_successful_empty_reader_means_zero_only_after_actual_query(tmp_path):
    from empire_os.revenue_market_buyer_linkage import inspect_existing_buyer_projection_readonly
    prepared = sources(tmp_path)
    report = inspect_existing_buyer_projection_readonly(
        tmp_path,prepared=prepared,as_of=NOW,buyer_reader=lambda: []
    )
    assert report["status"] == "NO_EXACT_MARKET_BUYER_RECORDS_IN_PROJECTION"
    assert report["source_buyer_record_count"] == 0
    assert report["same_niche_and_exact_metro_record_count"] == 0


def test_invalid_canonical_projection_is_held_not_zero(tmp_path):
    from empire_os.revenue_market_buyer_linkage import inspect_existing_buyer_projection_readonly
    prepared = sources(tmp_path)
    report = inspect_existing_buyer_projection_readonly(
        tmp_path,prepared=prepared,as_of=NOW,buyer_reader=lambda: [None]
    )
    assert report["status"] == "BUYER_MARKET_LINKAGE_EVIDENCE_HELD"
    assert report["candidate_count"] is None
    assert report["same_niche_and_exact_metro_record_count"] is None


def test_injected_reader_only_invoked_once_on_complete_source(tmp_path):
    from empire_os.revenue_market_buyer_linkage import inspect_existing_buyer_projection_readonly
    prepared = sources(tmp_path)
    called = []
    def reader():
        called.append(1)
        return [buyer()]
    report = inspect_existing_buyer_projection_readonly(
        tmp_path,prepared=prepared,as_of=NOW,buyer_reader=reader
    )
    assert called == [1]
    assert report["candidate_count"] == 1
    assert report["original_buyer_reply_or_authorisation_verified"] is False
