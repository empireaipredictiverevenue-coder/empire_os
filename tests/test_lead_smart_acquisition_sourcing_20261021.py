"""The roofing acquisition research cannot turn public data into contact authority."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts.review_lead_smart_acquisition_sourcing_20261021 import (
    DEMAND, PARTNERS, ROOT, evaluate,
)


def test_curated_research_has_20_distinct_candidates_and_no_promoted_buyers():
    report = evaluate()
    assert report["partner_organisations_researched"] == 20
    assert report["web_researched_sources"] == 16
    assert report["prior_handoff_sources_requiring_fresh_check"] == 4
    assert report["public_demand_discussions_observed"] == 4
    assert report["qualified_consented_homeowner_leads"] == 0
    assert report["partner_messages_sent_by_this_review"] == 0
    assert report["partner_referrals_authorized"] == 0
    assert report["buyer_affiliate_route_for_partner_visits"] == "NOT_APPROVED"
    assert report["execution_authority"] == "NONE"


def _copy_catalogue(tmp_path):
    for item in (PARTNERS, DEMAND):
        dst = tmp_path / item
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((ROOT / item).read_bytes())


def _rewrite_csv(file: Path, transform):
    with file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        items = list(reader)
    transform(items)
    with file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(items)


@pytest.mark.parametrize("mutation", ["duplicate_domain", "send_authorized", "invalid_web_url"])
def test_partner_inventory_rejects_untrusted_or_activated_sources(tmp_path, mutation):
    _copy_catalogue(tmp_path)
    def change(items):
        if mutation == "duplicate_domain":
            items[1]["source_url"] = items[0]["source_url"]
        elif mutation == "send_authorized":
            items[0]["status"] = "APPROVED_FOR_SEND"
        else:
            items[0]["source_url"] = "http://unverified-site.invalid/"
    _rewrite_csv(tmp_path / PARTNERS, change)
    with pytest.raises(ValueError, match="INVALID_OR_UNAPPROVED_PARTNER_SOURCE"):
        evaluate(tmp_path)


@pytest.mark.parametrize("mutation", ["activated", "contacted", "duplicate"])
def test_public_posts_cannot_be_promoted_into_claimed_buyer_leads(tmp_path, mutation):
    _copy_catalogue(tmp_path)
    def change(items):
        if mutation == "activated":
            items[0]["eligible_for_direct_calls"] = "true"
        elif mutation == "contacted":
            items[0]["contacted_or_replied"] = "true"
        else:
            items[0]["url"] = items[1]["url"]
    _rewrite_csv(tmp_path / DEMAND, change)
    with pytest.raises(ValueError, match="UNAUTHORIZED_DEMAND_PROMOTION"):
        evaluate(tmp_path)
