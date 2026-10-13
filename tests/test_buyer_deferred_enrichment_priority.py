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
    assert [row["prospect_id"] for row in due] == ["evidence-rich"]
    assert q.snapshot()["evidence_parked_count"] == 1


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


def test_reenqueue_cannot_steal_active_worker_lease(tmp_path):
    q = _queue(tmp_path)
    q.enqueue({"prospect_id": "p1", "reason": "no_contact_evidence",
               "business_name": "Real Buyer", "website": "https://buyer.example"})
    first = q.claim_due(limit=1, worker_id="worker-a", lease_seconds=420)
    assert first[0]["status"] == "running"
    assert q.enqueue({"prospect_id": "p1", "reason": "no_contact_evidence"})
    import json
    row = json.loads((tmp_path / "deferred.json").read_text())["p1"]
    assert row["status"] == "running"
    assert row["lease_owner"] == "worker-a"
    assert row["lease_expires_at"] == first[0]["lease_expires_at"]
    assert row["business_name"] == "Real Buyer"
    assert row["website"] == "https://buyer.example"
    assert q.claim_due(limit=1, worker_id="worker-b") == []


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


def test_new_first_party_person_evidence_wakes_hot_cooldown_once(tmp_path):
    import json
    q = _queue(tmp_path)
    original = {
        "prospect_id": "hot", "reason": "no_bound_contact",
        "website": "https://buyer.example/",
        "target_people": [{"name": "Jane Buyer", "title": "Founder",
                           "source": "first_party_site_current",
                           "evidence_url": "https://buyer.example/team/"}],
    }
    assert q.enqueue(original)
    file = tmp_path / "deferred.json"
    data = json.loads(file.read_text())
    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    data["hot"]["attempts"] = 32
    data["hot"]["status"] = "deferred"
    data["hot"]["next_retry_at"] = future
    file.write_text(json.dumps(data))

    fresh = dict(original, target_people=[{
        "name": "John Buyer", "title": "CEO",
        "source": "first_party_site_current",
        "evidence_url": "https://buyer.example/leadership/",
    }])
    assert q.enqueue(fresh)
    after = json.loads(file.read_text())["hot"]
    assert after["next_retry_at"] <= datetime.now(timezone.utc).isoformat()
    assert after["last_evidence_acceleration_at"]
    assert q.snapshot()["evidence_wakes_last_24h"] == 1
    assert q.due(limit=1)[0]["prospect_id"] == "hot"

    # Repeated identical data cannot bypass the governed cooldown.
    q.defer_again("hot", reason="no_bound_contact", attempts=33, retry_minutes=43200)
    first_backoff = json.loads(file.read_text())["hot"]["next_retry_at"]
    assert q.enqueue(fresh)
    assert json.loads(file.read_text())["hot"]["next_retry_at"] == first_backoff


def test_off_site_or_unverified_contact_cannot_wake_hot_backoff(tmp_path):
    import json
    q = _queue(tmp_path)
    base = {"prospect_id": "hot", "reason": "no_bound_contact",
            "website": "https://buyer.example/",
            "target_people": [{"name": "Jane Buyer", "title": "Founder"}]}
    q.enqueue(base)
    file = tmp_path / "deferred.json"
    data = json.loads(file.read_text())
    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    data["hot"]["next_retry_at"] = future
    file.write_text(json.dumps(data))
    untrusted = dict(base, target_people=[{
        "name": "Other Buyer", "title": "CEO",
        "evidence_url": "https://unrelated.test/team/"}])
    assert q.enqueue(untrusted)
    after = json.loads(file.read_text())["hot"]
    assert after["next_retry_at"] == future
    assert not after.get("last_evidence_acceleration_at")


