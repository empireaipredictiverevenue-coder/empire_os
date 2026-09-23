from pathlib import Path

import empire_os.solar_opportunity_map as som


PID = "00000000-0000-0000-0000-000000000101"


def fake_request(method, path, payload=None, prefer=None):
    if path.startswith("/rest/v1/prospects?"):
        return [{
            "id": PID,
            "business_name": "Example Solar Ltd",
            "niche": "solar",
            "metro": "United Kingdom",
            "website": "https://solar.example",
            "phone": "0123456789",
            "address": "1 Test Road",
            "status": "qualified",
        }]
    if path.startswith("/rest/v1/prospect_qualifications?"):
        return [{
            "prospect_id": PID,
            "score": 92.6,
            "tier": "hot",
            "status": "scored",
            "evidence_confidence": 0.9,
            "result_payload": {},
            "scored_at": "2026-09-23T20:00:00Z",
        }]
    if path.startswith("/rest/v1/prospect_acquisitions?"):
        return [{
            "source": "recc_solar",
            "source_url": "https://recc.example/member",
            "evidence": {},
            "created_at": "2026-09-23T19:00:00Z",
        }]
    if path.startswith("/rest/v1/buyer_candidate_reviews?"):
        return [{
            "id": "00000000-0000-0000-0000-000000000301",
            "prospect_id": PID,
            "contact_name": "Jane Smith",
            "contact_title": "Managing Director",
            "contact_email": "info@solar.example",
            "offer_key": "managed_service",
            "company_score": 69,
            "decision_score": 1.0,
            "evidence": {"contact_route": "company_routed"},
            "status": "pending",
            "proposed_at": "2026-09-23T21:00:00Z",
        }]
    raise AssertionError(path)


def test_solar_map_reuses_search_report_and_keeps_serp_unknown():
    payload = som.build_solar_opportunity_map(
        PID,
        request=fake_request,
        crawl=lambda *args, **kwargs: {
            "schema_version": "empire.search.crawl.v1",
            "audit": {
                "available": True,
                "findings": [{
                    "code": "meta_description_missing",
                    "severity": "medium",
                    "scope": "site",
                    "message": "No usable meta description was observed.",
                    "url": "https://solar.example",
                }],
            },
        },
        market_gps={},
        competitor_market={},
        observe_tags=lambda *args, **kwargs: {
            "ok": True,
            "page_tags": {
                "url": "https://solar.example",
                "title": "Example Solar",
                "title_count": 1,
                "meta_description": None,
                "canonical_url": "https://solar.example",
                "robots": "index,follow",
                "open_graph": {},
                "twitter": {},
                "json_ld_types": [],
                "viewport_present": True,
                "charset_present": True,
                "h1_count": 1,
                "images_missing_alt": 0,
            },
            "measurement_tags": {
                "ga4_measurement_ids": [],
                "google_tag_ids": [],
                "gtm_container_ids": [],
                "observed_events": [],
            },
        },
    )

    assert payload["offer"]["price_display"] == "£249"
    assert payload["buyer_review"]["contact_route"] == "company_routed"
    assert payload["actual_revenue"] is False
    report = payload["search_opportunity_report"]
    assert report["product"]["key"] == "search_opportunity_map"
    states = {row["key"]: row["state"] for row in report["sections"]}
    assert states["priority_backlog"] == "observed"
    assert states["opportunity_evidence"] == "observed"
    assert states["keyword_opportunity_portfolio"] == "unavailable"
    assert report["synthetic_metrics"] == 0


def test_solar_map_artifacts_are_written_atomically(tmp_path: Path):
    payload = som.build_solar_opportunity_map(
        PID,
        request=fake_request,
        crawl=lambda *args, **kwargs: {
            "audit": {"available": True, "findings": []},
        },
        market_gps={},
        competitor_market={},
        observe_tags=lambda *args, **kwargs: {
            "ok": False,
            "error": "timeout",
        },
    )

    paths = som.write_solar_opportunity_map(payload, root=tmp_path)

    json_path = Path(paths["json_path"])
    md_path = Path(paths["markdown_path"])
    assert json_path.exists()
    assert md_path.exists()
    assert "Solar Opportunity Map" in md_path.read_text()
    assert json_path.stat().st_mode & 0o777 == 0o600
    assert md_path.stat().st_mode & 0o777 == 0o600


