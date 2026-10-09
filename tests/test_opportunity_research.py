from empire_os.opportunity_research import (
    build_opportunity_research_queries,
    execute_opportunity_research,
    research_candidate,
)


def _candidate(**overrides):
    row = {
        "opportunity_key": "market:roofing:denver",
        "opportunity_class": "market_research",
        "title": "roofing / denver",
        "niche": "roofing",
        "metro": "denver",
        "trigger": "observed_market_evidence",
    }
    row.update(overrides)
    return row


def fake_search(query, *, num):
    assert num <= 5
    return {
        "searchParameters": {"engine": "test"},
        "organic": [
            {
                "position": 1,
                "title": "Denver roofing market",
                "snippet": "Roofing services and companies in Denver.",
                "link": "https://example.com/denver-roofing",
            },
            {
                "position": 2,
                "title": "Unrelated cooking page",
                "snippet": "Pasta recipes.",
                "link": "https://example.com/pasta",
            },
        ],
    }


def test_query_plan_is_bounded():
    queries = build_opportunity_research_queries(_candidate())
    assert 1 <= len(queries) <= 3
    assert any("roofing" in query.lower() for query in queries)


def test_research_keeps_search_results_as_observations_only():
    result = research_candidate(
        _candidate(),
        search_fn=fake_search,
        max_results_per_query=3,
    )
    assert result["observation_count"] >= 1
    assert result["irrelevant_result_rejected_count"] >= 1
    assert result["observations_are_verified_facts"] is False
    assert result["demand_inferred"] is False
    assert result["buyer_intent_inferred"] is False
    assert result["revenue_inferred"] is False
    assert result["execution_authority"] == "none"


def test_batch_is_bounded_and_noncommercial():
    radar = {
        "candidates": [_candidate() for _ in range(20)],
    }
    result = execute_opportunity_research(
        radar,
        search_fn=fake_search,
        max_candidates=4,
    )
    assert result["radar_candidate_count"] == 20
    assert result["researched_candidate_count"] == 4
    assert result["outreach_enabled"] is False
    assert result["execution_authority"] == "none"


def test_live_rotation_reaches_all_24_without_duplicate_internal_jobs():
    """Five bounded sweeps cover the Radar rather than five repeating forever."""
    from datetime import datetime, timedelta, timezone
    radar = {"candidates": [
        _candidate(opportunity_key=f"market:roofing:denver:{i}")
        for i in range(24)
    ]}
    intake = {"items": [
        {"opportunity_key": f"market:roofing:denver:{i}", "blockers": [
            "buyer_intent_normalized_score_required",
            "urgency_normalized_score_required",
            "demand_normalized_score_required",
        ]}
        for i in range(24)
    ]}
    t0 = datetime(2026, 10, 9, 10, tzinfo=timezone.utc)
    batch = {}
    refreshed = set()
    calls = []

    def search(query, *, num):
        calls.append(query)
        assert "buyer intent" not in query.lower()
        assert num <= 5
        return fake_search(query, num=num)

    for iteration in range(5):
        batch = execute_opportunity_research(
            radar, intake=intake, previous=batch, search_fn=search,
            max_candidates=5, now=t0 + timedelta(minutes=15 * iteration),
        )
        assert batch["researched_candidate_count"] <= 5
        assert batch["error_count"] == 0
        assert batch["research_rotation_enabled"] is True
        assert batch["buyer_intent_inferred"] is False
        assert batch["commercial_intent_inferred"] is False
        assert batch["revenue_inferred"] is False
        assert batch["execution_authority"] == "none"
        refreshed.update(
            item["opportunity_key"] for item in batch["actions"]
            if item["reused_cached_observations"] is False
        )
    assert len(refreshed) == 24
    assert batch["covered_candidate_count"] == 24
    assert batch["cached_candidate_count"] == 20
    assert batch["researched_candidate_count"] == 4
    assert len(calls) <= 24 * 3
    assert any("deadline" in query for query in calls)
    assert all(a["observations_are_verified_facts"] is False
               for a in batch["actions"])