def test_new_verified_route_during_active_lease_wakes_after_worker_finishes(tmp_path):
    import json
    q = _queue(tmp_path)
    base = {
        "prospect_id": "busy",
        "reason": "no_bound_contact",
        "website": "https://buyer.example/",
        "target_people": [{"name": "Jane Buyer", "title": "Founder"}],
    }
    q.enqueue(base)
    first = q.claim_due(limit=1, worker_id="first", lease_seconds=420)
    assert first[0]["status"] == "running"
    updated = dict(base, company_contact_routes=[{
        "channel": "email", "value": "sales@buyer.example", "verified": True,
    }])
    assert q.enqueue(updated)
    row = json.loads((tmp_path / "deferred.json").read_text())["busy"]
    assert row["status"] == "running"
    assert row["lease_owner"] == "first"
    assert row["pending_evidence_wake_at"]
    assert q.snapshot()["evidence_refresh_pending_count"] == 1
    assert q.claim_due(limit=1, worker_id="second") == []
    q.defer_again("busy", reason="no_bound_contact", attempts=1, retry_minutes=43200)
    after = json.loads((tmp_path / "deferred.json").read_text())["busy"]
    assert after["pending_evidence_wake_at"] is None
    assert after["status"] == "deferred"
    assert q.due(limit=1)[0]["prospect_id"] == "busy"


def test_new_evidence_wake_is_rate_limited_against_repeated_refreshes(tmp_path):
    import json
    q = _queue(tmp_path)
    base = {
        "prospect_id": "hot", "reason": "no_bound_contact",
        "website": "https://buyer.example/",
        "target_people": [{"name": "Jane Buyer", "title": "Founder"}],
    }
    q.enqueue(base)
    for index in (1, 2):
        q.defer_again("hot", reason="no_bound_contact",
                      attempts=index + 8, retry_minutes=43200)
        new = dict(base, target_people=[{
            "name": ("John Buyer" if index == 1 else "Alex Buyer"),
            "title": "CEO",
            "evidence_url": f"https://buyer.example/team/{index}",
        }])
        q.enqueue(new)
        row = json.loads((tmp_path / "deferred.json").read_text())["hot"]
        retry_at = datetime.fromisoformat(row["next_retry_at"])
        if index == 1:
            first_wake = row["last_evidence_acceleration_at"]
            assert retry_at <= datetime.now(timezone.utc)
        else:
            assert row["last_evidence_acceleration_at"] == first_wake
            delay = retry_at - datetime.now(timezone.utc)
            assert timedelta(hours=5) < delay <= timedelta(hours=6)


def test_new_hot_evidence_merges_without_dropping_existing_people(tmp_path):
    import json
    q = _queue(tmp_path)
    old = {
        "prospect_id": "merged", "reason": "no_bound_contact",
        "website": "https://buyer.example/",
        "target_people": [{
            "name": "Jane Buyer", "title": "Founder",
            "source": "first_party_site",
            "evidence_url": "https://buyer.example/about/",
        }],
        "company_contact_routes": [{
            "channel": "email", "value": "info@buyer.example",
            "verified": True,
        }],
    }
    assert q.enqueue(old)
    newer = {
        **old,
        "target_people": [{
            "name": "John Buyer", "title": "CEO",
            "source": "first_party_site",
            "evidence_url": "https://buyer.example/leadership/",
        }],
        "company_contact_routes": [{
            "channel": "email", "value": "partners@buyer.example",
            "verified": True,
        }],
    }
    assert q.enqueue(newer)
    row = json.loads((tmp_path / "deferred.json").read_text())["merged"]
    assert {p["name"] for p in row["target_people"]} == {"Jane Buyer", "John Buyer"}
    assert {r["value"] for r in row["company_contact_routes"]} == {
        "info@buyer.example", "partners@buyer.example"
    }
    assert q.enqueue(newer)
    row = json.loads((tmp_path / "deferred.json").read_text())["merged"]
    assert len(row["target_people"]) == 2
    assert len(row["company_contact_routes"]) == 2


def test_weak_repeat_never_overwrites_strong_first_party_person(tmp_path):
    import json
    q = _queue(tmp_path)
    q.enqueue({
        "prospect_id": "p1", "reason": "no_bound_contact",
        "website": "https://buyer.example/",
        "target_people": [{
            "name": "Jane Buyer", "title": "Founder",
            "source": "first_party_site",
            "evidence_url": "https://buyer.example/team/",
        }],
    })
    q.enqueue({
        "prospect_id": "p1", "reason": "no_bound_contact",
        "website": "https://buyer.example/",
        "target_people": [{
            "name": "Jane Buyer", "title": "Founder",
            "source": "search_summary", "evidence_url": "https://unrelated.test/",
        }],
    })
    row = json.loads((tmp_path / "deferred.json").read_text())["p1"]
    assert len(row["target_people"]) == 1
    assert row["target_people"][0]["evidence_url"] == "https://buyer.example/team/"


