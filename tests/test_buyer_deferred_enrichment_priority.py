from datetime import datetime, timedelta, timezone

from empire_os.buyer_deferred_enrichment import BuyerDeferredEnrichmentQueue


def _queue(tmp_path):
    return BuyerDeferredEnrichmentQueue(
        deferred_path=tmp_path / "deferred.json",
        call_ready_path=tmp_path / "calls.json",
    )


def test_due_prefers_explicit_commercial_priority(tmp_path):
    q = _queue(tmp_path)
    q.enqueue({"prospect_id":"normal","reason":"no_contact_evidence","priority_score":50})
    q.enqueue({"prospect_id":"enterprise","reason":"no_contact_evidence","priority_score":95})
    due = q.due(limit=2)
    assert [row["prospect_id"] for row in due] == ["enterprise", "normal"]


def test_due_age_boost_prevents_starvation(tmp_path):
    q = _queue(tmp_path)
    q.enqueue({"prospect_id":"old-low","reason":"no_contact_evidence","priority_score":10})
    q.enqueue({"prospect_id":"new-high","reason":"no_contact_evidence","priority_score":95})
    now = datetime.now(timezone.utc)
    import json
    data = json.loads((tmp_path / "deferred.json").read_text())
    data["old-low"]["created_at"] = (now - timedelta(hours=400)).isoformat()
    data["old-low"]["next_retry_at"] = (now - timedelta(minutes=1)).isoformat()
    data["new-high"]["created_at"] = now.isoformat()
    data["new-high"]["next_retry_at"] = (now - timedelta(minutes=1)).isoformat()
    (tmp_path / "deferred.json").write_text(json.dumps(data))
    due = q.due(limit=2, now=now)
    assert [row["prospect_id"] for row in due] == ["old-low", "new-high"]


def test_reenqueue_never_lowers_existing_priority(tmp_path):
    q = _queue(tmp_path)
    q.enqueue({"prospect_id":"p1","reason":"no_contact_evidence","priority_score":95})
    q.enqueue({"prospect_id":"p1","reason":"outreach_not_ready","priority_score":20})
    row = q.due(limit=1)[0]
    assert row["priority_score"] == 95


def test_due_deprioritises_retry_saturated_site_failure(tmp_path):
    q = _queue(tmp_path)
    q.enqueue({
        "prospect_id": "saturated",
        "reason": "site_unavailable",
        "priority_score": 100,
    })
    q.enqueue({
        "prospect_id": "evidence-rich",
        "reason": "no_contact_evidence",
        "priority_score": 90,
        "target_people": [{
            "name": "Jane Buyer",
            "title": "Founder",
            "source": "first_party_site_current",
            "evidence_url": "https://example.com/about",
        }],
        "offer_key": "predictive_revenue_diagnostic",
        "wave": "buyer_scout_review_ready",
    })
    import json
    data = json.loads((tmp_path / "deferred.json").read_text())
    data["saturated"]["attempts"] = 20
    data["evidence-rich"]["attempts"] = 1
    (tmp_path / "deferred.json").write_text(json.dumps(data))
    due = q.due(limit=2)
    assert [row["prospect_id"] for row in due] == [
        "evidence-rich",
        "saturated",
    ]


def test_claim_due_prevents_duplicate_worker_claims(tmp_path):
    q = _queue(tmp_path)
    for prospect_id in ("p1", "p2", "p3", "p4"):
        q.enqueue({
            "prospect_id": prospect_id,
            "reason": "no_contact_evidence",
            "priority_score": 90,
        })

    first = q.claim_due(limit=2, worker_id="worker-a")
    second = q.claim_due(limit=2, worker_id="worker-b")

    first_ids = {row["prospect_id"] for row in first}
    second_ids = {row["prospect_id"] for row in second}
    assert first_ids
    assert second_ids
    assert first_ids.isdisjoint(second_ids)


