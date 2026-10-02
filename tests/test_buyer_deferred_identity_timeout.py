import subprocess

import scripts.run_buyer_deferred_enrichment as worker


def test_identity_recovery_timeout_is_bounded_defer(monkeypatch):
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["identity"], timeout=45)

    monkeypatch.setattr(worker.subprocess, "run", timeout)
    result = worker.recover_identity_isolated(
        business_name="Acme Roofing",
        website="https://acme.example",
        metro="Dallas, TX",
        hard_timeout_seconds=45,
    )
    assert result["decision"] == "deferred"
    assert result["identity"] is None
    assert result["reason"] == "identity_recovery_timeout"


def test_identity_recovery_accepts_valid_child_json(monkeypatch):
    def success(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            ["identity"],
            0,
            stdout='{"decision":"resolved","identity":{"name":"Alex Smith"}}',
            stderr="",
        )

    monkeypatch.setattr(worker.subprocess, "run", success)
    result = worker.recover_identity_isolated(
        business_name="Acme Roofing",
        website="https://acme.example",
        metro="Dallas, TX",
    )
    assert result["decision"] == "resolved"
    assert result["identity"]["name"] == "Alex Smith"


def test_batch_prospect_loader_uses_three_bounded_queries(monkeypatch):
    calls = []

    def fake_get(path, params):
        calls.append((path, dict(params)))
        if path == "/rest/v1/prospects":
            return [{
                "id": "p1",
                "business_name": "Acme Roofing",
                "website": None,
            }]
        if path == "/rest/v1/prospect_entity_links":
            return [{
                "prospect_id": "p1",
                "entity_id": "e1",
                "active": True,
                "match_score": 1.0,
            }]
        if path == "/rest/v1/prospect_acquisitions":
            return []
        raise AssertionError(path)

    monkeypatch.setattr(worker, "_get", fake_get)
    rows = worker._prospect_rows(["p1"])
    assert rows["p1"]["entity_id"] == "e1"
    assert len(calls) == 3
    assert calls[0][1]["id"] == "in.(p1)"
    assert "address" in calls[0][1]["select"]
    assert calls[1][1]["prospect_id"] == "in.(p1)"
    assert calls[2][1]["prospect_id"] == "in.(p1)"


def test_targeted_probe_budget_exhaustion_is_durably_redeferred(monkeypatch):
    class FakeQueue:
        instance = None
        def __init__(self):
            self.deferred = []
            FakeQueue.instance = self
        def claim_due(self, *, limit, worker_id, lease_seconds):
            return [{
                "prospect_id": "p1",
                "attempts": 0,
                "target_people": [{"name":"Jane Smith","title":"CEO"}],
                "reason": "target_contact_not_verified",
            }]
        def defer_again(self, prospect_id, *, reason, attempts, retry_minutes):
            self.deferred.append((prospect_id, reason, attempts, retry_minutes))
        def resolve(self, *args, **kwargs):
            raise AssertionError("must not resolve")
        def mark_call_ready(self, *args, **kwargs):
            return False
        def snapshot(self):
            return {}

    monkeypatch.setattr(worker, "BuyerDeferredEnrichmentQueue", FakeQueue)
    monkeypatch.setattr(worker, "_prospect_rows", lambda ids: {
        "p1": {
            "id":"p1", "business_name":"Acme Law", "niche":"law",
            "metro":"Dallas, TX", "website":"https://acme.test",
            "phone":"", "buy_signal_score":90, "status":"new",
            "notes":"", "contact_name":"", "contact_title":"",
            "contact_source":"", "contacted_status":"", "created_at":"",
        }
    })
    monkeypatch.setattr(
        worker, "_targeted_enterprise_probe",
        lambda *args, **kwargs: (None, 1),
    )
    monkeypatch.setattr(worker, "materialize_call_plans", lambda: {"count":0})

    result = worker.run_cycle(limit=1)

    assert result["processed"] == 1
    assert result["deferred_again"] == 1
    assert result["results"][0]["outcome"] == "deferred_by_network_budget"
    assert FakeQueue.instance.deferred == [
        ("p1", "network_probe_budget_exhausted", 1, 10)
    ]


def test_high_priority_retry_backoff_is_fast_but_bounded():
    item = {"priority_score": 100}
    assert worker._retry_minutes(item, 1) == 10
    assert worker._retry_minutes(item, 2) == 20
    assert worker._retry_minutes(item, 3) == 40
    assert worker._retry_minutes(item, 4) == 60
    assert worker._retry_minutes(item, 8) == 180


def test_normal_retry_backoff_preserves_existing_cadence():
    item = {"priority_score": 50}
    assert worker._retry_minutes(item, 1) == 30
    assert worker._retry_minutes(item, 2) == 60
    assert worker._retry_minutes(item, 3) == 120
    assert worker._retry_minutes(item, 4) == 240
    assert worker._retry_minutes(item, 8) == 180


