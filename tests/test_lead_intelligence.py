from uuid import uuid4

import pytest

from empire_os.lead_intelligence import (
    LeadIntelligenceError,
    LeadIntelligenceLimits,
    build_lead_intelligence,
)


def fixture_ids():
    return str(uuid4()), str(uuid4())


def make_reader(
    prospect_id,
    entity_id,
    *,
    linked=True,
    qualified=True,
):
    calls = []

    def reader(path, params):
        calls.append((path, dict(params)))

        if path == "/rest/v1/prospects":
            return [{
                "id": prospect_id,
                "business_name": "Acme Ltd",
                "niche": "roofing",
                "metro": "london",
                "buy_signal_score": 81,
                "status": "raw",
            }]

        if path == "/rest/v1/prospect_entity_links":
            return ([{
                "prospect_id": prospect_id,
                "entity_id": entity_id,
                "match_method": "exact_business_niche_metro",
                "match_score": 1.0,
                "evidence": {"source_row_count": 2},
                "active": True,
            }] if linked else [])

        if path == "/rest/v1/business_entities":
            return [{
                "id": entity_id,
                "canonical_name": "Acme Ltd",
                "normalized_name": "acme ltd",
                "canonical_niche": "roofing",
                "canonical_metro": "london",
                "identity_confidence": 1.0,
                "resolution_state": "resolved_candidate",
                "provenance": {
                    "resolver": "identity_resolver.dry_run.v1"
                },
            }]

        if path == "/rest/v1/prospect_qualifications":
            return ([{
                "id": str(uuid4()),
                "prospect_id": prospect_id,
                "score": 84.0,
                "tier": "A",
                "status": "scored",
                "scoring_engine": "empire_os.lead_scoring",
                "scoring_version": "v1",
            }] if qualified else [])

        if path == "/rest/v1/intelligence_facts":
            return [
                {
                    "id": str(uuid4()),
                    "entity_type": "company",
                    "entity_id": entity_id,
                    "fact_key": "employee_count",
                    "fact_value": {"value": 50},
                    "confidence": 0.7,
                },
                {
                    "id": str(uuid4()),
                    "entity_type": "company",
                    "entity_id": entity_id,
                    "fact_key": "employee_count",
                    "fact_value": {"value": 62},
                    "confidence": 0.8,
                },
            ]

        if path == "/rest/v1/intelligence_signals":
            return [{
                "id": str(uuid4()),
                "entity_id": entity_id,
                "signal_type": "sales_hiring",
                "signal_domain": "intent",
                "strength": 0.8,
                "confidence": 0.9,
            }]

        if path == "/rest/v1/intelligence_scores":
            return [{
                "id": str(uuid4()),
                "entity_type": "company",
                "entity_id": entity_id,
                "score_type": "omega_fit",
                "score": 88.2,
                "confidence": 0.84,
                "model_key": "omega:v1",
                "features": {"intent": 0.9},
                "explanation": {"why": ["hiring"]},
            }]

        if path == "/rest/v1/intelligence_contact_points":
            return [{
                "id": str(uuid4()),
                "entity_id": entity_id,
                "contact_type": "business_phone",
                "value": "+442000000000",
                "verification_state": "verified",
                "confidence": 0.95,
            }]

        if path == "/rest/v1/intelligence_employment":
            return [{
                "id": str(uuid4()),
                "person_id": str(uuid4()),
                "entity_id": entity_id,
                "title": "Managing Director",
                "buying_role": "economic_buyer",
                "is_current": True,
                "confidence": 0.9,
            }]

        raise AssertionError(f"unexpected path: {path}")

    reader.calls = calls
    return reader


def test_builds_canonical_projection_and_preserves_conflicts():
    prospect_id, entity_id = fixture_ids()
    reader = make_reader(prospect_id, entity_id)

    result = build_lead_intelligence(reader, prospect_id)

    assert result["schema_version"] == "lead_intelligence.v1"
    assert result["source_of_truth"] == "canonical_supabase"
    assert result["read_only"] is True
    assert result["prospect_id"] == prospect_id
    assert result["identity"]["entity"]["id"] == entity_id
    assert result["qualification"]["tier"] == "A"
    assert len(result["intelligence"]["facts"]) == 2
    assert {
        row["fact_value"]["value"]
        for row in result["intelligence"]["facts"]
    } == {50, 62}
    assert result["unknowns"] == []


def test_unresolved_identity_stays_unknown_without_entity_queries():
    prospect_id, entity_id = fixture_ids()
    reader = make_reader(
        prospect_id,
        entity_id,
        linked=False,
        qualified=False,
    )

    result = build_lead_intelligence(reader, prospect_id)

    assert result["identity"]["link"] is None
    assert result["identity"]["entity"] is None
    assert result["qualification"] is None
    assert "canonical_entity_unresolved" in result["unknowns"]
    assert "qualification_missing" in result["unknowns"]

    queried = {path for path, _ in reader.calls}
    assert "/rest/v1/business_entities" not in queried
    assert "/rest/v1/intelligence_signals" not in queried


def test_multiple_active_identity_links_fail_closed():
    prospect_id, entity_id = fixture_ids()

    def reader(path, params):
        if path == "/rest/v1/prospects":
            return [{"id": prospect_id}]
        if path == "/rest/v1/prospect_entity_links":
            return [
                {
                    "prospect_id": prospect_id,
                    "entity_id": entity_id,
                },
                {
                    "prospect_id": prospect_id,
                    "entity_id": str(uuid4()),
                },
            ]
        return []

    with pytest.raises(
        LeadIntelligenceError,
        match="multiple rows",
    ):
        build_lead_intelligence(reader, prospect_id)


def test_invalid_uuid_fails_before_reader_call():
    called = False

    def reader(path, params):
        nonlocal called
        called = True
        return []

    with pytest.raises(
        LeadIntelligenceError,
        match="invalid prospect_id",
    ):
        build_lead_intelligence(reader, "not-a-uuid")

    assert called is False


def test_limits_are_bounded():
    with pytest.raises(ValueError):
        LeadIntelligenceLimits(signals=0)

    with pytest.raises(ValueError):
        LeadIntelligenceLimits(facts=501)
