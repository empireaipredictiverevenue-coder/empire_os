import empire_os.source_buyer_review_bridge as bridge
from empire_os.source_buyer_review_bridge import (
    fetch_hot_source_prospect_ids,
)


P1 = "00000000-0000-0000-0000-000000000001"
P2 = "00000000-0000-0000-0000-000000000002"
P3 = "00000000-0000-0000-0000-000000000003"


def test_hot_source_selector_requires_hot_scored_and_verified_website():
    calls = []

    def request(method, path, payload=None, prefer=None):
        calls.append(path)
        if path.startswith("/rest/v1/prospect_acquisitions?"):
            return [
                {"prospect_id": P1},
                {"prospect_id": P2},
                {"prospect_id": P3},
            ]
        if path.startswith("/rest/v1/prospect_qualifications?"):
            return [
                {
                    "prospect_id": P2,
                    "score": 93.0,
                    "tier": "hot",
                    "status": "scored",
                },
                {
                    "prospect_id": P1,
                    "score": 90.0,
                    "tier": "hot",
                    "status": "scored",
                },
            ]
        if path.startswith("/rest/v1/prospects?"):
            return [
                {"id": P1, "niche": "solar", "website": "https://one.example"},
                {"id": P2, "niche": "solar", "website": None},
            ]
        raise AssertionError(path)

    ids = fetch_hot_source_prospect_ids(
        source="recc_solar",
        niche="solar",
        request=request,
    )

    assert ids == [P1]
    assert len(calls) == 3


def test_hot_source_selector_returns_empty_without_acquisition_rows():
    def request(method, path, payload=None, prefer=None):
        return []

    assert fetch_hot_source_prospect_ids(
        source="recc_solar",
        niche="solar",
        request=request,
    ) == []


def test_source_probe_reprobes_only_buyer_level_recovered_identity(monkeypatch):
    calls = []

    def fake_probe(row, hard_timeout_seconds=55.0, probe_options=None):
        calls.append({
            "row": dict(row),
            "probe_options": dict(probe_options or {}),
        })
        if len(calls) == 1:
            return {
                "site_ok": True,
                "review_ready": False,
                "outreach_ready": False,
                "decision_maker": None,
                "contacts": [],
                "rejection_reason": "no_decision_maker",
            }
        return {
            "site_ok": True,
            "review_ready": True,
            "outreach_ready": True,
            "decision_maker": {
                "name": "Jane Smith",
                "title": "Managing Director",
                "decision_score": 1.0,
            },
            "contacts": [{
                "email": "jane@example.test",
                "bound_to_decision_maker": True,
            }],
            "preferred_email": "jane@example.test",
        }

    monkeypatch.setattr(bridge, "run_buyer_probe_isolated", fake_probe)
    monkeypatch.setattr(
        bridge,
        "_recover_identity_isolated",
        lambda row: {
            "recovered": True,
            "identity": {
                "name": "Jane Smith",
                "title": "Managing Director",
                "source": "empire_first_party_people_probe",
                "source_url": "https://example.test/about",
                "confidence": 0.95,
            },
        },
    )

    result = bridge._source_probe({
        "id": P1,
        "business_name": "Example Solar Ltd",
        "website": "https://example.test",
        "metro": "United Kingdom",
    })

    assert len(calls) == 2
    assert calls[1]["row"]["contact_name"] == "Jane Smith"
    assert calls[1]["row"]["contact_title"] == "Managing Director"
    assert calls[0]["probe_options"] == {
        "max_pages": 12,
        "request_timeout": 5.0,
        "time_budget_seconds": 35.0,
        "allow_company_routed": True,
    }
    assert result["review_ready"] is True
    assert result["identity_recovery"]["promoted"] is True


def test_source_probe_does_not_promote_director_from_identity_confidence(monkeypatch):
    calls = []

    def fake_probe(row, hard_timeout_seconds=55.0, probe_options=None):
        calls.append(dict(row))
        return {
            "site_ok": True,
            "review_ready": False,
            "outreach_ready": False,
            "decision_maker": None,
            "contacts": [],
            "rejection_reason": "no_decision_maker",
        }

    monkeypatch.setattr(bridge, "run_buyer_probe_isolated", fake_probe)
    monkeypatch.setattr(
        bridge,
        "_recover_identity_isolated",
        lambda row: {
            "recovered": True,
            "identity": {
                "name": "John Director",
                "title": "Director",
                "source": "companies_house",
                "source_url": "https://find-and-update.company-information.service.gov.uk/company/123/officers",
                "confidence": 0.99,
            },
        },
    )

    result = bridge._source_probe({
        "id": P1,
        "business_name": "Example Solar Ltd",
        "website": "https://example.test",
        "metro": "United Kingdom",
    })

    assert len(calls) == 1
    assert result["review_ready"] is False
    assert result["identity_recovery"]["promoted"] is False
    assert result["identity_recovery"]["decision_score"] < 0.70


def test_site_timeout_is_durable_deferred_reason():
    from empire_os.buyer_deferred_enrichment import DEFERABLE_REASONS

    assert "site_timeout" in DEFERABLE_REASONS
