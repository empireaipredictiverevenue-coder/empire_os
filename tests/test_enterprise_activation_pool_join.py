"""Stale location snapshots cannot bypass the current enterprise pool."""
import json

from scripts import activate_predictive_revenue_enterprise_targets as activation


def save(root, relative, value):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def record(domain, candidate_id):
    return {
        "domain": domain,
        "candidate_id": candidate_id,
        "account_name": domain,
        "website": f"https://{domain}/",
        "location_verified": True,
        "location_evidence_addresses": ["Austin, TX 78701"],
    }


def test_only_current_pool_members_can_reach_rolling_acquisition(monkeypatch, tmp_path):
    monkeypatch.setattr(activation, "REPO_ROOT", tmp_path)
    current = record("current.example", "fresh-id")
    removed = record("removed.example", "stale-id")
    save(tmp_path, "runtime/predictive_revenue/enterprise_pool_latest.json", {
        "rolling_candidates": [current], "outreach_authorized": False,
    })
    save(tmp_path, "runtime/predictive_revenue/enterprise_location_enrichment_latest.json", {
        "candidates": [removed, current], "outreach_authorized": False,
    })
    save(tmp_path, "runtime/buyer_acquisition/promotion_plan_latest.json", {
        "proposals": [
            {"domain": "current.example", "candidate_id": "fresh-id",
             "first_party_emails_preserved_for_identity_resolution": []},
            {"domain": "removed.example", "candidate_id": "stale-id",
             "first_party_emails_preserved_for_identity_resolution": []},
        ]
    })
    results = activation._rolling_candidates()
    assert len(results) == 1
    assert results[0][0].name == "current.example"
    assert results[0][1]["account_key"] == "rolling:current.example"
    assert results[0][0].raw["outreach_authorized"] is False


def test_stale_identity_cannot_be_activated(monkeypatch, tmp_path):
    monkeypatch.setattr(activation, "REPO_ROOT", tmp_path)
    save(tmp_path, "runtime/predictive_revenue/enterprise_pool_latest.json", {
        "rolling_candidates": [record("current.example", "fresh-id")],
    })
    save(tmp_path, "runtime/predictive_revenue/enterprise_location_enrichment_latest.json", {
        "candidates": [record("current.example", "old-id")],
    })
    save(tmp_path, "runtime/buyer_acquisition/promotion_plan_latest.json", {
        "proposals": [{"domain": "current.example", "candidate_id": "fresh-id"}],
    })
    assert activation._rolling_candidates() == []


def test_missing_current_pool_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(activation, "REPO_ROOT", tmp_path)
    assert activation._rolling_candidates() == []
