from copy import deepcopy

from empire_os.opportunity_radar import build_opportunity_radar


def candidate(**changes):
    base = {
        "schema_version": "empire.opportunity-source.v1",
        "candidate_key": "economic_opportunity_economic_signal_" + ("a" * 64),
        "tenant_id": "tenant-alpha",
        "entity_id": "11111111-1111-1111-1111-111111111111",
        "source_id": "22222222-2222-2222-2222-222222222222",
        "source_signal_id": "economic_signal_" + ("a" * 64),
        "source_family": "economic_signal_fabric",
        "source_signal_type": "market_gap",
        "opportunity_type": "market_gap",
        "observed_at": "2026-10-06T09:00:00+00:00",
        "evidence_refs": [
            "canonical:evidence:1",
            "canonical:evidence:2",
        ],
        "strength": 0.8,
        "confidence": 0.9,
        "source_payload": {"scope": "roofing:denver"},
        "buyer_demand_verified": False,
        "commercial_readiness_verified": False,
        "economics_verified": False,
        "payout_cents": None,
        "expected_revenue_cents": None,
        "recognized_revenue_cents": None,
        "evidence_complete": True,
        "factory_ready": False,
        "review_required": True,
        "execution_authority": "none",
        "outreach_authority": "none",
        "calls_authority": "none",
        "traffic_authority": "none",
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
    }
    base.update(changes)
    return base


def snapshot(rows=None, **changes):
    base = {
        "schema_version": "empire.economic-opportunity-snapshot.v1",
        "mode": "OBSERVE",
        "generated_at": "2026-10-06T09:30:00+00:00",
        "candidates": rows if rows is not None else [candidate()],
        "automatic_external_execution_allowed": False,
        "execution_authority": "none",
    }
    base.update(changes)
    return base


def radar(economic_signals):
    return build_opportunity_radar(
        market_gps=None,
        community_intent=None,
        competitor_market=None,
        tam_market=None,
        storm_opportunity=None,
        economic_signals=economic_signals,
        generated_at="2026-10-06T09:30:00+00:00",
    )


def test_radar_accepts_normalized_economic_signal_candidate():
    result = radar(snapshot())

    assert result["candidate_count"] == 1
    assert result["source_status"]["economic_signals"]["available"] is True

    row = result["candidates"][0]
    assert row["source"] == "economic_signal_fabric"
    assert row["opportunity_class"] == "market_gap"
    assert row["tenant_id"] == "tenant-alpha"
    assert row["observed_priority_score"] == 90.0


def test_missing_economic_source_is_unavailable():
    result = radar(None)

    assert result["candidate_count"] == 0
    assert result["source_status"]["economic_signals"]["available"] is False


def test_wrong_snapshot_schema_fails_closed():
    result = radar(snapshot(schema_version="legacy.v1"))
    assert result["candidate_count"] == 0


def test_non_observe_snapshot_fails_closed():
    result = radar(snapshot(mode="EXECUTE"))
    assert result["candidate_count"] == 0


def test_snapshot_authority_expansion_fails_closed():
    result = radar(snapshot(execution_authority="execute"))
    assert result["candidate_count"] == 0


def test_external_execution_flag_fails_closed():
    result = radar(snapshot(automatic_external_execution_allowed=True))
    assert result["candidate_count"] == 0


def test_candidate_authority_expansion_fails_closed():
    result = radar(snapshot([
        candidate(commercial_authority="execute")
    ]))
    assert result["candidate_count"] == 0


def test_duplicate_economic_candidate_collapses():
    original = candidate()
    duplicate = deepcopy(original)

    result = radar(snapshot([original, duplicate]))

    assert result["candidate_count"] == 1


def test_unknown_economics_remain_unknown():
    result = radar(snapshot())
    row = result["candidates"][0]

    assert row["buyer_demand_verified"] is False
    assert row["economics_verified"] is False
    assert row["expected_revenue_cents"] is None
    assert row["recognized_revenue_cents"] is None
    assert row["revenue_inferred"] is False


def test_payload_cannot_grant_commercial_truth():
    row = candidate(
        source_payload={
            "buyer_demand_verified": True,
            "expected_revenue_cents": 999999999,
        }
    )

    result = radar(snapshot([row]))
    output = result["candidates"][0]

    assert output["buyer_demand_verified"] is False
    assert output["expected_revenue_cents"] is None
    assert output["commercial_ready"] is False


def test_all_external_authorities_remain_none():
    result = radar(snapshot())
    row = result["candidates"][0]

    for field in (
        "execution_authority",
        "outreach_authority",
        "calls_authority",
        "traffic_authority",
        "commercial_authority",
        "payment_authority",
        "revenue_recognition_authority",
    ):
        assert row[field] == "none"

    assert result["execution_authority"] == "none"
    assert result["automatic_external_execution_allowed"] is False


def test_all_four_economic_classes_enter_same_radar_path():
    classes = (
        ("revenue_recovery", "revenue_leak"),
        ("idle_asset_activation", "idle_asset"),
        ("market_gap", "market_gap"),
        ("waste_recovery", "idle_waste"),
    )

    rows = []
    for index, (opportunity_type, signal_type) in enumerate(classes):
        rows.append(candidate(
            candidate_key=(
                "economic_opportunity_economic_signal_"
                + str(index) * 64
            ),
            source_signal_id="economic_signal_" + str(index) * 64,
            opportunity_type=opportunity_type,
            source_signal_type=signal_type,
        ))

    result = radar(snapshot(rows))

    assert result["candidate_count"] == 4
    assert {
        row["opportunity_class"]
        for row in result["candidates"]
    } == {
        "revenue_recovery",
        "idle_asset_activation",
        "market_gap",
        "waste_recovery",
    }
    assert all(
        row["source"] == "economic_signal_fabric"
        for row in result["candidates"]
    )
