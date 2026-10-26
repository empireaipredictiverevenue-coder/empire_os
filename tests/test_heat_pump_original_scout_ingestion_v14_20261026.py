"""V14: original scheduled Scout consumes V13 heat-pump research without false buys."""
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os import buyer_public_research_seed as public
from empire_os import buyer_acquisition_scout as scout
from empire_os.heat_pump_market_expansion import materialize

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 26, 21, 30, tzinfo=timezone.utc)


def evidence():
    registry = {"schema_version": "empire.commercial_relationship_registry.v1",
                "relationships": [{
                    "identity_domains": ["leadpronto.co.uk"],
                    "last_outbound_at": "2026-10-21T19:36:25+00:00",
                    "do_not_pursue": False, "gmail_thread_ids": [],
                }]}
    queue = {"candidates": []}
    return materialize(
        (ROOT / "docs/commercial/HEAT_PUMP_MARKET_EXPANSION_SEEDS_20261026.tsv").read_bytes(),
        registry, queue, now=NOW,
    )


def test_original_seed_reader_uses_all_32_safe_research_domains(monkeypatch):
    monkeypatch.setattr(public, "review_original_heat_pump_market",
                        lambda root, now, write: evidence())
    payload = public.build_public_research_seeds(
        {}, search_fn=lambda queries, num: {}, max_queries=2,
        observed_at=NOW,
    )
    before = len(payload["seeds"])
    public.append_existing_heat_pump_market_review(payload, ROOT, now=NOW)
    ingested = payload["heat_pump_market_ingestion"]
    assert ingested["seed_domain_count"] == 32
    assert ingested["prior_contact_or_identity_held"] == 2
    assert payload["seed_count"] > before
    heat = [x for x in payload["seeds"] if any(
        r.startswith("public:heat_pump_review:UK:") for r in x["source_refs"])]
    assert len(heat) == 32
    assert all(x["outreach_authorized"] is False for x in heat)
    assert not any(x["domain"] in ("leadpronto.co.uk", "newpoweruk.co.uk")
                   for x in heat)
    assert ingested["outbound_authorized"] is False


def test_missing_or_tampered_source_does_not_erase_original_research(monkeypatch):
    payload = public.build_public_research_seeds(
        {}, search_fn=lambda q, num: {}, max_queries=2, observed_at=NOW)
    count = len(payload["seeds"])
    monkeypatch.setattr(public, "review_original_heat_pump_market",
                        lambda root, now, write: {**evidence(), "outbound_authorized": True})
    public.append_existing_heat_pump_market_review(payload, ROOT, now=NOW)
    assert len(payload["seeds"]) == count
    assert payload["heat_pump_market_ingestion"]["seed_domain_count"] == 0


def test_scout_rotates_existing_two_probe_slots_without_extra_search(monkeypatch):
    monkeypatch.setattr(scout, "probe_site",
                        lambda url, **k: {"ok": False, "error": "offline_fixture"})
    source = evidence()
    seeds = [{
        "domain": x["domain"], "website": "https://" + x["domain"],
        "source_refs": ["public:heat_pump_review:UK:" + x["domain"]],
        "target_buyer_pools": ["potential_partner_research"],
        "target_markets": ["UK"], "outreach_authorized": False,
    } for x in source["companies"] if x["original_contact_state"] not in (
        "PRIOR_OUTBOUND_REVIEW_THREAD_NO_DUPLICATE",
        "POSSIBLE_NEWPOWER_ADVANCED_ALIAS_VERIFY_NO_DUPLICATE")]
    result = scout.run_buyer_scout(
        {}, research_seed_records=seeds, max_queries=2,
        max_domains=40, max_probes=20, search_enabled=False)
    assert result["heat_pump_review_seed_count"] == 32
    assert result["heat_pump_review_included_count"] == 2
    assert result["heat_pump_review_probed_count"] == 2
    assert result["probed_domain_count"] <= 20
    assert result["heat_pump_additional_search_queries"] == 0
    assert result["heat_pump_new_probe_capacity"] == 0
    assert result["heat_pump_review_claims_are_not_buyer_approval"] is True
    assert result["outbound_sent"] is False
    assert result["database_write_performed"] is False


def test_tiny_scout_budget_never_displaces_existing_important_work(monkeypatch):
    monkeypatch.setattr(scout, "probe_site",
                        lambda url, **k: {"ok": False, "error": "offline_fixture"})
    out = scout.run_buyer_scout(
        {}, max_queries=1, max_domains=2, max_probes=1,
        search_enabled=False, research_seed_records=[{
            "website": "https://goodenergy.co.uk",
            "source_refs": ["public:heat_pump_review:UK:goodenergy.co.uk"],
            "target_buyer_pools": ["potential_partner_research"],
        }])
    assert out["heat_pump_review_included_count"] == 0
    assert out["heat_pump_review_probed_count"] == 0
    assert out["domain_count"] <= 2
