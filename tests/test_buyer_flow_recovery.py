"""Source-quality filtering and same-company evidence progression tests."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from empire_os.buyer_acquisition_scout import run_buyer_scout
from empire_os.buyer_flow_recovery import (
    candidate_evidence_states, compare_repeated_domains, plan_recovery,
)
from empire_os.buyer_claim_provenance import classify_buyer_source_pages
from empire_os.revenue_flow_meter import RECEIPTS, SOURCE_SCHEMAS, refresh_flow_meter

NOW = datetime.now(timezone.utc)


def _plan():
    return {"priority_targets": [], "product_priority_targets": [],
            "icp_priority_targets": [{
                "icp_profile_key": "high_ticket_home_service",
                "research_queries": {"end_service_buyers": ["roofing leads buyer"]},
            }]}


def _evidence(url):
    return {"ok": True, "canonical_url": url, "final_url": url,
            "title": "Example Buyer", "business_names": ["Example Buyer"],
            "description": "Commercial contracting", "emails": [],
            "phones": [], "people": [], "pages_checked": [
                {"url": url, "visible_text": "Commercial contracting"}],
            "evidence_score": 0.4}


def test_search_engine_result_excluded_before_site_probe(monkeypatch):
    seen = []
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {q: ["search.google", "cybo.com", "buyer.example"] for q in queries})
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda url, **kw: (seen.append(url) or _evidence(url)))
    out = run_buyer_scout(_plan(), max_queries=2, max_domains=5, max_probes=5)
    assert out["candidate_count"] == out["search_domain_count"] == 1
    assert out["rejected_search_infrastructure_domain_count"] == 2
    assert out["candidates"][0]["domain"] == "buyer.example"
    assert seen == ["https://buyer.example"]
    assert out["outbound_sent"] is False


def test_noise_only_does_not_block_canonical_fallback(monkeypatch):
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {q: ["search.google"] for q in queries})
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda url, **kw: _evidence(url))
    out = run_buyer_scout(_plan(), max_queries=2, max_domains=5, max_probes=5,
        canonical_seed_records=[{
            "id": "seed", "business_name": "Example Buyer",
            "website": "https://buyer.example", "niche": "roofing",
            "icp_profile_key": "high_ticket_home_service",
        }])
    assert out["search_domain_count"] == 0
    assert out["canonical_seed_fallback_used"] is True
    assert out["rejected_search_infrastructure_domain_count"] == 1
    assert out["candidates"][0]["domain"] == "buyer.example"


def test_prioritise_high_impact_blockers_and_marketplace_review():
    flow = {"source_health": {"scout": {"status": "fresh"},
             "review": {"status": "fresh"}}, "blockers": [
        {"reason": "site_evidence_below_floor", "count": 93},
        {"reason": "direct_buyer_evidence_missing", "count": 44},
        {"reason": "official_registry_identity_mismatch", "count": 28},
        {"reason": "untrusted_commercial_funnel_snapshot", "count": None},
    ]}
    scout = {"candidates": [
        {"domain": "unknown.example", "website": "https://unknown.example",
         "buyer_relationship": "unknown", "site_evidence_score": 0.2},
        {"domain": "partner.example", "website": "https://partner.example",
         "buyer_relationship": "intermediary_or_marketplace"},
        {"domain": "search.google", "website": "https://search.google"},
    ]}
    result = plan_recovery(flow, scout, now=NOW)
    assert [r["blocking_reason"] for r in result["holding_blocker_priority"]][:3] == [
        "direct_buyer_evidence_missing", "official_registry_identity_mismatch",
        "site_evidence_below_floor"]
    assert result["scout_target_population"] == 2
    targets = {r["company_domain"]: r for r in result["scout_targets"]}
    assert targets["unknown.example"]["next_evidence_action"] == "first_party_purchase_claim_recovery"
    assert targets["partner.example"]["next_evidence_action"] == "partner_relationship_review"
    assert result["execution_authority"] == "none"
    assert result["outbound_sent"] is False


def test_stale_review_yields_no_inventory_priority():
    flow = {"source_health": {"scout": {"status": "fresh"},
             "review": {"status": "stale"}},
            "blockers": [{"reason": "site_evidence_below_floor", "count": 93}]}
    result = plan_recovery(flow, {"candidates": []}, now=NOW)
    assert result["holding_blocker_priority"] == []
    assert result["status"] == "source_receipts_stale_or_unavailable"


def test_duplicate_and_cross_domain_candidates_not_eligible():
    row = {"domain": "buyer.example", "website": "https://buyer.example"}
    output = candidate_evidence_states({"candidates": [
        row, dict(row), {"domain": "buyer.example",
                         "website": "https://buyer.example.evil.test"},
    ]}, now=NOW)
    assert output == {}


def test_same_domain_improvement_not_revenue_conversion():
    before = {"fingerprint": {
        "purchase_statement_verified": False,
        "named_person_email_bound": False,
        "canonical_company_correlated": False}}
    after = {"fingerprint": {
        "purchase_statement_verified": True,
        "named_person_email_bound": False,
        "canonical_company_correlated": True}}
    result = compare_repeated_domains(before, after)
    assert result["repeated_company_count"] == 1
    assert result["newly_observed"]["purchase_statement_verified"] == 1
    assert result["newly_observed"]["canonical_company_correlated"] == 1
    assert result["causal_revenue_conversion_rate"] is None
    assert compare_repeated_domains(before, {})["status"] == "no_repeat_companies"


def _write_receipts(root, timestamp, *, with_statement):
    scout = {"candidate_count": 1, "candidates": [
        {"domain": "buyer.example", "website": "https://buyer.example"}]}
    if with_statement:
        scout["candidates"][0]["buyer_claim_provenance"] = classify_buyer_source_pages(
            [{"url": "https://buyer.example/partners",
              "visible_text": "We buy leads from qualified publishers."}],
            company_website="https://buyer.example",
            observed_at=timestamp.isoformat())
    data = {
        "scout": scout,
        "reconciliation": {"candidate_count": 1,
                           "results": [{"domain": "buyer.example"}]},
        "persistence": {"persisted_candidate_count": 1},
        "review": {"candidate_count": 4, "review_ready_count": 0,
                   "blocked_reason_counts": {"site_evidence_below_floor": 4}},
        "quality": {"stage_receipts_time_aligned": True,
                    "scout_receipt_fresh": True,
                    "candidate_with_valid_direct_purchase_receipt": int(with_statement),
                    "candidate_with_strict_named_person_email_binding": 0},
        "astra": {"canonical_company_binding_count": 0},
        "commercial_funnel": {"counts": {"outbound_delivered": 0}},
        "revenue_pulse": {"recognized_revenue_truth": {
            "recognized_revenue_cents": 0}},
    }
    for key, obj in data.items():
        obj["schema_version"] = SOURCE_SCHEMAS[key]
        obj["generated_at"] = timestamp.isoformat()
    data["quality"]["source_generated_at"] = {
        k: timestamp.isoformat() for k in (
            "scout", "reconciliation", "persistence", "holding_review")}
    for key, path in RECEIPTS.items():
        file = root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(data[key]))


def test_persisted_private_history_tracks_repeated_buyer_evidence(tmp_path):
    _write_receipts(tmp_path, NOW-timedelta(minutes=10), with_statement=False)
    first = refresh_flow_meter(tmp_path, now=NOW-timedelta(minutes=9))
    assert first["repeat_company_evidence_progress"]["status"] == "baseline_only"
    _write_receipts(tmp_path, NOW, with_statement=True)
    second = refresh_flow_meter(tmp_path, now=NOW+timedelta(seconds=1))
    progress = second["repeat_company_evidence_progress"]
    assert progress["status"] == "matched_repeat_companies"
    assert progress["repeated_company_count"] == 1
    assert progress["newly_observed"]["purchase_statement_verified"] == 1
    assert progress["causal_revenue_conversion_rate"] is None
    history_file = tmp_path / "runtime/buyer_acquisition/flow_meter_history.json"
    assert "buyer.example" not in history_file.read_text()
    assert json.loads(history_file.read_text())["sample_count"] == 2
    again = refresh_flow_meter(tmp_path, now=NOW+timedelta(seconds=2))
    assert again["tracking"]["history_count"] == 2


def test_mismatched_receipts_do_not_create_repeat_domain_evidence(tmp_path):
    _write_receipts(tmp_path, NOW, with_statement=False)
    quality = tmp_path / RECEIPTS["quality"]
    data = json.loads(quality.read_text())
    data["source_generated_at"]["scout"] = (NOW-timedelta(hours=2)).isoformat()
    quality.write_text(json.dumps(data))
    out = refresh_flow_meter(tmp_path, now=NOW+timedelta(seconds=1))
    assert out["repeat_company_evidence_progress"]["status"] == "baseline_only"
    assert "cohort_domain_evidence" in json.loads(
        (tmp_path/"runtime/buyer_acquisition/flow_meter_history.json").read_text()
    )["samples"][0]


def test_directory_domain_cannot_reenter_via_canonical_or_research_seed(monkeypatch):
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {q: [] for q in queries})
    seen = []
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda url, **kw: (seen.append(url) or _evidence(url)))
    result = run_buyer_scout(_plan(), max_queries=1, max_domains=5,
        canonical_seed_records=[{
            "id": "seed-cybo", "business_name": "Cybo",
            "website": "https://cybo.com",
            "icp_profile_key": "high_ticket_home_service",
        }],
        research_seed_records=[{
            "website": "https://search.google",
            "target_buyer_pools": ["direct_demand_buyers"],
            "source_queries": ["site buyers"],
        }])
    assert result["candidate_count"] == 0
    assert result["canonical_seed_domain_count"] == 0
    assert result["rejected_search_infrastructure_domain_count"] == 2
    assert seen == []


def test_generic_gmail_host_is_not_buyer_candidate_even_if_search_returns_it(monkeypatch):
    seen = []
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {q: ["gmail.com", "actual-installer.example"] for q in queries},
    )
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda url, **kw: (seen.append(url) or _evidence(url)),
    )
    out=run_buyer_scout(_plan(), max_queries=2, max_domains=5, max_probes=5)
    assert out["search_domain_count"] == 1
    assert out["rejected_search_infrastructure_domain_count"] == 1
    assert {row["domain"] for row in out["candidates"]} == {"actual-installer.example"}
    assert seen == ["https://actual-installer.example"]
    # The suppression is for EXACT domain-as-business discovery only;
    # it does not block companies whose own website lists a Gmail contact.
    states = candidate_evidence_states({
        "candidates": [
            {"domain": "gmail.com", "website": "https://gmail.com",
             "buyer_relationship": "unknown"},
            {"domain": "actual-installer.example",
             "website": "https://actual-installer.example",
             "buyer_relationship": "unknown",
             "first_party_people": [{"email": "owner@gmail.com"}]},
        ]
    }, now=NOW)
    assert len(states) == 1
