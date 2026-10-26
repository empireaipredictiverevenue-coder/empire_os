from datetime import datetime, timezone
import pytest

from empire_os.search_intelligence.backlinks import BacklinkObservation
from empire_os.search_intelligence.earned_authority_reconciliation import (
    AuthorityEvidenceHeld, reconcile_earned_authority,
)


def archive():
    return dict(
        schema_version="empire.cc.graph.referrer_review_queue.v1",
        source="commoncrawl_2026_domain_webgraph", mode="OBSERVE",
        no_page_level_backlink_proof=True, manual_review_required_for_all=True,
        empiredb_writes=False, distinct_historical_source_domains=3,
        cross_target_source_domain_count=1, manual_review_queue=[{}, {}, {}],
    )


def editorial():
    return dict(
        schema_version="empire.marketing.earned_editorial_opportunities.v1",
        mode="OBSERVE", outbound_authorized=False,
        publication_authorized=False, site_modified=False,
        existing_independently_verified_backlinks=1,
        new_external_links_earned_this_run=0,
        verified_live_first_party_link_additions=27,
        publishers=[{"publisher": "InfoQ"}, {"publisher": "Roofing Contractor"}],
    )


def observed():
    return BacklinkObservation(
        source_url="https://agenstry.com/providers/Empire%20AI",
        target_url="https://empire-ai.co.uk",
        observed_at=datetime(2026, 10, 26, tzinfo=timezone.utc).isoformat(),
        rel="", provenance=("exact_public_html_anchor",),
    )


def call(**kwargs):
    values=dict(historical_review=archive(), editorial_queue=editorial(),
                live_anchor_observations=[], canonical_stored_backlink_count=0)
    values.update(kwargs)
    return reconcile_earned_authority(**values)


def test_historical_domain_links_and_internal_links_not_counted_as_external():
    result=call()
    assert result["historical_commoncrawl_distinct_domain_candidates"]==3
    assert result["historical_domain_graph_is_page_backlink_proof"] is False
    assert result["original_editorial_receipt_internal_link_additions"]==27
    assert result["first_party_links_are_external_backlinks"] is False
    assert result["current_caller_observed_external_links"]==0
    assert result["reconciliation_needed"] is False


def test_one_real_observed_anchor_with_zero_canonical_rows_surfaces_gap():
    result=call(live_anchor_observations=[observed()])
    assert result["current_caller_observed_external_links"]==1
    assert result["current_caller_observed_referring_domains"]==1
    assert result["canonical_stored_backlink_count"]==0
    assert result["reconciliation_needed"] is True
    assert result["authority_score"] is None
    assert result["ranking_lift_verified"] is False
    assert result["automatic_link_exchange_authorized"] is False
    assert result["next_owner_action"].startswith("VERIFY_AND_ADMIT")


def test_caller_observed_anchor_not_unconditionally_promoted_to_canonical_truth():
    r=call(live_anchor_observations=[observed()],canonical_stored_backlink_count=None)
    assert r["reconciliation_needed"] is False
    assert r["current_observed_anchor_report_is_canonical_proof"] is False


@pytest.mark.parametrize("edit", [
    {"source":"random"},
    {"no_page_level_backlink_proof":False},
    {"manual_review_queue":[]},
    {"cross_target_source_domain_count":4},
    {"empiredb_writes":True},
])
def test_archive_provenance_and_coherence_required(edit):
    a=archive()
    a.update(edit)
    with pytest.raises(AuthorityEvidenceHeld):
        call(historical_review=a)


@pytest.mark.parametrize("edit", [
    {"outbound_authorized":True},
    {"publication_authorized":True},
    {"schema_version":"wrong"},
    {"publishers":"not a list"},
])
def test_editorial_custody_and_review_required(edit):
    e=editorial()
    e.update(edit)
    with pytest.raises(AuthorityEvidenceHeld):
        call(editorial_queue=e)


def test_malformed_canonical_count_fails_closed():
    with pytest.raises(AuthorityEvidenceHeld):
        call(canonical_stored_backlink_count=False)


def test_original_backlink_analyzer_rejects_invalid_anchor_provenance():
    broken=BacklinkObservation(
        source_url="https://site.test",target_url="https://empire-ai.co.uk",
        observed_at="2026-10-26",provenance=(),
    )
    with pytest.raises(ValueError):
        call(live_anchor_observations=[broken])
