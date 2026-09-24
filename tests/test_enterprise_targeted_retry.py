from datetime import datetime, timezone
from types import SimpleNamespace

from empire_os.buyer_deferred_enrichment import BuyerDeferredEnrichmentQueue
import scripts.run_buyer_deferred_enrichment as worker


def test_deferred_queue_preserves_enterprise_target_context(tmp_path):
    queue = BuyerDeferredEnrichmentQueue(
        deferred_path=tmp_path / "deferred.json",
        call_ready_path=tmp_path / "calls.json",
    )
    assert queue.enqueue({
        "prospect_id": "00000000-0000-0000-0000-000000000123",
        "business_name": "Apex Service Partners",
        "website": "https://apexservicepartners.com",
        "reason": "no_bound_contact",
        "account_key": "apex_service_partners",
        "wave": "direct_enterprise",
        "offer_key": "predictive_revenue_intelligence_os",
        "target_people": [
            {"name": "AJ Brown", "title": "Co-Chief Executive Officer"},
            {"name": "Will Matson", "title": "Co-Chief Executive Officer"},
        ],
        "target_product_codes": [
            "predictive_revenue_intelligence_os",
            "predictive_revenue_private_strategic",
        ],
    })

    due = queue.due(
        now=datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
    )
    assert len(due) == 1
    row = due[0]
    assert row["account_key"] == "apex_service_partners"
    assert row["offer_key"] == "predictive_revenue_intelligence_os"
    assert row["target_people"][0]["name"] == "AJ Brown"
    assert len(row["target_people"]) == 2


def _candidate():
    return SimpleNamespace(
        to_dict=lambda: {
            "prospect_id": "00000000-0000-0000-0000-000000000123",
            "entity_id": None,
            "business_name": "Apex Service Partners",
            "niche": "predictive_revenue_enterprise",
            "metro": "United States",
            "website": "https://apexservicepartners.com",
            "phone": "",
            "contact_name": "",
            "contact_title": "",
            "contact_source": "public_enterprise_target",
            "decision_role": "unknown",
            "decision_score": 0.0,
            "company_score": 40.0,
            "offer_key": "software_mrr",
            "evidence": {},
            "mode": "OBSERVE",
            "write_authorized": False,
        }
    )


def test_targeted_enterprise_probe_accepts_only_intended_person(monkeypatch):
    def probe(row, **kwargs):
        assert row["contact_name"] == "AJ Brown"
        return {
            "decision_maker": {
                "name": "AJ Brown",
                "title": "Co-Chief Executive Officer",
            },
            "review_ready": True,
            "outreach_ready": True,
            "person_bound": True,
            "preferred_email": "aj@apex.example",
        }

    monkeypatch.setattr(worker, "run_buyer_probe_isolated", probe)
    result, used = worker._targeted_enterprise_probe(
        _candidate(),
        {
            "target_people": [{
                "name": "AJ Brown",
                "title": "Co-Chief Executive Officer",
            }],
        },
        available_budget=2,
        attempts=1,
    )
    assert used == 1
    assert result["enterprise_target_match"] is True
    assert result["outreach_ready"] is True


def test_targeted_enterprise_probe_blocks_identity_drift(monkeypatch):
    def probe(row, **kwargs):
        return {
            "decision_maker": {
                "name": "Random Executive",
                "title": "Chief Executive Officer",
            },
            "review_ready": True,
            "outreach_ready": True,
            "person_bound": True,
            "preferred_email": "random@apex.example",
        }

    monkeypatch.setattr(worker, "run_buyer_probe_isolated", probe)
    result, used = worker._targeted_enterprise_probe(
        _candidate(),
        {
            "target_people": [{
                "name": "AJ Brown",
                "title": "Co-Chief Executive Officer",
            }],
        },
        available_budget=2,
        attempts=1,
    )
    assert used == 1
    assert result["enterprise_target_match"] is False
    assert result["review_ready"] is False
    assert result["outreach_ready"] is False
    assert result["rejection_reason"] == "target_identity_mismatch"


def test_targeted_enterprise_probe_rotates_target_people_by_attempt(monkeypatch):
    seen = []

    def probe(row, **kwargs):
        seen.append(row["contact_name"])
        return {
            "decision_maker": {
                "name": row["contact_name"],
                "title": row["contact_title"],
            },
            "review_ready": False,
            "outreach_ready": False,
            "person_bound": False,
            "preferred_email": None,
        }

    monkeypatch.setattr(worker, "run_buyer_probe_isolated", probe)
    people = [
        {"name": "Person One", "title": "Chief Executive Officer"},
        {"name": "Person Two", "title": "Chief Revenue Officer"},
        {"name": "Person Three", "title": "Chief Marketing Officer"},
    ]
    worker._targeted_enterprise_probe(
        _candidate(),
        {"target_people": people},
        available_budget=2,
        attempts=1,
    )
    assert seen == ["Person One", "Person Two"]

    seen.clear()
    worker._targeted_enterprise_probe(
        _candidate(),
        {"target_people": people},
        available_budget=2,
        attempts=2,
    )
    assert seen == ["Person Three", "Person One"]
