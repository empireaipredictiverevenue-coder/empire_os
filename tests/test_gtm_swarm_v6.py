from empire_os.gtm_swarm_v6 import (
    EngagementEvent,
    GtmLeadEvidence,
    NicheConfig,
    build_gtm_plan,
    rescore_engagement,
)


def config():
    return NicheConfig(
        niche="roofing",
        icp_key="owner_operator_roofing",
        target_metros=("Austin", "Dallas"),
        score_threshold=70,
    )


def lead(**overrides):
    data = {
        "prospect_id": "prospect-1",
        "niche": "roofing",
        "metro": "Austin",
        "score": 84,
        "score_evidence_ref": "omega:prospect-1",
        "intent_class": "commercial",
        "intent_evidence_refs": ("keyword:roofing-leads",),
        "contact_ready": True,
        "outreach_ready": True,
        "event_signal_observed": False,
    }
    data.update(overrides)
    return GtmLeadEvidence(**data)


def test_multi_niche_plan_routes_ready_lead_to_governed_handoff():
    plan = build_gtm_plan(config(), lead())

    assert plan["eligible_for_copy_draft"] is True
    assert plan["eligible_for_governed_outbound_handoff"] is True
    assert plan["lead_magnet_key"] == "revenue_leak_audit"
    assert plan["copy_generation"]["variant_count"] == 3
    assert plan["execution"]["direct_send"] is False
    assert plan["execution"]["handoff"] == "canonical_gtm_outbound_governor"
    assert plan["actual_revenue"] is False


def test_score_below_threshold_stops_before_copy_and_send():
    plan = build_gtm_plan(config(), lead(score=69))

    assert plan["eligible_for_copy_draft"] is False
    assert plan["eligible_for_governed_outbound_handoff"] is False
    assert "below_niche_score_threshold" in plan["blockers"]


def test_event_trigger_requires_observed_event_for_radar():
    no_event = build_gtm_plan(
        config(),
        lead(
            intent_class="event_trigger",
            event_signal_observed=False,
        ),
    )
    with_event = build_gtm_plan(
        config(),
        lead(
            intent_class="event_trigger",
            event_signal_observed=True,
        ),
    )

    assert no_event["lead_magnet_key"] is None
    assert with_event["lead_magnet_key"] == "live_event_radar"


def test_engagement_rescore_uses_observed_events_only():
    result = rescore_engagement(
        base_score=70,
        events=[
            EngagementEvent(
                event_type="link_click",
                evidence_ref="event:1",
                observed_at="2026-09-20T19:00:00+00:00",
            ),
            EngagementEvent(
                event_type="lead_magnet_completed",
                evidence_ref="event:2",
                observed_at="2026-09-20T19:02:00+00:00",
            ),
        ],
    )

    assert result["rescored"] == 86
    assert result["reengagement_eligible"] is True
    assert result["direct_send"] is False
    assert result["evidence_refs"] == ["event:1", "event:2"]


def test_unsubscribe_hard_stops_reengagement():
    result = rescore_engagement(
        base_score=95,
        events=[
            EngagementEvent(
                event_type="unsubscribe",
                evidence_ref="event:stop",
                observed_at="2026-09-20T19:00:00+00:00",
            ),
        ],
    )

    assert result["rescored"] == 0
    assert result["terminal_stop"] is True
    assert result["reengagement_eligible"] is False
