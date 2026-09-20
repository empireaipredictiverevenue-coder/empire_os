from empire_os.buyer_review_materializer import (
    run_buyer_review_materializer,
)


PROSPECT_ID = "00000000-0000-0000-0000-000000000101"
ENTITY_ID = "00000000-0000-0000-0000-000000000201"


def prospect():
    return {
        "id": PROSPECT_ID,
        "business_name": "Acme Roofing",
        "niche": "roofing",
        "metro": "Austin, TX",
        "phone": "+15125550123",
        "website": "https://acmeroofing.test",
        "buy_signal_score": 100,
        "status": "qualified",
        "notes": "",
        "contact_name": None,
        "contact_title": None,
        "contact_source": None,
        "contacted_status": "not_contacted",
        "created_at": "2026-09-20T12:00:00+00:00",
    }


def strong_probe(row):
    assert row["id"] == PROSPECT_ID
    return {
        "review_ready": True,
        "outreach_ready": True,
        "preferred_email": "jane@acmeroofing.test",
        "decision_maker": {
            "name": "Jane Smith",
            "title": "CEO",
            "decision_score": 1.0,
            "decision_role": "economic_buyer",
            "source": "website_structured_data",
        },
        "verified_contacts": [
            {
                "email": "jane@acmeroofing.test",
                "is_valid": True,
                "confidence": 0.95,
                "is_role_address": False,
                "is_disposable": False,
                "has_mx": True,
                "smtp_accepts": False,
                "source": "person_structured_data",
                "bound_to_decision_maker": True,
            }
        ],
    }


class FakeRequest:
    def __init__(self, *, existing=False):
        self.existing = existing
        self.posts = []

    def __call__(self, method, path, payload=None, **_kwargs):
        if method == "POST":
            self.posts.append((path, payload))
            if path.endswith("propose_buyer_candidate_review"):
                return {
                    "decision": "proposed",
                    "review_id": "00000000-0000-0000-0000-000000000301",
                }
            raise AssertionError(path)

        if path.startswith("/rest/v1/prospects?"):
            return [prospect()]
        if path.startswith("/rest/v1/buyer_candidate_reviews?"):
            if self.existing:
                return [{"id": "r1", "status": "approved"}]
            return []
        if path.startswith("/rest/v1/prospect_entity_links?"):
            return [{
                "entity_id": ENTITY_ID,
                "active": True,
                "match_score": 1.0,
            }]
        if path.startswith("/rest/v1/prospect_acquisitions?"):
            return []
        raise AssertionError(path)


def test_materializer_proposes_only_review_ready_outreach_ready_candidate():
    request = FakeRequest()
    result = run_buyer_review_materializer(
        request,
        probe=strong_probe,
        scan_limit=10,
        proposal_limit=5,
    )
    assert result.scanned == 1
    assert result.eligible == 1
    assert result.probed == 1
    assert result.review_ready == 1
    assert result.proposed == 1
    assert result.errors == ()

    path, payload = request.posts[0]
    assert path.endswith("propose_buyer_candidate_review")
    assert payload["p_prospect_id"] == PROSPECT_ID
    assert payload["p_entity_id"] == ENTITY_ID
    assert payload["p_contact_name"] == "Jane Smith"
    assert payload["p_contact_email"] == "jane@acmeroofing.test"
    assert payload["p_company_score"] >= 70
    assert payload["p_decision_score"] >= 0.70
    assert payload["p_evidence"]["contact_source"] == "official_site"
    contact = payload["p_evidence"]["verified_contacts"][0]
    assert contact["source"] == "official_site"
    assert contact["source_detail"] == "person_structured_data"
    assert payload["p_evidence"]["decision_source"] == (
        "website_structured_data"
    )


def test_existing_review_is_not_reproposed_or_probed():
    request = FakeRequest(existing=True)
    called = []

    def probe(_row):
        called.append(True)
        return strong_probe(_row)

    result = run_buyer_review_materializer(
        request,
        probe=probe,
    )
    assert result.scanned == 0
    assert result.skipped_existing == 1
    assert result.proposed == 0
    assert called == []
    assert request.posts == []


def test_weak_decision_evidence_does_not_create_review():
    request = FakeRequest()

    def weak_probe(row):
        value = strong_probe(row)
        value["decision_maker"] = {
            **value["decision_maker"],
            "decision_score": 0.5,
            "title": "Manager",
        }
        return value

    result = run_buyer_review_materializer(
        request,
        probe=weak_probe,
    )
    assert result.eligible == 1
    assert result.probed == 1
    assert result.review_ready == 0
    assert result.proposed == 0
    assert result.skipped_ineligible == 1
    assert request.posts == []


def test_non_managed_service_candidate_is_skipped_before_probe():
    request = FakeRequest()

    def software_prospect():
        value = prospect()
        value["niche"] = "software"
        value["business_name"] = "Acme Software"
        return value

    original = request.__call__

    class SoftwareRequest(FakeRequest):
        def __call__(self, method, path, payload=None, **kwargs):
            if method == "GET" and path.startswith("/rest/v1/prospects?"):
                return [software_prospect()]
            return super().__call__(
                method,
                path,
                payload=payload,
                **kwargs,
            )

    request = SoftwareRequest()
    called = []

    def probe(row):
        called.append(row)
        return strong_probe(row)

    result = run_buyer_review_materializer(
        request,
        probe=probe,
    )
    assert result.proposed == 0
    assert result.skipped_ineligible == 1
    assert called == []


def test_unlinked_but_verified_candidate_can_still_enter_review():
    class UnlinkedRequest(FakeRequest):
        def __call__(self, method, path, payload=None, **kwargs):
            if method == "GET" and path.startswith("/rest/v1/prospect_entity_links?"):
                return []
            return super().__call__(method, path, payload=payload, **kwargs)

    request = UnlinkedRequest()
    result = run_buyer_review_materializer(
        request,
        probe=strong_probe,
        scan_limit=5,
        proposal_limit=1,
    )
    assert result.proposed == 1
    assert request.posts[0][1]["p_entity_id"] is None
