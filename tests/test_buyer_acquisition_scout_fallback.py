import pytest

from empire_os.buyer_acquisition_scout import run_buyer_scout


def _plan(profile_key: str) -> dict:
    return {
        "priority_targets": [],
        "product_priority_targets": [],
        "icp_priority_targets": [{
            "priority_score": 100,
            "icp_profile_key": profile_key,
            "buying_triggers": ["growth", "expansion", "case intake"],
            "decision_maker_roles": [
                "managing partner",
                "chief revenue officer",
            ],
            "research_queries": {
                "enterprise_and_data_buyers": [
                    f'"{profile_key}" buyer discovery'
                ],
            },
        }],
    }


def _evidence(
    url: str,
    *,
    description: str,
    title: str = "Seed Company",
    role: str = "Chief Revenue Officer",
) -> dict:
    return {
        "ok": True,
        "canonical_url": url,
        "final_url": url,
        "business_names": [],
        "title": title,
        "description": description,
        "emails": [],
        "phones": [],
        "people": [{"name": "Decision Maker", "title": role}],
        "pages_checked": [{
            "visible_text": description,
        }],
        "evidence_score": 0.9,
    }


def test_canonical_fallback_activates_only_when_search_is_empty_and_preserves_source(
    monkeypatch,
):
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {query: [] for query in queries},
    )
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda url, **_kwargs: _evidence(
            url,
            description=(
                "Mass tort law firm expanding case intake for new litigation."
            ),
            role="Managing Partner",
        ),
    )

    result = run_buyer_scout(
        _plan("legal_mass_tort_plaintiff_firm"),
        canonical_seed_records=[{
            "id": "seed-mass-1",
            "business_name": "Recovered Mass Law",
            "niche": "mass tort lawyer",
            "website": "https://mass-seed.example",
            "icp_profile_key": "legal_mass_tort_plaintiff_firm",
        }],
        max_domains=10,
        max_probes=10,
    )

    assert result["search_domain_count"] == 0
    assert result["canonical_seed_domain_count"] == 1
    assert result["canonical_seed_fallback_used"] is True
    assert result["candidate_count"] == 1

    row = result["candidates"][0]
    assert row["discovery_source"] == "canonical_prospect_seed"
    assert row["canonical_seed_prospect_id"] == "seed-mass-1"
    assert row["business_name"] == "Recovered Mass Law"
    assert row["business_name_source"] == "canonical_prospect_seed"
    assert row["query_evidence"][0]["source"] == "canonical_prospect_seed"
    assert row["query_evidence"][0]["prospect_id"] == "seed-mass-1"
    assert row["outreach_authorized"] is False
    assert result["outbound_sent"] is False
    assert result["execution_authority"] == "none"


def test_search_fabric_takes_precedence_over_canonical_seed_fallback(
    monkeypatch,
):
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {
            query: ["fresh-search.example"]
            for query in queries
        },
    )
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda url, **_kwargs: _evidence(
            url,
            description=(
                "Mass tort law firm expanding case intake for new litigation."
            ),
            role="Managing Partner",
        ),
    )

    result = run_buyer_scout(
        _plan("legal_mass_tort_plaintiff_firm"),
        canonical_seed_records=[{
            "id": "seed-should-not-win",
            "business_name": "Old Seed",
            "niche": "mass tort lawyer",
            "website": "https://old-seed.example",
        }],
        max_domains=10,
        max_probes=10,
    )

    assert result["search_domain_count"] == 1
    assert result["canonical_seed_domain_count"] == 0
    assert result["canonical_seed_fallback_used"] is False
    assert result["candidate_count"] == 1
    row = result["candidates"][0]
    assert row["domain"] == "fresh-search.example"
    assert row["discovery_source"] == "search_fabric"
    assert row["canonical_seed_prospect_id"] is None
    assert row["outreach_authorized"] is False


@pytest.mark.parametrize(
    ("profile_key", "niche", "description", "role", "expected_lane"),
    [
        (
            "legal_mass_tort_plaintiff_firm",
            "mass tort lawyer",
            "Mass tort law firm with new litigation and expanding case intake.",
            "Managing Partner",
            "legal_mass_tort",
        ),
        (
            "legal_plaintiff_growth_firm",
            "personal injury lawyer",
            (
                "Personal injury law firm expanding case intake, marketing, "
                "growth and a new practice area."
            ),
            "Managing Partner",
            "legal_services",
        ),
        (
            "insurance_distribution_growth",
            "auto insurance",
            (
                "Insurance agency network expanding distribution growth "
                "through acquisition and new markets."
            ),
            "Chief Revenue Officer",
            "insurance",
        ),
    ],
)
def test_canonical_fallback_classifies_continuous_commercial_lanes(
    monkeypatch,
    profile_key,
    niche,
    description,
    role,
    expected_lane,
):
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {query: [] for query in queries},
    )
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        lambda url, **_kwargs: _evidence(
            url,
            description=description,
            role=role,
        ),
    )

    result = run_buyer_scout(
        _plan(profile_key),
        canonical_seed_records=[{
            "id": f"seed-{profile_key}",
            "business_name": "Recovered Buyer",
            "niche": niche,
            "website": f"https://{expected_lane}.example",
            "icp_profile_key": profile_key,
        }],
        max_domains=10,
        max_probes=10,
    )

    assert result["canonical_seed_fallback_used"] is True
    row = result["candidates"][0]
    assert row["icp_intelligence"]["best_profile_key"] == profile_key
    assert row["continuous_commercial_lane"] == expected_lane
    assert row["continuous_lane_candidate"] is True
    assert row["continuous_lane_fit_score"] >= 40
    assert result["continuous_lane_candidate_counts"][expected_lane] == 1
    assert row["outreach_authorized"] is False


def test_canonical_fallback_processing_is_bounded(monkeypatch):
    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.search_domains_parallel",
        lambda queries, num: {query: [] for query in queries},
    )

    probed = []

    def fake_probe(url, **_kwargs):
        probed.append(url)
        return _evidence(
            url,
            description=(
                "Mass tort law firm expanding case intake for new litigation."
            ),
            role="Managing Partner",
        )

    monkeypatch.setattr(
        "empire_os.buyer_acquisition_scout.probe_site",
        fake_probe,
    )

    seeds = [
        {
            "id": f"seed-{idx}",
            "business_name": f"Recovered Buyer {idx}",
            "niche": "mass tort lawyer",
            "website": f"https://seed-{idx}.example",
            "icp_profile_key": "legal_mass_tort_plaintiff_firm",
        }
        for idx in range(10)
    ]

    result = run_buyer_scout(
        _plan("legal_mass_tort_plaintiff_firm"),
        canonical_seed_records=seeds,
        max_domains=3,
        max_probes=2,
    )

    assert result["canonical_seed_domain_count"] == 10
    assert result["domain_count"] == 3
    assert result["probed_domain_count"] == 2
    assert len(probed) == 2
    assert result["candidate_count"] <= 2
    assert result["outbound_sent"] is False
    assert result["database_write_performed"] is False
