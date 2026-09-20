from uuid import uuid4

import empire_os.qualification_worker_v2 as worker


def _prospect():
    return {
        "id": str(uuid4()),
        "business_name": "Real Roofing Co",
        "niche": "roofing",
        "metro": "Austin",
        "phone": "5125550101",
        "website": None,
        "address": "100 Main St, Austin, TX",
        "buy_signal_score": None,
    }


def test_evidence_backed_payload_uses_v2_and_preserves_provenance(monkeypatch):
    monkeypatch.setattr(
        worker,
        "enrich_prospect_for_scoring",
        lambda prospect: {
            "fields": {
                "website": "https://realroofing.example",
                "email": "sales@realroofing.example",
            },
            "enrichment_score": 80.0,
            "sources": ["website"],
            "evidence": [
                {"source": "identity_guard", "accepted": True},
                {"source": "website", "accepted": True},
            ],
            "enriched_at": "2026-09-20T11:00:00+00:00",
        },
    )

    payload = worker.build_evidence_backed_payload(_prospect())

    assert payload["scoring_version"] == "v2"
    assert payload["input_snapshot"]["website"] == "https://realroofing.example"
    assert payload["engagement_potential_score"] is None
    assert "engagement_potential" in payload["unknown_dimensions"]
    assert payload["result_payload"]["enrichment"]["sources"] == ["website"]


def test_rejected_site_does_not_become_canonical_evidence(monkeypatch):
    monkeypatch.setattr(
        worker,
        "enrich_prospect_for_scoring",
        lambda prospect: {
            "fields": {},
            "enrichment_score": 0.0,
            "sources": [],
            "evidence": [
                {
                    "source": "identity_guard",
                    "accepted": False,
                    "reasons": ["phone_mismatch"],
                },
                {"source": "website", "accepted": False},
            ],
            "enriched_at": "2026-09-20T11:00:00+00:00",
        },
    )

    prospect = _prospect()
    prospect["phone"] = None
    payload = worker.build_evidence_backed_payload(
        prospect,
        acquisition_website="https://wrong.example",
    )

    assert not payload["input_snapshot"].get("website")
    assert payload["tier"] == "insufficient_evidence"
    assert payload["result_payload"]["enrichment"]["evidence"][0]["accepted"] is False


def test_cycle_continues_after_one_prospect_failure(monkeypatch):
    prospects = [_prospect(), _prospect()]
    monkeypatch.setattr(worker, "fetch_pending_prospects", lambda limit: prospects)

    def fake_qualify(prospect):
        if prospect["id"] == prospects[0]["id"]:
            raise RuntimeError("network down")
        return {"prospect_id": prospect["id"], "tier": "warm"}

    monkeypatch.setattr(worker, "qualify_prospect", fake_qualify)
    result = worker.run_cycle(limit=2)

    assert result["attempted"] == 2
    assert result["qualified"] == 1
    assert result["failed"] == 1
    assert result["real_data_only"] is True
    assert result["outreach_enabled"] is False
    assert result["payment_enabled"] is False
