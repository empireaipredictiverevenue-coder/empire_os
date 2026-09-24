from pathlib import Path

from empire_os.enterprise_contact_intelligence import (
    _refresh_pending_review,
    current_target_people,
    reconcile_verified_enterprise_contact,
    sync_enterprise_activation,
)


class FakeQueue:
    def __init__(self):
        self.enqueued = []
        self.resolved = []

    def enqueue(self, item):
        self.enqueued.append(dict(item))
        return True

    def resolve(self, prospect_id, *, outcome):
        self.resolved.append((prospect_id, outcome))


def _probe(name, title, email):
    return {
        "review_ready": True,
        "outreach_ready": True,
        "person_bound": True,
        "preferred_email": email,
        "contact_route": "person_bound",
        "decision_maker": {
            "name": name,
            "title": title,
            "decision_score": 1.0,
            "decision_role": "economic_buyer",
            "source": "website_structured_data",
        },
        "verified_contacts": [{
            "email": email,
            "is_valid": True,
            "source": "person_structured_data",
        }],
    }


def test_sila_verified_contact_reconciles_to_current_observed_title():
    row = {
        "account_name": "Sila Services",
        "person_contact_verified": True,
        "probe": _probe(
            "Kyle Martin",
            "President",
            "kmartin@sila.com",
        ),
    }
    result = reconcile_verified_enterprise_contact(row)
    assert result is not None
    assert result["name"] == "Kyle Martin"
    assert result["title"] == "Vice President, Corporate Development"
    assert result["role_reconciled"] is True


def test_unobserved_generated_identity_cannot_enter_review_gate():
    row = {
        "account_name": "EQT",
        "person_contact_verified": True,
        "probe": {
            **_probe(
                "Gautam Nadella",
                "Chief Executive Officer",
                "gautam@example.com",
            ),
            "decision_maker": {
                "name": "Gautam Nadella",
                "title": "Chief Executive Officer",
                "decision_score": 1.0,
                "source": "generated_pattern",
            },
            "verified_contacts": [{
                "email": "gautam@example.com",
                "is_valid": True,
                "source": "generated_pattern",
            }],
        },
    }
    assert reconcile_verified_enterprise_contact(row) is None


def test_sync_proposes_verified_redwood_review_with_predictive_offer():
    prospect_id = "00000000-0000-0000-0000-000000000777"
    activation = {
        "targets": [{
            "account_name": "Redwood Services",
            "prospect_id": prospect_id,
            "person_contact_verified": True,
            "probe": _probe(
                "Richard Lewis",
                "Chief Executive Officer",
                "richard@redwoodservices.com",
            ),
        }]
    }
    calls = []

    def request(method, path, payload=None, **kwargs):
        calls.append((method, path, payload))
        if method == "GET":
            return [{
                "id": prospect_id,
                "business_name": "Redwood Services",
                "niche": "predictive_revenue_enterprise",
                "metro": "Memphis, TN",
                "website": "https://redwoodservices.com",
                "buy_signal_score": 50,
                "contact_source": "public_enterprise_target",
            }]
        return {
            "decision": "proposed",
            "review_id": "00000000-0000-0000-0000-000000000888",
            "status": "pending",
            "actual_revenue": False,
        }

    queue = FakeQueue()
    result = sync_enterprise_activation(
        activation,
        request=request,
        queue=queue,
    )
    assert result["proposed_review_count"] == 1
    assert result["targeted_retry_queued_count"] == 0
    post = next(call for call in calls if call[0] == "POST")
    assert (
        post[2]["p_offer_key"]
        == "predictive_revenue_intelligence_os"
    )
    assert post[2]["p_contact_name"] == "Richard Lewis"
    assert post[2]["p_evidence"]["live_outbound_send"] is False
    assert queue.resolved