def test_research_cached_evidence_expires_without_imaginary_verification():
    from datetime import datetime, timedelta, timezone
    candidates = [_candidate(opportunity_key=f"c{i}") for i in range(6)]
    radar = {"candidates": candidates}
    t0 = datetime(2026, 10, 9, tzinfo=timezone.utc)
    first = execute_opportunity_research(
        radar, previous={}, intake={}, max_candidates=6,
        now=t0, search_fn=fake_search,
    )
    assert first["covered_candidate_count"] == 6
    second = execute_opportunity_research(
        radar, previous=first, intake={}, max_candidates=1,
        now=t0 + timedelta(days=8), search_fn=fake_search,
    )
    assert second["researched_candidate_count"] == 1
    assert second["covered_candidate_count"] == 1
    assert second["expired_cached_candidate_count"] == 5
    assert second["cached_candidate_count"] == 0
    assert second["execution_authority"] == "none"


def test_changed_opportunity_expires_incorrect_cached_evidence():
    from datetime import datetime, timedelta, timezone
    a = _candidate(opportunity_key="a")
    b = _candidate(opportunity_key="b")
    radar = {"candidates": [a, b]}
    t0 = datetime(2026, 10, 9, tzinfo=timezone.utc)
    first = execute_opportunity_research(
        radar, previous={}, intake={}, max_candidates=2,
        now=t0, search_fn=fake_search,
    )
    modified = dict(b, trigger="new_verified_public_event_trigger")
    second = execute_opportunity_research(
        {"candidates": [a, modified]}, previous=first, intake={},
        max_candidates=1, now=t0 + timedelta(minutes=20),
        search_fn=fake_search,
    )
    assert second["covered_candidate_count"] == 2
    changed = next(x for x in second["actions"] if x["opportunity_key"] == "b")
    assert changed["reused_cached_observations"] is False


def test_research_queries_do_not_elevate_public_results_into_buyer_demand():
    candidate = _candidate()
    queries = build_opportunity_research_queries(
        candidate,
        evidence_blockers=(
            "urgency_normalized_score_required",
            "demand_normalized_score_required",
            "independent_evidence_required",
        ),
    )
    assert len(queries) <= 3
    assert "deadline" in queries[0]
    assert "official public records" in queries[1]
    results = research_candidate(
        candidate, evidence_blockers=("urgency_normalized_score_required",),
        search_fn=fake_search,
    )
    assert results["observations_are_verified_facts"] is False
    assert results["buyer_intent_inferred"] is False
    assert results["demand_inferred"] is False
    assert results["revenue_inferred"] is False
    assert results["evidence_gap_targets"] == [
        "urgency_normalized_score_required"
    ]


def test_unsearched_candidate_priority_applies_without_starvation():
    from datetime import datetime, timezone
    radar = {"candidates": [
        _candidate(opportunity_key="low", observed_priority_score=10),
        _candidate(opportunity_key="high", observed_priority_score=95),
        _candidate(opportunity_key="medium", observed_priority_score=60),
    ]}
    def empty_search(query, *, num):
        return {"organic": []}
    first = execute_opportunity_research(
        radar, previous={}, intake={}, max_candidates=1,
        now=datetime(2026, 10, 9, tzinfo=timezone.utc),
        search_fn=empty_search,
    )
    assert first["actions"][0]["opportunity_key"] == "high"
    second = execute_opportunity_research(
        radar, previous=first, intake={}, max_candidates=1,
        now=datetime(2026, 10, 9, 0, 15, tzinfo=timezone.utc),
        search_fn=empty_search,
    )
    newly_queried = [a["opportunity_key"] for a in second["actions"]
                     if a["reused_cached_observations"] is False]
    assert newly_queried == ["medium"]
    third = execute_opportunity_research(
        radar, previous=second, intake={}, max_candidates=1,
        now=datetime(2026, 10, 9, 0, 30, tzinfo=timezone.utc),
        search_fn=empty_search,
    )
    newly_queried = [a["opportunity_key"] for a in third["actions"]
                     if a["reused_cached_observations"] is False]
    assert newly_queried == ["low"]
    assert third["covered_candidate_count"] == 3
    assert third["buyer_intent_inferred"] is False


