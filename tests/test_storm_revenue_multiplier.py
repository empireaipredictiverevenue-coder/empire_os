from empire_os.storm_revenue_multiplier import calculate_storm_multiplier


def test_severe_hail_creates_material_multiplier():
    result = calculate_storm_multiplier(
        niche="roofing",
        event_type="hail",
        severity="severe",
        evidence_confidence=0.95,
        territory_match=1.0,
        age_hours=8,
        evidence_refs=("nws:dfw:2026-09-20",),
    )

    assert result.relevant is True
    assert 2.5 < result.multiplier <= 3.0
    assert result.priority_boost > 35
    assert result.modeled_only is True
    assert result.execution_authority == "none"


def test_stale_signal_decays():
    fresh = calculate_storm_multiplier(
        niche="roofing",
        event_type="severe thunderstorm",
        severity="severe",
        evidence_confidence=0.9,
        territory_match=1.0,
        age_hours=12,
        evidence_refs=("nws:fresh",),
    )
    stale = calculate_storm_multiplier(
        niche="roofing",
        event_type="severe thunderstorm",
        severity="severe",
        evidence_confidence=0.9,
        territory_match=1.0,
        age_hours=140,
        evidence_refs=("nws:stale",),
    )

    assert fresh.multiplier > stale.multiplier
    assert stale.multiplier > 1.0


def test_unrelated_niche_does_not_get_storm_boost():
    result = calculate_storm_multiplier(
        niche="legal",
        event_type="hail",
        severity="severe",
        evidence_confidence=1.0,
        territory_match=1.0,
        age_hours=1,
        evidence_refs=("nws:dfw",),
    )

    assert result.relevant is False
    assert result.multiplier == 1.0
    assert result.priority_boost == 0.0


def test_missing_evidence_fails_closed():
    try:
        calculate_storm_multiplier(
            niche="roofing",
            event_type="hail",
            severity="severe",
            evidence_confidence=1.0,
            territory_match=1.0,
            age_hours=1,
            evidence_refs=(),
        )
    except ValueError as exc:
        assert "evidence refs" in str(exc)
    else:
        raise AssertionError("storm multiplier must require evidence")