def test_solar_map_v2_adds_observed_market_and_competitor_context():
    market_gps = {
        "window_days": 7,
        "demand_signal_semantics": (
            "only genuine commercial replies, terms and verified payments "
            "count as observed commercial demand"
        ),
        "competitor_pressure_semantics": (
            "modeled research proxy from observed competitive evidence density"
        ),
        "markets": [{
            "niche": "solar",
            "metro": "United Kingdom",
            "canonical_company_count": 20,
            "acquisition_count": 20,
            "qualification_count": 20,
            "approved_buyer_count": 2,
            "delivered_outreach_count": 0,
            "commercial_reply_count": 0,
            "commercial_terms_count": 0,
            "verified_payment_count": 0,
            "commercial_demand_state": "not_observed",
            "commercial_demand_evidence_count": 0,
            "competitive_entity_count": 4,
            "competitive_signal_count": 7,
            "competitor_pressure_proxy": 8.75,
            "competitor_pressure_basis": "competitive_signal_density",
            "research_priority_score": 76.0,
            "evidence_refs": [
                "canonical:prospect_acquisitions",
                "canonical:prospect_qualifications",
            ],
        }],
    }
    competitor = {
        "niche": "solar",
        "metro": "United Kingdom",
        "market_key": "solar:gb",
        "market_query": "solar installers uk",
        "resolved_company_count": 20,
        "observed_company_count": 8,
        "research_gap_company_count": 12,
        "territory_heatmap": [{"metro": "United Kingdom"}],
        "underserved_audience_candidates": [{
            "entity_id": "entity-1",
            "company_name": "Competitor One",
            "company_domain": "competitor.example",
            "observed_competitor_count": 0,
            "observed_evidence_count": 0,
            "reason": "No competitor evidence observed.",
        }],
    }

    payload = som.build_solar_opportunity_map(
        PID,
        request=fake_request,
        market_gps=market_gps,
        competitor_market=competitor,
        crawl=lambda *args, **kwargs: {
            "audit": {"available": True, "findings": []},
        },
        observe_tags=lambda *args, **kwargs: {
            "ok": False,
            "error": "timeout",
        },
    )

    assert payload["schema_version"] == "empire.solar-opportunity-map.v2"
    assert payload["market_context"]["available"] is True
    assert payload["market_context"]["match_basis"] == "exact_niche_metro"
    market = payload["market_context"]["markets"][0]
    assert market["commercial_demand_state"] == "not_observed"
    assert market["commercial_demand_evidence_count"] == 0
    assert market["revenue_inferred"] is False

    assert payload["competitor_context"]["available"] is True
    assert payload["competitor_context"]["research_gap_company_count"] == 12
    assert payload["competitor_context"]["market_share_inferred"] is False
    assert payload["competitor_context"]["revenue_opportunity_inferred"] is False

    assert payload["local_visibility"]["available"] is False
    assert payload["local_visibility"]["synthetic_points"] == 0

    markdown = som.render_markdown(payload)
    assert "## Market GPS" in markdown
    assert "## Competitor coverage" in markdown
    assert "## Local visibility" in markdown
    assert "Coverage gaps are research gaps only" in markdown


def test_market_context_labels_niche_portfolio_as_not_local():
    context = som._market_gps_context(
        {"niche": "solar", "metro": "United Kingdom"},
        {
            "window_days": 7,
            "markets": [
                {
                    "niche": "solar",
                    "metro": "London",
                    "research_priority_score": 90,
                },
                {
                    "niche": "solar",
                    "metro": "Manchester",
                    "research_priority_score": 80,
                },
            ],
        },
    )

    assert context["available"] is True
    assert context["match_basis"] == "niche_portfolio_not_local"
    assert context["local_match"] is False
    assert len(context["markets"]) == 2
