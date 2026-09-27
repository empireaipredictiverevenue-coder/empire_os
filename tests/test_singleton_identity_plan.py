import pytest

from empire_os.singleton_identity_plan import (
    SingletonIdentityPlanError,
    build_singleton_identity_plan,
)


PROSPECT_ID = "ce13a10d-5b7a-4707-977e-0577fb0d3536"


def inputs():
    prospect = {
        "id": PROSPECT_ID,
        "business_name": "All Star Roofing",
        "niche": "roofing",
        "metro": "austin, tx",
        "phone": "+1-512-477-7827",
    }
    acquisition = {
        "prospect_id": PROSPECT_ID,
        "source": "overpass_osm",
        "source_url": "https://www.openstreetmap.org/node/2513069333",
        "evidence": {
            "quality": {
                "accepted": True,
                "confidence": 100,
                "source_role": "identity_or_direct",
            },
            "raw": {
                "business_website": "https://www.allstarroofingtexas.com/",
                "osm_tags": {
                    "name": "All Star Roofing",
                    "phone": "+1-512-477-7827",
                    "website": "https://www.allstarroofingtexas.com/",
                },
            },
        },
    }
    enrichment = {
        "fields": {
            "website": "https://allstarroofingtexas.com",
            "email": "info@allstarroofingtx.com",
        },
        "evidence": [
            {
                "source": "identity_guard",
                "accepted": True,
                "source_phone_match": True,
            },
            {
                "source": "acquisition_evidence",
                "accepted": True,
            },
        ],
    }
    return prospect, acquisition, enrichment


def test_strong_direct_singleton_produces_dry_run_candidate():
    prospect, acquisition, enrichment = inputs()
    plan = build_singleton_identity_plan(
        prospect=prospect,
        acquisition=acquisition,
        enrichment=enrichment,
    )

    assert plan["resolution_state"] == "evidence_resolved_candidate"
    assert plan["dry_run"] is True
    assert plan["writes_performed"] == 0
    assert plan["promotion_ready"] is False
    assert plan["requires_explicit_production_approval"] is True
    assert plan["association_confidence"] == 1.0
    assert plan["canonical_website_candidate"] == (
        "https://allstarroofingtexas.com"
    )


def test_candidate_id_is_deterministic():
    prospect, acquisition, enrichment = inputs()
    first = build_singleton_identity_plan(
        prospect=prospect,
        acquisition=acquisition,
        enrichment=enrichment,
    )
    second = build_singleton_identity_plan(
        prospect=prospect,
        acquisition=acquisition,
        enrichment=enrichment,
    )
    assert first["entity_id_candidate"] == second["entity_id_candidate"]


def test_phone_mismatch_fails_closed():
    prospect, acquisition, enrichment = inputs()
    acquisition["evidence"]["raw"]["osm_tags"]["phone"] = "+1-512-000-0000"

    with pytest.raises(SingletonIdentityPlanError, match="phone mismatch"):
        build_singleton_identity_plan(
            prospect=prospect,
            acquisition=acquisition,
            enrichment=enrichment,
        )


def test_verified_domain_mismatch_fails_closed():
    prospect, acquisition, enrichment = inputs()
    enrichment["fields"]["website"] = "https://different-roofer.example"

    with pytest.raises(
        SingletonIdentityPlanError,
        match="verified website mismatch",
    ):
        build_singleton_identity_plan(
            prospect=prospect,
            acquisition=acquisition,
            enrichment=enrichment,
        )


def test_identity_guard_rejection_fails_closed():
    prospect, acquisition, enrichment = inputs()
    enrichment["evidence"][0]["accepted"] = False

    with pytest.raises(
        SingletonIdentityPlanError,
        match="identity guard did not accept site",
    ):
        build_singleton_identity_plan(
            prospect=prospect,
            acquisition=acquisition,
            enrichment=enrichment,
        )


def test_low_acquisition_confidence_fails_closed():
    prospect, acquisition, enrichment = inputs()
    acquisition["evidence"]["quality"]["confidence"] = 89

    with pytest.raises(
        SingletonIdentityPlanError,
        match="confidence below singleton floor",
    ):
        build_singleton_identity_plan(
            prospect=prospect,
            acquisition=acquisition,
            enrichment=enrichment,
        )