def test_sync_queues_unresolved_account_with_intended_people():
    activation = {
        "targets": [{
            "account_name": "Neighborly",
            "prospect_id": "00000000-0000-0000-0000-000000000999",
            "person_contact_verified": False,
            "canonical_website": "https://neighborlybrands.com",
            "probe": {
                "rejection_reason": "no_contact_evidence",
            },
            "company_contact_routes": [{
                "channel": "voice",
                "value": "+18552178437",
                "verified": True,
                "person_bound": False,
                "source": "first_party_contact_page",
                "evidence_url": "https://neighborlybrands.com/contact-us/",
            }],
        }]
    }
    queue = FakeQueue()
    result = sync_enterprise_activation(
        activation,
        request=lambda *args, **kwargs: None,
        queue=queue,
    )
    assert result["proposed_review_count"] == 0
    assert result["targeted_retry_queued_count"] == 1
    item = queue.enqueued[0]
    assert item["account_key"] == "neighborly"
    assert item["offer_key"] == "predictive_revenue_autonomous_os"
    assert any(
        person["name"] == "Tanner Stutz"
        for person in item["target_people"]
    )
    assert item["reason"] == "no_contact_evidence"
    assert item["phone"] == "+18552178437"
    assert item["company_contact_routes"][0]["channel"] == "voice"


def test_enterprise_sync_worker_keeps_execution_governed():
    source = Path(
        "scripts/run_enterprise_contact_intelligence.py"
    ).read_text()
    assert '"live_outbound_send": False' in source
    assert '"actual_revenue": False' in source


def test_current_first_party_leadership_precedes_curated_fallback():
    row = {
        "account_name": "Sila Services",
        "probe": {
            "site_people": [{
                "name": "Kyle Martin",
                "title": "Chief Strategy Officer",
                "url": "https://silaservices.com/leadership/",
                "source_kind": "visible_text",
            }]
        },
    }
    people = current_target_people(row)
    kyle = next(
        person for person in people
        if person["name"] == "Kyle Martin"
    )
    assert kyle["title"] == "Chief Strategy Officer"
    assert kyle["source"] == "first_party_site_current"


def test_reconciliation_uses_current_first_party_title_when_available():
    row = {
        "account_name": "Sila Services",
        "person_contact_verified": True,
        "probe": {
            **_probe(
                "Kyle Martin",
                "President",
                "kmartin@sila.com",
            ),
            "site_people": [{
                "name": "Kyle Martin",
                "title": "Vice President, Corporate Development",
                "url": "https://silaservices.com/leadership/",
                "source_kind": "visible_text",
            }],
        },
    }
    result = reconcile_verified_enterprise_contact(row)
    assert result["title"] == "Vice President, Corporate Development"
    assert result["decision_role"] == "functional_buyer"
    assert result["decision_score"] == 0.8
    assert result["leadership_source"] == "first_party_site_current"


def test_enterprise_sync_retries_transient_prospect_fetch_failure(monkeypatch):
    prospect_id = "00000000-0000-0000-0000-000000001111"
    activation = {
        "targets": [{
            "account_name": "Redwood Services",
            "prospect_id": prospect_id,
            "person_contact_verified": True,
            "probe": _probe(
                "Richard Lewis",
                "Chief Executive Officer",
                "richard@redwoodservices.com",
            ),
        }]
    }
    calls = {"get": 0, "post": 0}

    def request(method, path, payload=None, **kwargs):
        if method == "GET":
            calls["get"] += 1
            if calls["get"] == 1:
                raise TimeoutError("transient read timeout")
            return [{
                "id": prospect_id,
                "business_name": "Redwood Services",
                "niche": "predictive_revenue_enterprise",
                "metro": "Memphis, TN",
                "website": "https://redwoodservices.com",
                "buy_signal_score": 50,
                "contact_source": "public_enterprise_target",
            }]
        calls["post"] += 1
        return {
            "decision": "proposed",
            "review_id": "00000000-0000-0000-0000-000000001112",
            "status": "pending",
            "actual_revenue": False,
        }

    monkeypatch.setattr(
        "empire_os.enterprise_contact_intelligence.time.sleep",
        lambda _seconds: None,
    )
    result = sync_enterprise_activation(
        activation,
        request=request,
        queue=FakeQueue(),
    )
    assert result["error_count"] == 0
    assert result["proposed_review_count"] == 1
    assert calls["get"] == 2
    assert calls["post"] == 1


