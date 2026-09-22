from empire_os.competitor_market_scale import (
    review_market_seed_config,
    run_market_scale_sweep,
)


def _config():
    return {
        "market_key": "denver-co-roofing",
        "market_query": "Denver CO roofing",
        "niche": "roofing",
        "metro": "denver, co",
        "source_refs": ["https://example.com/denver-roofers"],
        "competitors": [
            {
                "competitor_key": "elite-roofing-solar",
                "competitor_name": "Elite Roofing & Solar",
                "competitor_domain": "elite-roofs.com",
            },
            {
                "competitor_key": "core-roofing-solar",
                "competitor_name": "Core Roofing + Solar",
                "competitor_domain": "coreroofing.com",
            },
        ],
    }


def _sweep_fn(**kwargs):
    key = kwargs["competitor_key"]
    common = {
        "schema_version": "empire.competitor_audience_sweep.v1",
        "mode": "OBSERVE",
        "candidate_count": 5,
        "persisted_count": 0,
        "existing_count": 0,
        "evidence": [],
        "signals": [],
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }

    if key == "elite-roofing-solar":
        common["evidence"] = [
            {
                "entity_id": "entity-golden",
                "company_name": "Golden Spike Roofing Inc",
                "company_domain": "goldenspikeroofing.com",
                "competitor_key": key,
                "competitor_domain": "elite-roofs.com",
                "source_ref": "https://example.com/list-a",
                "evidence_type": "comparison_mention",
            },
            {
                "entity_id": "entity-colorado",
                "company_name": "Colorado's Best Roofing",
                "company_domain": "roofingcolorado.com",
                "competitor_key": key,
                "competitor_domain": "elite-roofs.com",
                "source_ref": "https://example.com/list-b",
                "evidence_type": "comparison_mention",
            },
        ]
    elif key == "core-roofing-solar":
        common["evidence"] = [
            {
                "entity_id": "entity-golden",
                "company_name": "Golden Spike Roofing Inc",
                "company_domain": "goldenspikeroofing.com",
                "competitor_key": key,
                "competitor_domain": "coreroofing.com",
                "source_ref": "https://example.com/list-a",
                "evidence_type": "comparison_mention",
            }
        ]

    return common


def test_market_seed_config_requires_unique_competitors():
    raw = _config()
    raw["competitors"].append(dict(raw["competitors"][0]))

    result = review_market_seed_config(raw)

    assert result["review_ready"] is False
    assert "invalid_competitor_seed" in result["blockers"]


def test_market_scale_runs_multiple_competitors():
    result = run_market_scale_sweep(
        writer=object(),
        config=_config(),
        sweep_fn=_sweep_fn,
    )

    assert result["configured_competitor_count"] == 2
    assert result["executed_competitor_count"] == 2
    assert result["unique_evidence_count"] == 3
    assert result["company_count"] == 2
    assert result["competitor_with_evidence_count"] == 2
    assert result["buyer_intent_inferred"] is False
    assert result["commercial_intent_inferred"] is False
    assert result["market_share_inferred"] is False
    assert result["outreach_enabled"] is False
    assert result["execution_authority"] == "none"


def test_market_scale_builds_shared_audience_overlap_without_market_share():
    result = run_market_scale_sweep(
        writer=object(),
        config=_config(),
        sweep_fn=_sweep_fn,
    )

    by_company = {
        row["company_name"]: row
        for row in result["companies"]
    }
    golden = by_company["Golden Spike Roofing Inc"]
    assert golden["competitor_count"] == 2
    assert golden["evidence_count"] == 2
    assert golden["buyer_intent"] is False
    assert golden["commercial_intent"] is False

    assert result["shared_audience_edge_count"] == 1
    edge = result["shared_audience_edges"][0]
    assert edge["shared_company_count"] == 1
    assert edge["shared_company_entity_ids"] == ["entity-golden"]
    assert edge["market_share_inferred"] is False


def test_market_scale_can_bound_seed_count():
    result = run_market_scale_sweep(
        writer=object(),
        config=_config(),
        max_seeds=1,
        sweep_fn=_sweep_fn,
    )

    assert result["configured_competitor_count"] == 2
    assert result["executed_competitor_count"] == 1
    assert result["competitor_with_evidence_count"] == 1
    assert result["shared_audience_edge_count"] == 0


def test_market_scale_persistence_counts_do_not_imply_commercial_authority():
    def persisted_sweep(**kwargs):
        row = _sweep_fn(**kwargs)
        row["persisted_count"] = 1
        return row

    result = run_market_scale_sweep(
        writer=object(),
        config=_config(),
        persist=True,
        sweep_fn=persisted_sweep,
    )

    assert result["persist_requested"] is True
    assert result["persisted_signal_count"] == 2
    assert result["prospect_created"] is False
    assert result["outreach_enabled"] is False
    assert result["execution_authority"] == "none"
