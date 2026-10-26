"""Do not turn degraded search locale collisions into contactable US buyers."""
from datetime import datetime, timezone

from empire_os.buyer_public_research_seed import build_public_research_seeds


def test_foreign_domain_is_held_from_us_metro_scout_without_losing_existing_publishers():
    def fake_search(queries, num):
        # One public HTML SERP returned an irrelevant French company to a US
        # roofing volume query. This is synthetic regression, not live SERP.
        return {
            q: ["energietpfdm.fr", "roofingexample.com", "example.co.uk"]
            for q in queries if " TX" in q or " OK" in q or " IL" in q
        }
    packet=build_public_research_seeds(
        {}, search_fn=fake_search, max_queries=25,
        observed_at=datetime(2026,10,26,16,0,tzinfo=timezone.utc),
    )
    rows={x["domain"]:x for x in packet["seeds"]}
    assert "roofingexample.com" in rows
    assert "energietpfdm.fr" not in rows
    assert "example.co.uk" not in rows
    # Original manually reviewed programme seeds MUST remain present.
    assert "leadsbycall.com" in rows
    assert "leads2trade.co.uk" in rows
    assert packet["local_search_country_tld_conflict_rows_held"]>0
    assert packet["commercial_authority"]=="none"
    assert packet["outbound_sent"] is False


def test_european_domains_on_uk_publisher_search_are_not_globally_deleted():
    def fake_search(queries,num):
        return {q:["partnerprogram.fr"] for q in queries if "publisher" in q}
    packet=build_public_research_seeds(
        {},search_fn=fake_search,max_queries=2,include_volume=False,
        observed_at=datetime(2026,10,26,16,0,tzinfo=timezone.utc),
    )
    assert "partnerprogram.fr" in {x["domain"] for x in packet["seeds"]}
    assert packet["local_search_country_tld_conflict_rows_held"]==0


def test_source_stays_research_not_qualified_buyer_even_for_matching_tld():
    def fake_search(queries,num):
        return {q:["roofingexample.com"] for q in queries}
    result=build_public_research_seeds({},search_fn=fake_search,max_queries=20,
        observed_at=datetime(2026,10,26,16,0,tzinfo=timezone.utc))
    x=next(s for s in result["seeds"] if s["domain"]=="roofingexample.com")
    for claim in ("identity_verified","commercial_terms_verified","buyer_capacity_verified",
                  "buyer_price_verified","outreach_authorized"):
        assert x[claim] is False