def test_slow_recovery_stages_are_bounded_per_lane(monkeypatch):
    class FakeQueue:
        def __init__(self):
            self.deferred = []
        def claim_due(self, *, limit, worker_id, lease_seconds):
            return [
                {
                    "prospect_id": f"p{i}",
                    "attempts": 0,
                    "reason": "no_contact_evidence",
                }
                for i in range(1, 4)
            ]
        def defer_again(self, prospect_id, *, reason, attempts, retry_minutes):
            self.deferred.append(prospect_id)
        def resolve(self, *args, **kwargs):
            return None
        def mark_call_ready(self, *args, **kwargs):
            return False
        def snapshot(self):
            return {}

    rows = {
        f"p{i}": {
            "id": f"p{i}",
            "business_name": f"Buyer {i}",
            "niche": "roofing",
            "metro": "Dallas, TX",
            "address": "",
            "website": f"https://buyer{i}.example",
            "phone": "",
            "buy_signal_score": 90,
            "status": "new",
            "notes": "",
            "contact_name": "",
            "contact_title": "",
            "contact_source": "",
            "contacted_status": "",
            "created_at": "",
        }
        for i in range(1, 4)
    }
    identity_calls = []
    public_calls = []

    monkeypatch.setattr(worker, "BuyerDeferredEnrichmentQueue", FakeQueue)
    monkeypatch.setattr(worker, "_prospect_rows", lambda ids: rows)
    monkeypatch.setattr(
        worker,
        "run_buyer_probe_isolated",
        lambda *args, **kwargs: {
            "review_ready": False,
            "outreach_ready": False,
            "decision_maker": None,
            "contacts": [],
        },
    )
    monkeypatch.setattr(
        worker,
        "recover_identity_isolated",
        lambda **kwargs: (
            identity_calls.append(kwargs) or
            {"decision": "deferred", "identity": None}
        ),
    )
    monkeypatch.setattr(
        worker,
        "_direct_public_contact_recovery",
        lambda candidate, result: (
            public_calls.append(candidate.prospect_id) or
            {**result, "public_person_contact_evidence": {"evidence": []}}
        ),
    )
    monkeypatch.setattr(worker, "_persist_recovered_identity", lambda *a, **k: False)
    monkeypatch.setattr(worker, "_propose_review", lambda *a, **k: None)
    monkeypatch.setattr(worker, "rejection_reason", lambda result: "no_contact_evidence")
    monkeypatch.setattr(worker, "materialize_call_plans", lambda: {"count": 0})

    result = worker.run_cycle(limit=3)

    assert result["processed"] == 3
    assert result["identity_recovery_attempts"] == 1
    assert result["identity_recovery_budget"] == 1
    assert result["public_contact_recovery_attempts"] == 1
    assert result["public_contact_recovery_budget"] == 1
    assert len(identity_calls) == 1
    assert len(public_calls) == 1


def test_canonical_target_hint_requires_real_decision_identity():
    assert worker._canonical_target_hint({
        "contact_name": "Jane Smith",
        "contact_title": "Founder",
        "contact_source": "official_site_current",
    }) == {
        "name": "Jane Smith",
        "title": "Founder",
        "source": "official_site_current",
        "identity_hint_only": True,
    }
    assert worker._canonical_target_hint({
        "contact_name": "Case Studies",
        "contact_title": "Founder",
    }) is None
    assert worker._canonical_target_hint({
        "contact_name": "Jane Smith",
        "contact_title": "Marketing Assistant",
    }) is None


def test_run_cycle_reuses_canonical_identity_as_target_hint(monkeypatch):
    captured = {}

    class FakeQueue:
        def claim_due(self, **_kwargs):
            return [{"prospect_id":"p1","attempts":0,"reason":"no_decision_maker"}]
        def defer_again(self, *args, **kwargs):
            pass
        def resolve(self, *args, **kwargs):
            pass
        def mark_call_ready(self, *args, **kwargs):
            return False
        def snapshot(self):
            return {}

    monkeypatch.setattr(worker, "BuyerDeferredEnrichmentQueue", FakeQueue)
    monkeypatch.setattr(worker, "_prospect_rows", lambda _ids: {"p1": {
        "id":"p1","business_name":"Acme Roofing","niche":"roofing",
        "metro":"Dallas, TX","address":"","phone":"","website":"https://acme.test",
        "buy_signal_score":90,"status":"new","notes":"",
        "contact_name":"Jane Smith","contact_title":"Founder",
        "contact_source":"official_site_current","contacted_status":"","created_at":"",
    }})
    def targeted(_candidate, item, **_kwargs):
        captured["people"] = item["target_people"]
        return ({"rejection_reason":"target_contact_not_verified"}, 1)
    monkeypatch.setattr(worker, "_targeted_enterprise_probe", targeted)
    monkeypatch.setattr(worker, "_direct_public_contact_recovery", lambda _c, r: r)
    monkeypatch.setattr(worker, "_persist_recovered_identity", lambda *a, **k: False)
    monkeypatch.setattr(worker, "rejection_reason", lambda _r: "target_contact_not_verified")
    monkeypatch.setattr(worker, "materialize_call_plans", lambda: {"count":0})

    result = worker.run_cycle(limit=1)
    assert captured["people"][0]["name"] == "Jane Smith"
    assert captured["people"][0]["identity_hint_only"] is True
    assert result["canonical_identity_hints_used"] == 1