def test_mismatched_company_website_cannot_replace_existing_identity(tmp_path):
    import json
    q = _queue(tmp_path)
    q.enqueue({
        "prospect_id": "p1", "reason": "no_bound_contact",
        "website": "https://buyer.example/",
        "target_people": [{
            "name": "Jane Buyer", "title": "Founder",
            "evidence_url": "https://buyer.example/team/",
        }],
    })
    assert q.enqueue({
        "prospect_id": "p1", "reason": "no_bound_contact",
        "website": "https://unrelated.test/",
        "target_people": [{
            "name": "Other Buyer", "title": "CEO",
            "evidence_url": "https://unrelated.test/leadership/",
        }],
    }) is False
    row = json.loads((tmp_path / "deferred.json").read_text())["p1"]
    assert row["website"] == "https://buyer.example/"
    assert [p["name"] for p in row["target_people"]] == ["Jane Buyer"]


def test_resolved_review_is_not_reopened_by_identical_recurring_sync(tmp_path):
    import json
    q = _queue(tmp_path)
    original = {
        "prospect_id": "p1", "reason": "no_bound_contact",
        "website": "https://buyer.example/",
        "target_people": [{
            "name": "Jane Buyer", "title": "Founder",
            "evidence_url": "https://buyer.example/team/",
        }],
    }
    q.enqueue(original)
    q.resolve("p1", outcome="buyer_review_proposed")
    assert q.enqueue(original) is False
    row = json.loads((tmp_path / "deferred.json").read_text())["p1"]
    assert row["status"] == "resolved"
    assert q.due(limit=1) == []


def test_resolved_review_can_reopen_for_new_same_company_evidence(tmp_path):
    import json
    q = _queue(tmp_path)
    original = {
        "prospect_id": "p1", "reason": "no_bound_contact",
        "website": "https://buyer.example/",
        "target_people": [{
            "name": "Jane Buyer", "title": "Founder",
            "evidence_url": "https://buyer.example/team/",
        }],
    }
    q.enqueue(original)
    q.resolve("p1", outcome="buyer_review_proposed")
    changed = dict(original, target_people=[{
        "name": "John Buyer", "title": "CEO",
        "evidence_url": "https://buyer.example/leadership/",
    }])
    assert q.enqueue(changed) is True
    row = json.loads((tmp_path / "deferred.json").read_text())["p1"]
    assert row["status"] == "pending"
    assert {p["name"] for p in row["target_people"]} == {
        "Jane Buyer", "John Buyer",
    }
    assert q.due(limit=1)[0]["prospect_id"] == "p1"


def test_expired_lease_is_counted_as_due(tmp_path):
    q = _queue(tmp_path)
    q.enqueue({"prospect_id": "p1", "reason": "no_contact_evidence"})
    current = datetime.now(timezone.utc)
    q.claim_due(limit=1, worker_id="worker-a", lease_seconds=60, now=current)
    assert q.snapshot()["due_now"] == 0
    import json
    p = tmp_path / "deferred.json"
    data = json.loads(p.read_text())
    data["p1"]["lease_expires_at"] = (current - timedelta(minutes=1)).isoformat()
    p.write_text(json.dumps(data))
    assert q.snapshot()["due_now"] == 1


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


def test_deferred_rows_expose_next_recovery_prerequisite(tmp_path):
    q = _queue(tmp_path)
    q.enqueue({
        "prospect_id": "p-site",
        "reason": "site_unavailable",
        "priority_score": 90,
    })
    import json
    row = json.loads((tmp_path / "deferred.json").read_text())["p-site"]
    assert row["next_prerequisite"] == "verified_company_website_available"
    snap = q.snapshot()
    assert (
        snap["recovery_prerequisite_counts"]["verified_company_website_available"]
        == 1
    )


def test_defer_again_updates_recovery_prerequisite(tmp_path):
    q = _queue(tmp_path)
    q.enqueue({
        "prospect_id": "p1",
        "reason": "no_decision_maker",
    })
    q.defer_again(
        "p1",
        reason="site_timeout",
        attempts=3,
        retry_minutes=60,
    )
    import json
    row = json.loads((tmp_path / "deferred.json").read_text())["p1"]
    assert row["next_prerequisite"] == "first_party_site_reachable"

