"""V5 audit-only tests for exact-site, window, ID and money reconciliation."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import runpy

import pytest

from empire_os.microsite_verified_outcomes_v5 import (
    OriginalPageReaders, build_approved_microsite_scorecard,
    reconcile_approved_page,
)
from empire_os.predictive_microsite_factory import build_candidate

START, END = "2026-10-16", "2026-10-22"
CAMPAIGN = "campaign_aaaaaaaaaaaaaaaaaaaaaaaa"
CANONICAL_ASSET = CAMPAIGN + ":landing"
URL = "https://empire-ai.co.uk/research/" + CAMPAIGN
ACCEPTED = "crm_accepted_original_event_0001"
SETTLED = "canonical_cash_settlement_0001"


def spec():
    return runpy.run_path(
        str(Path(__file__).with_name("test_predictive_microsite_factory_20261026.py"))
    )["candidate"]()


def fixture_readers(candidate=None):
    item = candidate or spec()
    packet, html = build_candidate(item)
    cid = packet["id"]
    digest = sha256(html.encode()).hexdigest()

    def bound(owner):
        return {
            "source_owner": owner, "candidate_id": cid,
            "asset_sha256": digest, "public_url": URL,
            "source_evidence_ref": "owned_evidence:" + owner,
            "canonical_campaign_id": CAMPAIGN, "canonical_asset_id": CANONICAL_ASSET,
            "window_start": START, "window_end": END,
        }

    site = {
        **bound("original_empire_website_owner"),
        "status": "ORIGINAL_OWNER_DEPLOYMENT_READBACK_VERIFIED",
        "immutable_release_readback": True,
        "source_preview_sha256": digest,
        "deployed_asset_readback_verified": True,
    }
    gsc = {
        **bound("original_seo_first_party_gsc"),
        "dimension": "page", "status": "MEASURED_PAGE_METRICS",
        "impressions": 11, "clicks": 2,
    }
    events = {
        **bound("original_website_consent_and_event_owner"),
        "lawful_website_analytics_consent_verified": True,
        "server_side_event_collection_verified": True,
        "sessions": 8,
    }
    crm = {
        **bound("original_empire_crm_owner"),
        "source_to_enquiry_identity_join_verified": True,
        "consent_and_suppression_verified": True,
        "consented_enquiries": 2, "qualified_enquiries": 1,
        "buyer_accepted_events": 1,
        "canonical_buyer_accepted_event_refs": [ACCEPTED],
    }
    settlement = {
        **bound("original_empire_verified_settlement_owner"),
        "original_accepted_event_to_settlement_join_verified": True,
        "cash_settled_independently_verified": True,
        "settled_revenue_minor": 5000, "currency": "USD",
        "original_settled_event_rows": [{
            "accepted_event_ref": ACCEPTED,
            "settlement_ref": SETTLED, "amount_minor": 5000,
        }],
    }
    data = {"site": site, "gsc": gsc, "events": events,
            "crm": crm, "settlement": settlement}
    return data, OriginalPageReaders(
        site_owner=lambda _: data["site"], gsc=lambda _: data["gsc"],
        first_party_events=lambda _: data["events"], crm=lambda _: data["crm"],
        settlement=lambda _: data["settlement"],
    )


def test_missing_real_owner_returns_unknown_not_zero():
    output = build_approved_microsite_scorecard(
        [spec()], readers=OriginalPageReaders(),
        window_start=START, window_end=END)
    assert output["approved_original_site_pages"] == 0
    assert output["pages_with_original_gsc_metrics"] == 0
    assert output["pages_with_canonical_enquiries"] == 0
    assert output["realised_revenue_by_currency"] == {}
    row = output["pages"][0]
    assert row["status"] == "NO_ORIGINAL_OWNER_PAGE_RELEASE"
    assert row["organic_search_impressions"] is None
    assert row["settled_revenue_minor"] is None
    assert row["attributed_revenue_verified"] is False


def test_full_mock_owner_chain_returns_matching_cash_only():
    data, readers = fixture_readers()
    row, accepted, paid = reconcile_approved_page(
        spec(), readers=readers, window_start=START, window_end=END)
    assert row["status"] == "ATTRIBUTED_SETTLEMENT_VERIFIED"
    assert row["organic_search_ctr"] == pytest.approx(2 / 11, abs=1e-6)
    assert row["enquiry_per_consented_session"] == 0.25
    assert row["buyer_accepted_events"] == 1
    assert row["individually_reconciled_accepted_event_count"] == 1
    assert row["settled_events"] == 1
    assert row["settled_revenue_minor"] == 5000
    assert row["attributed_revenue_verified"]
    assert row["private_identity_refs_exposed"] is False
    assert ACCEPTED not in repr(row)
    assert SETTLED not in repr(row)
    assert accepted == {ACCEPTED}
    assert paid == {ACCEPTED}
    score = build_approved_microsite_scorecard(
        [spec()], readers=readers, window_start=START, window_end=END)
    assert score["realised_revenue_by_currency"] == {"USD": 5000}


def test_no_session_owner_retains_missing_web_traffic():
    data, readers = fixture_readers()
    without = OriginalPageReaders(
        site_owner=readers.site_owner, gsc=readers.gsc,
        crm=readers.crm, settlement=readers.settlement)
    row, _, _ = reconcile_approved_page(
        spec(), readers=without, window_start=START, window_end=END)
    assert row["consent_verified_sessions"] is None
    assert row["enquiry_per_consented_session"] is None
    assert row["organic_search_clicks"] == 2


@pytest.mark.parametrize("field,value", [
    ("canonical_campaign_id", "wrong"),
    ("canonical_asset_id", "wrong"),
    ("public_url", "https://other.com/research/campaign_aaaaaaaaaaaaaaaaaaaaaaaa"),
    ("immutable_release_readback", False),
])
def test_site_owner_release_cannot_be_self_approved(field, value):
    data, readers = fixture_readers()
    data["site"][field] = value
    with pytest.raises(ValueError):
        reconcile_approved_page(
            spec(), readers=readers, window_start=START, window_end=END)


@pytest.mark.parametrize("owner,field,value", [
    ("gsc", "window_start", "2026-10-15"),
    ("events", "window_end", "2026-10-23"),
    ("crm", "canonical_campaign_id", "campaign_bbbbbbbbbbbbbbbbbbbbbbbb"),
    ("settlement", "canonical_asset_id", "other"),
])
def test_cross_page_or_cross_period_source_rejected(owner, field, value):
    data, readers = fixture_readers()
    data[owner][field] = value
    with pytest.raises(ValueError, match="join"):
        reconcile_approved_page(
            spec(), readers=readers, window_start=START, window_end=END)


def test_missing_accepted_event_cannot_settle():
    data, readers = fixture_readers()
    data["settlement"]["original_settled_event_rows"][0]["accepted_event_ref"] = "other_accepted_12345"
    with pytest.raises(ValueError, match="not found"):
        reconcile_approved_page(
            spec(), readers=readers, window_start=START, window_end=END)


def test_amount_mismatch_or_invalid_amount_rejected():
    data, readers = fixture_readers()
    data["settlement"]["original_settled_event_rows"][0]["amount_minor"] = 4000
    with pytest.raises(ValueError, match="differs"):
        reconcile_approved_page(
            spec(), readers=readers, window_start=START, window_end=END)
    data["settlement"]["original_settled_event_rows"][0]["amount_minor"] = True
    with pytest.raises(ValueError, match="amount"):
        reconcile_approved_page(
            spec(), readers=readers, window_start=START, window_end=END)


def test_duplicate_accepted_events_rejected_even_when_counts_match():
    data, readers = fixture_readers()
    data["crm"]["buyer_accepted_events"] = 2
    data["crm"]["qualified_enquiries"] = 2
    data["crm"]["canonical_buyer_accepted_event_refs"] = [ACCEPTED, ACCEPTED]
    with pytest.raises(ValueError, match="repeats"):
        reconcile_approved_page(
            spec(), readers=readers, window_start=START, window_end=END)


def test_positive_settlement_requires_canonical_crm_owner():
    data, readers = fixture_readers()
    without = OriginalPageReaders(
        site_owner=readers.site_owner, settlement=readers.settlement)
    with pytest.raises(ValueError, match="settlement not joined"):
        reconcile_approved_page(
            spec(), readers=without, window_start=START, window_end=END)


def test_gsc_zero_is_real_zero_but_ctr_unknown():
    data, readers = fixture_readers()
    data["gsc"]["clicks"] = 0
    data["gsc"]["impressions"] = 0
    row, _, _ = reconcile_approved_page(
        spec(), readers=readers, window_start=START, window_end=END)
    assert row["organic_search_clicks"] == 0
    assert row["organic_search_impressions"] == 0
    assert row["organic_search_ctr"] is None


@pytest.mark.parametrize("start,end", [
    ("2026-10-22", "2026-10-16"),
    ("2026-10-01", "2026-12-31"),
    ("2026-10-14T11:00:00Z", "2026-10-22"),
])
def test_measurement_window_invalid(start, end):
    with pytest.raises(ValueError):
        build_approved_microsite_scorecard(
            [spec()], readers=OriginalPageReaders(),
            window_start=start, window_end=end)


def test_duplicate_factory_candidate_rejected():
    with pytest.raises(ValueError, match="duplicate factory"):
        build_approved_microsite_scorecard(
            [spec(), spec()], readers=OriginalPageReaders(),
            window_start=START, window_end=END)


def test_actual_indexable_deployment_digest_can_differ_from_draft_preview():
    data, readers = fixture_readers()
    real_deployed_digest = "b" * 64
    for row in data.values():
        row["asset_sha256"] = real_deployed_digest
    # Original site owner has explicitly tied the different production bytes
    # to the immutable draft. All collectors must refer to deployed bytes.
    row, _, _ = reconcile_approved_page(
        spec(), readers=readers, window_start=START, window_end=END)
    assert row["original_release_asset_sha256"] == real_deployed_digest
    assert row["attributed_revenue_verified"] is True
    data["crm"]["asset_sha256"] = "c" * 64
    with pytest.raises(ValueError, match="binding"):
        reconcile_approved_page(
            spec(), readers=readers, window_start=START, window_end=END)


def test_released_preview_provenance_digest_cannot_drift():
    data, readers = fixture_readers()
    data["site"]["source_preview_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="linkage"):
        reconcile_approved_page(
            spec(), readers=readers, window_start=START, window_end=END)


def test_same_canonical_campaign_cannot_be_claimed_by_two_pages():
    from tests.test_microsite_ranked_queue_outcomes_v4_20261027 import inputs
    a, b = inputs()
    source_a, _ = fixture_readers(a)
    source_b, _ = fixture_readers(b)
    lookup = {
        build_candidate(a)[0]["id"]: source_a["site"],
        build_candidate(b)[0]["id"]: source_b["site"],
    }
    reader = OriginalPageReaders(site_owner=lambda cid: lookup[cid])
    with pytest.raises(ValueError, match="campaign claimed"):
        build_approved_microsite_scorecard(
            [a, b], readers=reader,
            window_start=START, window_end=END)