def test_degraded_identity_search_opens_cycle_breaker(monkeypatch):
    worker.IDENTITY_SEARCH_DEGRADED.clear()

    class FakeQueue:
        def claim_due(self, **_kwargs):
            return [{"prospect_id":"p1","attempts":0,"reason":"no_decision_maker"}]
        def defer_again(self, *args, **kwargs):
            pass
        def resolve(self, *args, **kwargs):
            pass
        def mark_call_ready(self, *args, **kwargs):
            return False
        def snapshot(self):
            return {}

    monkeypatch.setattr(worker, "BuyerDeferredEnrichmentQueue", FakeQueue)
    monkeypatch.setattr(worker, "_prospect_rows", lambda _ids: {"p1": {
        "id":"p1","business_name":"Acme","niche":"roofing","metro":"Dallas, TX",
        "address":"","phone":"","website":"https://acme.test","buy_signal_score":90,
        "status":"new","notes":"","contact_name":"","contact_title":"",
        "contact_source":"","contacted_status":"","created_at":"",
    }})
    monkeypatch.setattr(worker, "run_buyer_probe_isolated", lambda *a, **k: {})
    monkeypatch.setattr(worker, "recover_identity_isolated", lambda **k: {
        "identity": None,
        "serp_degraded": True,
    })
    monkeypatch.setattr(worker, "_direct_public_contact_recovery", lambda _c, r: r)
    monkeypatch.setattr(worker, "_persist_recovered_identity", lambda *a, **k: False)
    monkeypatch.setattr(worker, "rejection_reason", lambda _r: "no_decision_maker")
    monkeypatch.setattr(worker, "materialize_call_plans", lambda: {"count":0})

    result = worker.run_cycle(limit=1)
    assert result["identity_search_degraded"] is True
    assert worker.IDENTITY_SEARCH_DEGRADED.is_set()


def test_open_cycle_breaker_skips_identity_recovery(monkeypatch):
    worker.IDENTITY_SEARCH_DEGRADED.set()
    called = {"recover": 0}

    class FakeQueue:
        def claim_due(self, **_kwargs):
            return [{"prospect_id":"p1","attempts":0,"reason":"no_decision_maker"}]
        def defer_again(self, *args, **kwargs):
            pass
        def resolve(self, *args, **kwargs):
            pass
        def mark_call_ready(self, *args, **kwargs):
            return False
        def snapshot(self):
            return {}

    monkeypatch.setattr(worker, "BuyerDeferredEnrichmentQueue", FakeQueue)
    monkeypatch.setattr(worker, "_prospect_rows", lambda _ids: {"p1": {
        "id":"p1","business_name":"Acme","niche":"roofing","metro":"Dallas, TX",
        "address":"","phone":"","website":"https://acme.test","buy_signal_score":90,
        "status":"new","notes":"","contact_name":"","contact_title":"",
        "contact_source":"","contacted_status":"","created_at":"",
    }})
    monkeypatch.setattr(worker, "run_buyer_probe_isolated", lambda *a, **k: {})
    def should_not_run(**kwargs):
        called["recover"] += 1
        return {}
    monkeypatch.setattr(worker, "recover_identity_isolated", should_not_run)
    monkeypatch.setattr(worker, "_direct_public_contact_recovery", lambda _c, r: r)
    monkeypatch.setattr(worker, "_persist_recovered_identity", lambda *a, **k: False)
    monkeypatch.setattr(worker, "rejection_reason", lambda _r: "no_decision_maker")
    monkeypatch.setattr(worker, "materialize_call_plans", lambda: {"count":0})

    result = worker.run_cycle(limit=1)
    assert called["recover"] == 0
    assert result["identity_recovery_attempts"] == 0
    worker.IDENTITY_SEARCH_DEGRADED.clear()


def test_saturated_network_retry_backoff_moves_to_long_cooldown():
    item = {"priority_score": 100, "reason": "site_timeout"}
    assert worker._retry_minutes(item, 4) == 360
    assert worker._retry_minutes(item, 8) == 1440
    assert worker._retry_minutes(item, 16) == 10080
    assert worker._retry_minutes(item, 32) == 43200