def test_refresh_bridge_reuses_disk_cache_and_rotates_live_sized_inputs(
    tmp_path, monkeypatch,
):
    import json
    from empire_os import opportunity_research as module
    radar = {
        "candidates": [
            _candidate(opportunity_key=f"operational-key-{i}")
            for i in range(12)
        ]
    }
    intake = {"items": [
        {"opportunity_key": f"operational-key-{i}",
         "blockers": ["urgency_normalized_score_required"]}
        for i in range(12)
    ]}
    rp = tmp_path / module.RADAR
    ip = tmp_path / module.INTAKE
    rp.parent.mkdir(parents=True, exist_ok=True)
    ip.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(radar))
    ip.write_text(json.dumps(intake))
    executed = []
    true_executor = module.execute_opportunity_research

    def no_network(radar_arg, **kwargs):
        return true_executor(
            radar_arg, search_fn=lambda q, *, num: (
                executed.append(q) or fake_search(q, num=num)
            ), **kwargs,
        )
    monkeypatch.setattr(module, "execute_opportunity_research", no_network)
    first = module.refresh_opportunity_research(tmp_path)
    assert first["researched_candidate_count"] == 5
    assert first["covered_candidate_count"] == 5
    second = module.refresh_opportunity_research(tmp_path)
    assert second["researched_candidate_count"] == 5
    assert second["covered_candidate_count"] == 10
    assert second["cached_candidate_count"] == 5
    third = module.refresh_opportunity_research(tmp_path)
    assert third["researched_candidate_count"] == 2
    assert third["covered_candidate_count"] == 12
    assert third["cached_candidate_count"] == 10
    assert len(executed) <= 12 * 3
    disk = json.loads((tmp_path / module.OUTPUT).read_text())
    assert disk["covered_candidate_count"] == 12
    assert disk["observations_are_verified_facts"] is False
    assert disk["buyer_intent_inferred"] is False
    assert disk["revenue_inferred"] is False
    assert disk["execution_authority"] == "none"


def test_urgency_queries_match_the_sector_not_generic_permits():
    lawyer = _candidate(niche="mass tort lawyer", metro="Austin")
    roofing = _candidate(niche="roofing", metro="Denver")
    enterprise = _candidate(niche="predictive_revenue_enterprise", metro="Memphis")
    blockers = ("urgency_normalized_score_required",)
    legal = build_opportunity_research_queries(
        lawyer, evidence_blockers=blockers
    )[0].lower()
    roof = build_opportunity_research_queries(
        roofing, evidence_blockers=blockers
    )[0].lower()
    software = build_opportunity_research_queries(
        enterprise, evidence_blockers=blockers
    )[0].lower()
    assert "court filing" in legal and "building permit" not in legal
    assert "storm" in roof
    assert "enterprise procurement" in software
    assert '"' not in legal and '"' not in roof and '"' not in software
    assert "_" not in software


def test_one_bounded_fallback_and_distinct_provider_degradation():
    recovery_calls = []
    primary_calls = []

    def recovery(query, *, num):
        recovery_calls.append(query)
        return fake_search(query, num=num)

    def degraded(query, *, num):
        primary_calls.append(query)
        return {
            "organic": [],
            "searchParameters": {
                "engine": "none",
                "search_state": "PROVIDER_DEGRADED",
            },
            "error": "All engines failed",
        }

    result = research_candidate(
        _candidate(), search_fn=degraded, recovery_fn=recovery,
        evidence_blockers=("urgency_normalized_score_required",),
    )
    assert len(recovery_calls) == 1
    assert len(primary_calls) == result["planned_query_count"] - 1
    assert result["resilient_query_count"] == 1
    assert result["degraded_query_count"] == len(primary_calls)
    assert result["zero_result_query_count"] == len(primary_calls)
    assert result["observation_count"] >= 1
    assert result["observations_are_verified_facts"] is False
    assert result["demand_inferred"] is False
    assert result["buyer_intent_inferred"] is False
    assert result["revenue_inferred"] is False


def test_degraded_without_recovery_is_not_evidence_of_no_demand():
    def degraded(query, *, num):
        return {
            "organic": [],
            "searchParameters": {"search_state": "PROVIDER_DEGRADED"},
            "error": "blocked",
        }
    result = research_candidate(_candidate(), search_fn=degraded)
    assert result["observation_count"] == 0
    assert result["degraded_query_count"] == result["planned_query_count"]
    assert result["zero_result_query_count"] == result["planned_query_count"]
    assert result["error_count"] == 0
    assert result["buyer_intent_inferred"] is False
    assert result["revenue_inferred"] is False
