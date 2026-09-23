from empire_os.buyer_review_materializer import (
    fetch_candidate_rows,
    run_buyer_probe_isolated,
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
    assert result.outcomes == ({
        "prospect_id": PROSPECT_ID,
        "business_name": "Acme Roofing",
        "status": "proposed",
        "reason": None,
        "review_ready": True,
        "outreach_ready": True,
        "decision_name": "Jane Smith",
        "decision_title": "CEO",
        "identity_recovery": None,
        "preferred_email": "jane@acmeroofing.test",
        "contact_route": None,
    },)

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


def test_software_buyer_candidate_can_enter_review_pipeline():
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
    assert result.proposed == 1
    assert result.skipped_ineligible == 0
    assert len(called) == 1


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


def test_isolated_probe_timeout_returns_bounded_rejection(monkeypatch):
    import subprocess

    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["probe"], timeout=12)

    monkeypatch.setattr(
        "empire_os.buyer_review_materializer.subprocess.run",
        timeout,
    )
    result = run_buyer_probe_isolated(
        {
            "id": PROSPECT_ID,
            "business_name": "Acme Roofing",
        },
        hard_timeout_seconds=12,
    )
    assert result["rejection_reason"] == "site_timeout"
    assert result["review_ready"] is False
    assert result["outreach_ready"] is False
    assert result["write_authorized"] is False


def test_explicit_probe_rejection_reason_is_preserved():
    request = FakeRequest()

    def timed_out_probe(_row):
        return {
            "site_ok": False,
            "review_ready": False,
            "outreach_ready": False,
            "rejection_reason": "site_timeout",
        }

    result = run_buyer_review_materializer(
        request,
        probe=timed_out_probe,
    )
    assert result.proposed == 0
    assert dict(result.rejection_counts)["site_timeout"] == 1



def test_candidate_fetch_is_cross_pool_and_uses_score_only_for_ordering():
    paths = []

    class InspectRequest(FakeRequest):
        def __call__(self, method, path, payload=None, **kwargs):
            if method == "GET":
                paths.append(path)
            return super().__call__(
                method,
                path,
                payload=payload,
                **kwargs,
            )

    rows, skipped = fetch_candidate_rows(
        InspectRequest(),
        scan_limit=10,
        scan_offset=0,
    )

    assert len(rows) == 1
    assert skipped == 0
    prospect_path = next(
        path for path in paths
        if path.startswith("/rest/v1/prospects?")
    )
    assert "buy_signal_score=gte.70" not in prospect_path
    assert "website=not.is.null" in prospect_path
    assert "niche.ilike." not in prospect_path
    assert "buy_signal_score.desc.nullslast" in prospect_path


def test_cross_pool_review_still_requires_company_score_floor():
    weak = prospect()
    weak["website"] = "https://local.example"
    weak["phone"] = ""
    weak["business_name"] = "Local Shop"
    weak["niche"] = "retail"
    weak["buy_signal_score"] = None

    class WeakRequest(FakeRequest):
        def __call__(self, method, path, payload=None, **kwargs):
            if method == "GET" and path.startswith("/rest/v1/prospects?"):
                return [weak]
            if method == "GET" and path.startswith(
                "/rest/v1/prospect_entity_links?"
            ):
                return []
            return super().__call__(
                method,
                path,
                payload=payload,
                **kwargs,
            )

    called = []

    def probe(row):
        called.append(row)
        return strong_probe(row)

    result = run_buyer_review_materializer(
        WeakRequest(),
        probe=probe,
    )

    assert result.proposed == 0
    assert result.skipped_ineligible == 1
    assert called == []


def test_targeted_fetch_scopes_prospect_ids():
    paths = []

    class InspectRequest(FakeRequest):
        def __call__(self, method, path, payload=None, **kwargs):
            if method == "GET":
                paths.append(path)
            return super().__call__(
                method,
                path,
                payload=payload,
                **kwargs,
            )

    rows, skipped = fetch_candidate_rows(
        InspectRequest(),
        scan_limit=10,
        prospect_ids=[PROSPECT_ID],
    )

    assert len(rows) == 1
    assert skipped == 0
    prospect_path = next(
        path for path in paths
        if path.startswith("/rest/v1/prospects?")
    )
    assert "id=in." in prospect_path
    assert PROSPECT_ID in prospect_path


def test_targeted_materializer_can_use_bounded_source_floor():
    request = FakeRequest()

    class Score69Request(FakeRequest):
        def __call__(self, method, path, payload=None, **kwargs):
            if method == "GET" and path.startswith("/rest/v1/prospects?"):
                row = prospect()
                row["buy_signal_score"] = 95
                row["contact_name"] = None
                row["contact_title"] = None
                return [row]
            if method == "GET" and path.startswith(
                "/rest/v1/prospect_entity_links?"
            ):
                return []
            return super().__call__(
                method,
                path,
                payload=payload,
                **kwargs,
            )

    request = Score69Request()
    result = run_buyer_review_materializer(
        request,
        probe=strong_probe,
        prospect_ids=[PROSPECT_ID],
        min_company_score=65.0,
        proposal_limit=1,
    )

    assert result.eligible == 1
    assert result.proposed == 1


def test_isolated_probe_accepts_bounded_override_options(monkeypatch):
    import json
    from types import SimpleNamespace

    seen = {}

    def fake_run(*args, **kwargs):
        seen["payload"] = json.loads(kwargs["input"])
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "review_ready": False,
                "outreach_ready": False,
                "rejection_reason": "no_decision_maker",
            }),
            stderr="",
        )

    monkeypatch.setattr(
        "empire_os.buyer_review_materializer.subprocess.run",
        fake_run,
    )

    run_buyer_probe_isolated(
        {
            "id": PROSPECT_ID,
            "business_name": "Acme Roofing",
        },
        hard_timeout_seconds=55,
        probe_options={
            "max_pages": 12,
            "request_timeout": 5.0,
            "time_budget_seconds": 35.0,
        },
    )

    assert seen["payload"]["_probe_options"] == {
        "max_pages": 12,
        "request_timeout": 5.0,
        "time_budget_seconds": 35.0,
    }


def test_company_routed_review_evidence_is_explicit():
    request = FakeRequest()

    def company_probe(row):
        assert row["id"] == PROSPECT_ID
        return {
            "review_ready": True,
            "outreach_ready": True,
            "preferred_email": "info@acmeroofing.test",
            "contact_route": "company_routed",
            "person_bound": False,
            "routing_name": "Jane Smith",
            "routing_title": "CEO",
            "decision_maker": {
                "name": "Jane Smith",
                "title": "CEO",
                "decision_score": 1.0,
                "decision_role": "economic_buyer",
                "source": "empire_first_party_people_probe",
            },
            "verified_contacts": [{
                "email": "info@acmeroofing.test",
                "is_valid": False,
                "confidence": 0.0,
                "is_role_address": True,
                "is_disposable": False,
                "has_mx": False,
                "smtp_accepts": False,
                "source": "site_observed",
                "bound_to_decision_maker": False,
            }],
        }

    result = run_buyer_review_materializer(
        request,
        probe=company_probe,
        proposal_limit=1,
    )

    assert result.proposed == 1
    payload = request.posts[0][1]
    evidence = payload["p_evidence"]
    assert payload["p_contact_email"] == "info@acmeroofing.test"
    assert evidence["contact_route"] == "company_routed"
    assert evidence["person_bound"] is False
    assert evidence["routing_name"] == "Jane Smith"
    assert evidence["routing_title"] == "CEO"
    assert evidence["outreach_ready"] is True