def test_enterprise_sync_retries_idempotent_review_rpc_timeout(monkeypatch):
    prospect_id = "00000000-0000-0000-0000-000000001221"
    activation = {
        "targets": [{
            "account_name": "Redwood Services",
            "prospect_id": prospect_id,
            "person_contact_verified": True,
            "probe": _probe(
                "Richard Lewis",
                "Chief Executive Officer",
                "richard@redwoodservices.com",
            ),
        }]
    }
    calls = {"post": 0}

    review_id = "00000000-0000-0000-0000-000000001222"
    review = {
        "id": review_id,
        "status": "pending",
        "contact_name": "Richard Lewis",
        "contact_title": "Chief Executive Officer",
        "contact_email": "richard@redwoodservices.com",
        "decision_score": 1.0,
        "evidence": {},
    }
    calls["refresh_rpc"] = 0

    def request(method, path, payload=None, **kwargs):
        if method == "GET" and "/prospects?" in path:
            return [{
                "id": prospect_id,
                "business_name": "Redwood Services",
                "niche": "predictive_revenue_enterprise",
                "metro": "Memphis, TN",
                "website": "https://redwoodservices.com",
                "buy_signal_score": 50,
                "contact_source": "public_enterprise_target",
            }]
        if method == "GET" and "/buyer_candidate_reviews?" in path:
            return [dict(review)]
        if method == "POST" and (
            path
            == "/rest/v1/rpc/refresh_pending_buyer_candidate_review"
        ):
            calls["refresh_rpc"] += 1
            review.update({
                "contact_name": payload["p_contact_name"],
                "contact_title": payload["p_contact_title"],
                "contact_email": payload["p_contact_email"],
                "decision_score": payload["p_decision_score"],
                "evidence": dict(payload["p_evidence"]),
            })
            return {
                "decision": "updated",
                "review_id": review_id,
                "status": "pending",
                "actual_revenue": False,
            }

        calls["post"] += 1
        if calls["post"] == 1:
            raise RuntimeError(
                "POST /rest/v1/rpc/propose_buyer_candidate_review "
                "-> HTTP 504: timeout"
            )
        return {
            "decision": "existing",
            "review_id": review_id,
            "status": "pending",
            "actual_revenue": False,
        }

    monkeypatch.setattr(
        "empire_os.enterprise_contact_intelligence.time.sleep",
        lambda _seconds: None,
    )
    result = sync_enterprise_activation(
        activation,
        request=request,
        queue=FakeQueue(),
    )
    assert result["error_count"] == 0
    assert result["proposed_review_count"] == 1
    assert calls["post"] == 2
    assert calls["refresh_rpc"] == 1
    assert review["contact_title"] == "Chief Executive Officer & Founder"


def test_sync_worker_prints_error_details_for_operator_diagnostics():
    source = Path(
        "scripts/run_enterprise_contact_intelligence.py"
    ).read_text()
    assert '"errors": result["errors"]' in source


