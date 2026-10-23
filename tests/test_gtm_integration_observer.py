from datetime import datetime, timezone
import json

from empire_os.gtm_agent import GTM_AGENT_ID
from empire_os.gtm_integration_observer import (
    build_gtm_integration_observation,
    observe_gtm_integration,
)

NOW = datetime(2026, 10, 22, 22, 0, tzinfo=timezone.utc)


def radar(rows=None):
    return {
        "mode": "OBSERVE",
        "source_status": {"market_gps": {"available": True}},
        "candidates": rows if rows is not None else [{
            "opportunity_key": "market:roofing:birmingham",
            "source": "market_sweeps_revenue_gps",
            "opportunity_class": "market_research",
            "offer_key": "planning_brief",
            "execution_authority": "none",
            "evidence_refs": ["council-source-1"],
        }],
    }


def loop():
    return {"mode": "OBSERVE", "highest_priority_blocker": "buyer_conversation", "loop_complete": False}


def test_existing_agent_is_invoked_but_never_executes():
    result = build_gtm_integration_observation(
        radar(), loop(), now=NOW,
        radar_source_fresh=True,
        commercial_loop_fresh=True,
    )
    assert result["agent_id"] == GTM_AGENT_ID
    assert result["agent_decision"]["next_action"] == "conversation.monitor"
    assert result["agent_decision"]["execution_performed"] is False
    assert result["internal_research_review_count"] == 1
    assert result["handoffs"][0]["status"] == "INTERNAL_RESEARCH_REVIEW_ONLY"
    assert result["outreach_sent"] is False
    assert result["crm_write_performed"] is False


def test_stale_sources_and_commercial_loop_fail_closed():
    result = build_gtm_integration_observation(
        radar(), loop(), now=NOW,
        radar_source_fresh=False,
        commercial_loop_fresh=False,
    )
    assert result["agent_decision"] is None
    assert result["internal_research_review_count"] == 0
    assert result["held_candidate_count"] == 1


def test_no_unknown_origin_or_missing_provenance_promotion():
    candidates = [
        {"opportunity_key": "x", "source": "custom_product", "evidence_refs": ["ref"]},
        {"opportunity_key": "y", "source": "market_sweeps_revenue_gps", "evidence_refs": []},
        {"opportunity_key": "z", "source": "market_sweeps_revenue_gps", "evidence_refs": ["ref"],
         "execution_authority": "outbound"},
    ]
    result = build_gtm_integration_observation(
        radar(candidates), loop(), now=NOW,
        radar_source_fresh=True,
        commercial_loop_fresh=True,
    )
    assert result["internal_research_review_count"] == 0
    assert result["held_candidate_count"] == 3


def test_dedup_and_deterministic_ids():
    item = radar()["candidates"][0]
    one = build_gtm_integration_observation(
        radar([item, item]), loop(), now=NOW,
        radar_source_fresh=True, commercial_loop_fresh=True,
    )
    two = build_gtm_integration_observation(
        radar([item]), loop(), now=NOW,
        radar_source_fresh=True, commercial_loop_fresh=True,
    )
    assert one["internal_research_review_count"] == 1
    assert one["held_candidate_count"] == 1
    assert one["handoffs"][0]["handoff_id"] == two["handoffs"][0]["handoff_id"]


def test_observer_creates_local_observation_without_external_actions(tmp_path):
    rad = tmp_path / "runtime/opportunity_radar/latest.json"
    rad.parent.mkdir(parents=True)
    rad.write_text(json.dumps({
        **radar(),
        "generated_at": NOW.isoformat(),
        "source_status": {"market_gps": {"available": True, "generated_at": NOW.isoformat()}},
    }))
    com = tmp_path / "runtime/commercial_loop/latest.json"
    com.parent.mkdir(parents=True)
    com.write_text(json.dumps(loop()))
    result = observe_gtm_integration(tmp_path, now=NOW)
    output = tmp_path / "runtime/gtm_pipeline/integration_observer_latest.json"
    assert output.exists()
    assert json.loads(output.read_text())["agent_id"] == GTM_AGENT_ID
    assert result["internal_research_review_count"] == 1
    assert result["payments_executed"] is False
    assert "extended_product_sources" in result
    assert result["extended_product_sources"]["execution_authority"] == "none"