def test_retry_exhaustion_parks_both_cold_and_hot_until_evidence(tmp_path):
    import json

    q = _queue(tmp_path)
    q.enqueue({
        "prospect_id": "cold", "reason": "site_timeout",
        "website": "https://cold.example",
    })
    q.enqueue({
        "prospect_id": "hot", "reason": "no_bound_contact",
        "website": "https://hot.example",
        "target_people": [{"name": "Jane Buyer", "title": "Founder"}],
    })
    path = tmp_path / "deferred.json"
    data = json.loads(path.read_text())
    data["cold"]["attempts"] = 8
    data["hot"]["attempts"] = 32
    path.write_text(json.dumps(data))
    assert q.due(limit=5) == []
    assert q.claim_due(limit=5, worker_id="no-repeat") == []
    snap = q.snapshot()
    assert snap["evidence_parked_count"] == 2
    assert snap["due_now"] == 0
    # Nothing is discarded, silently approved, or marked resolved.
    data = json.loads(path.read_text())
    assert {data[k]["status"] for k in ("cold", "hot")} == {"pending"}

    # Recurring discovery of identical or untrusted data does not reawaken.
    assert q.enqueue({"prospect_id": "cold", "reason": "site_timeout",
                      "website": "https://cold.example"})
    assert q.enqueue({"prospect_id": "hot", "reason": "no_bound_contact",
                      "website": "https://hot.example",
                      "target_people": [{"name": "Jane Buyer",
                                         "title": "Founder",
                                         "evidence_url": "https://elsewhere.example/team"}]})
    assert q.snapshot()["evidence_parked_count"] == 2


def test_distinct_same_host_person_evidence_reopens_exhausted_hot(tmp_path):
    import json

    q = _queue(tmp_path)
    original = {
        "prospect_id": "hot", "reason": "no_bound_contact",
        "website": "https://company.example",
        "target_people": [{"name": "Jane Buyer", "title": "Founder",
                           "evidence_url": "https://company.example/about"}],
    }
    q.enqueue(original)
    path = tmp_path / "deferred.json"
    data = json.loads(path.read_text())
    data["hot"]["attempts"] = 50
    path.write_text(json.dumps(data))
    assert q.due() == []

    changed = {
        **original,
        "target_people": [{"name": "John Buyer", "title": "CEO",
                           "evidence_url": "https://company.example/leadership"}],
    }
    assert q.enqueue(changed)
    assert [x["prospect_id"] for x in q.due()] == ["hot"]
    assert json.loads(path.read_text())["hot"]["attempts"] == 0
    assert q.snapshot()["evidence_parked_count"] == 0

    # Exhaustion after that bounded opportunity is not cleared by repeats.
    q.defer_again("hot", reason="no_bound_contact",
                  attempts=40, retry_minutes=5)
    assert q.enqueue(changed)
    assert json.loads(path.read_text())["hot"]["attempts"] == 40
    assert q.due(now=datetime.now(timezone.utc) + timedelta(minutes=7)) == []


def test_new_verified_route_during_exhausted_running_lease_recovers(tmp_path):
    import json

    q = _queue(tmp_path)
    original = {
        "prospect_id": "leased", "reason": "no_bound_contact",
        "website": "https://company.example",
        "target_people": [{"name": "Jane Buyer", "title": "Founder"}],
    }
    q.enqueue(original)
    q.claim_due(limit=1, worker_id="existing")
    path = tmp_path / "deferred.json"
    data = json.loads(path.read_text())
    data["leased"]["attempts"] = 35
    path.write_text(json.dumps(data))

    assert q.enqueue({**original, "company_contact_routes": [
        {"channel": "email", "value": "team@company.example",
         "verified": True},
    ]})
    during = json.loads(path.read_text())["leased"]
    assert during["status"] == "running"
    assert during["pending_evidence_wake_at"]
    assert q.claim_due(limit=1, worker_id="other") == []

    q.defer_again("leased", reason="no_bound_contact",
                  attempts=36, retry_minutes=1440)
    after = json.loads(path.read_text())["leased"]
    assert after["attempts"] == 0
    assert q.due(limit=1)[0]["prospect_id"] == "leased"
    assert q.snapshot()["evidence_refresh_pending_count"] == 0