def test_existing_pending_review_refreshes_current_verified_title():
    review_id = "00000000-0000-0000-0000-000000009001"
    calls = []
    reads = {"count": 0}

    def request(method, path, payload=None, **kwargs):
        calls.append((method, path, payload))
        if method == "GET":
            reads["count"] += 1
            title = (
                "President"
                if reads["count"] == 1
                else "Vice President, Corporate Development"
            )
            return [{
                "id": review_id,
                "status": "pending",
                "contact_name": "Kyle Martin",
                "contact_title": title,
                "contact_email": "kmartin@sila.com",
                "decision_score": 0.8,
                "evidence": {},
            }]
        if method == "POST" and (
            path
            == "/rest/v1/rpc/refresh_pending_buyer_candidate_review"
        ):
            assert payload["p_contact_title"] == (
                "Vice President, Corporate Development"
            )
            assert payload["p_contact_email"] == "kmartin@sila.com"
            assert payload["p_decision_score"] == 0.8
            assert payload["p_evidence"]["source"] == (
                "enterprise_contact_intelligence.v1"
            )
            return {
                "decision": "updated",
                "review_id": review_id,
                "status": "pending",
                "actual_revenue": False,
            }
        raise AssertionError((method, path))

    refreshed = _refresh_pending_review(
        review_id,
        contact_name="Kyle Martin",
        contact_title="Vice President, Corporate Development",
        contact_email="kmartin@sila.com",
        decision_score=0.8,
        evidence={
            "source": "enterprise_contact_intelligence.v1",
            "role_reconciled": True,
        },
        request=request,
    )

    assert refreshed is True
    assert [call[0] for call in calls] == ["GET", "POST", "GET"]


def test_existing_non_pending_review_is_not_rewritten():
    def request(method, path, payload=None, **kwargs):
        assert method == "GET"
        return [{
            "id": "00000000-0000-0000-0000-000000009002",
            "status": "approved",
            "contact_name": "Kyle Martin",
            "contact_title": "President",
            "contact_email": "kmartin@sila.com",
            "decision_score": 1.0,
            "evidence": {},
        }]

    refreshed = _refresh_pending_review(
        "00000000-0000-0000-0000-000000009002",
        contact_name="Kyle Martin",
        contact_title="Vice President, Corporate Development",
        contact_email="kmartin@sila.com",
        decision_score=0.8,
        evidence={"source": "enterprise_contact_intelligence.v1"},
        request=request,
    )
    assert refreshed is False


def test_legacy_untyped_site_person_cannot_beat_curated_first_party_role():
    row = {
        "account_name": "Sila Services",
        "probe": {
            "site_people": [{
                "name": "Kyle Martin",
                "title": "President",
                "url": "https://silaservices.com/leadership/",
            }]
        },
    }

    people = current_target_people(row)
    kyle = next(
        person for person in people if person["name"] == "Kyle Martin"
    )
    assert kyle["title"] == "Vice President, Corporate Development"
    assert kyle["source"] == "curated_public_evidence"


def test_structured_title_cannot_beat_curated_first_party_role():
    row = {
        "account_name": "Redwood Services",
        "probe": {
            "site_people": [{
                "name": "Richard Lewis",
                "title": "Chief Executive Officer",
                "url": "https://redwoodservices.com/team/",
                "source_kind": "structured_data",
            }]
        },
    }

    people = current_target_people(row)
    richard = next(
        person for person in people if person["name"] == "Richard Lewis"
    )
    assert richard["title"] == "Chief Executive Officer & Founder"
    assert richard["source"] == "curated_public_evidence"


def test_visible_leadership_title_can_supersede_curated_role():
    row = {
        "account_name": "Sila Services",
        "probe": {
            "site_people": [{
                "name": "Kyle Martin",
                "title": "Chief Strategy Officer",
                "url": "https://silaservices.com/leadership/",
                "source_kind": "visible_text",
            }]
        },
    }

    people = current_target_people(row)
    kyle = next(
        person for person in people if person["name"] == "Kyle Martin"
    )
    assert kyle["title"] == "Chief Strategy Officer"
    assert kyle["source"] == "first_party_site_current"


def test_pending_review_refresh_uses_governed_rpc_not_direct_patch():
    source = Path(
        "empire_os/enterprise_contact_intelligence.py"
    ).read_text()

    assert (
        "/rest/v1/rpc/refresh_pending_buyer_candidate_review"
        in source
    )
    assert (
        '"PATCH",\n        f"/rest/v1/buyer_candidate_reviews'
        not in source
    )
