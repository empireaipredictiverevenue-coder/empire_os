from empire_os.buyer_acquisition_scout import run_buyer_scout


def _plan():
    return {
        "priority_targets": [],
        "product_priority_targets": [],
        "icp_priority_targets": [{
            "priority_score": 100,
            "icp_profile_key": "high_ticket_home_service",
            "buying_triggers": [],
            "decision_maker_roles": ["owner"],
            "research_queries": {
                "end_service_buyers": [
                    '"general contractor" NYC'
                ],
            },
        }],
    }


def _seed(name, domain):
    return {
        "id": "seed-1",
        "business_name": name,
        "niche": "general_contractor",
        "website": f"https://{domain}",
        "metro": "nyc",
        "icp_profile_key": "high_ticket_home_service",
        "seed_buyer_pools": [
            "end_service_buyers",
            "local_and_smb_buyers",
        ],
        "seed_product_code": "permit_intelligence",
        "seed_corridor_key": (
            "permit-recovery:v1:general_contractor:nyc"
        ),
    }


def _run(monkeypatch, *, seed, evidence):
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {query: [] for query in queries},
    )
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda url, **kwargs: evidence,
    )
    return run_buyer_scout(
        _plan(),
        canonical_seed_records=[seed],
        max_domains=10,
        max_probes=10,
    )


def test_generic_home_schema_name_does_not_override_corroborated_seed(
    monkeypatch,
):
    result = _run(
        monkeypatch,
        seed=_seed(
            "V.I.P FIRE SPRINKLERS INC",
            "vipfiresprinkler.example",
        ),
        evidence={
            "ok": True,
            "canonical_url": "https://vipfiresprinkler.example/",
            "final_url": "https://vipfiresprinkler.example/",
            "title": "Home",
            "description": (
                "VIP Fire Sprinklers Inc is a licensed NYC contractor "
                "serving Brooklyn, Queens, Manhattan, Bronx and Staten Island."
            ),
            "business_names": ["Home"],
            "addresses": ["Brooklyn, NY"],
            "emails": ["sales@vipfiresprinkler.example"],
            "phones": ["718-555-0100"],
            "people": [],
            "pages_checked": [{
                "visible_text": (
                    "VIP Fire Sprinklers Inc licensed New York City "
                    "fire sprinkler contractor."
                )
            }],
            "evidence_score": 0.85,
        },
    )

    row = result["candidates"][0]
    assert row["business_name"] == "V.I.P FIRE SPRINKLERS INC"
    assert row["business_name_source"] == (
        "canonical_seed_corroborated_by_site"
    )
    assert row["canonical_seed_identity_corroborated"] is True
    assert row["permit_territory_state"] == "NYC_FIRST_PARTY_EVIDENCE"
    assert row["continuous_commercial_lane"] == "permit_home_services"


def test_seed_identity_mismatch_uses_first_party_site_identity(monkeypatch):
    result = _run(
        monkeypatch,
        seed=_seed("LITRIC CONTRACTING", "zicklin.example"),
        evidence={
            "ok": True,
            "canonical_url": "https://zicklin.example/",
            "final_url": "https://zicklin.example/",
            "title": "Home Zicklin Contracting",
            "description": (
                "Zicklin Contracting provides general contracting "
                "and permit services across NYC."
            ),
            "business_names": [],
            "addresses": ["99 Wall St, New York, NY"],
            "emails": ["sales@zicklin.example"],
            "phones": ["347-555-0100"],
            "people": [],
            "pages_checked": [{
                "visible_text": (
                    "Zicklin Contracting New York City general contractor."
                )
            }],
            "evidence_score": 0.8,
        },
    )

    row = result["candidates"][0]
    assert row["business_name"] == "Zicklin Contracting"
    assert row["business_name_source"] == "first_party_site_identity"
    assert row["canonical_seed_identity_corroborated"] is False
    assert row["permit_territory_state"] == "NYC_FIRST_PARTY_EVIDENCE"
    assert row["continuous_commercial_lane"] == "permit_home_services"


def test_permit_lane_requires_first_party_nyc_territory(monkeypatch):
    result = _run(
        monkeypatch,
        seed=_seed("ADVANCED CONTR.", "advanced.example"),
        evidence={
            "ok": True,
            "canonical_url": "https://advanced.example/",
            "final_url": "https://advanced.example/",
            "title": "Advanced General Contractor, Inc.",
            "description": (
                "Residential and commercial general contractor serving "
                "Kern County, Fresno County and Sacramento County."
            ),
            "business_names": ["Advanced General Contractor, Inc."],
            "addresses": ["California"],
            "emails": [],
            "phones": [],
            "people": [],
            "pages_checked": [{
                "visible_text": "Serving California counties."
            }],
            "evidence_score": 0.4,
        },
    )

    row = result["candidates"][0]
    assert row["permit_territory_state"] == "NYC_NOT_OBSERVED"
    assert row["continuous_lane_candidate"] is False
    assert row["continuous_commercial_lane"] is None
