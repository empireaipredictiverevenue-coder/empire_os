from pathlib import Path

from empire_os.enterprise_contact_intelligence import (
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
            }],
        },
    }
    result = reconcile_verified_enterprise_contact(row)
    assert result["title"] == "Vice President, Corporate Development"
    assert result["decision_role"] == "functional_buyer"
    assert result["decision_score"] == 0.8
    assert result["leadership_source"] == "first_party_site_current"