def test_expired_claim_is_recovered_by_another_worker(tmp_path):
    q = _queue(tmp_path)
    q.enqueue({
        "prospect_id": "p1",
        "reason": "no_contact_evidence",
        "priority_score": 90,
    })
    now = datetime.now(timezone.utc)
    first = q.claim_due(
        limit=1,
        worker_id="worker-a",
        lease_seconds=60,
        now=now,
    )
    assert first[0]["lease_owner"] == "worker-a"

    recovered = q.claim_due(
        limit=1,
        worker_id="worker-b",
        lease_seconds=60,
        now=now + timedelta(seconds=61),
    )
    assert recovered[0]["prospect_id"] == "p1"
    assert recovered[0]["lease_owner"] == "worker-b"


def test_defer_again_clears_worker_lease(tmp_path):
    q = _queue(tmp_path)
    q.enqueue({
        "prospect_id": "p1",
        "reason": "no_contact_evidence",
        "priority_score": 90,
    })
    q.claim_due(limit=1, worker_id="worker-a")
    q.defer_again(
        "p1",
        reason="no_bound_contact",
        attempts=1,
        retry_minutes=5,
    )
    import json
    row = json.loads((tmp_path / "deferred.json").read_text())["p1"]
    assert row["status"] == "deferred"
    assert row["lease_owner"] is None
    assert row["lease_expires_at"] is None


def test_due_prioritises_near_sendable_named_buyer(tmp_path):
    q = _queue(tmp_path)
    q.enqueue({
        "prospect_id": "identity-gap",
        "reason": "no_decision_maker",
        "priority_score": 100,
    })
    q.enqueue({
        "prospect_id": "contact-gap",
        "reason": "no_bound_contact",
        "priority_score": 95,
        "target_people": [{
            "name": "Jane Smith",
            "title": "Founder",
            "source": "first_party_site_current",
            "evidence_url": "https://acme.test/about",
        }],
        "company_contact_routes": [{
            "channel": "email",
            "value": "info@acme.test",
            "verified": True,
        }],
        "offer_key": "predictive_revenue_diagnostic",
    })
    import json
    data = json.loads((tmp_path / "deferred.json").read_text())
    data["contact-gap"]["attempts"] = 10
    (tmp_path / "deferred.json").write_text(json.dumps(data))

    due = q.due(limit=2)
    assert [row["prospect_id"] for row in due] == [
        "contact-gap", "identity-gap",
    ]


def test_enqueue_drops_false_target_people(tmp_path):
    q = _queue(tmp_path)
    q.enqueue({
        "prospect_id": "p-false",
        "reason": "no_bound_contact",
        "priority_score": 90,
        "target_people": [
            {"name": "Case Studies", "title": "Managing Director"},
            {"name": "New Orleans", "title": "Owner"},
            {"name": "Jane Smith", "title": "Founder"},
        ],
    })
    row = q.due(limit=1)[0]
    assert [p["name"] for p in row["target_people"]] == ["Jane Smith"]

def test_claim_due_quarantines_retry_saturated_while_productive_work_exists(tmp_path):
    q = _queue(tmp_path)
    q.enqueue({"prospect_id":"saturated","reason":"no_contact_evidence","priority_score":100})
    q.enqueue({
        "prospect_id":"hot","reason":"no_bound_contact","priority_score":80,
        "target_people":[{"name":"Jane Buyer","title":"Founder"}],
    })
    import json
    data=json.loads((tmp_path/"deferred.json").read_text())
    data["saturated"]["attempts"]=8
    (tmp_path/"deferred.json").write_text(json.dumps(data))
    claimed=q.claim_due(limit=1,worker_id="worker-a")
    assert claimed[0]["prospect_id"]=="hot"


def test_snapshot_exposes_recovery_lanes(tmp_path):
    q = _queue(tmp_path)
    q.enqueue({
        "prospect_id":"hot","reason":"no_bound_contact",
        "target_people":[{"name":"Jane Buyer","title":"Founder"}],
    })
    q.enqueue({"prospect_id":"identity","reason":"no_decision_maker"})
    snap=q.snapshot()
    assert snap["recovery_lane_counts"]["hot_contact_recovery"] == 1
    assert snap["recovery_lane_counts"]["identity_recovery"] == 1
