import pytest

from empire_os.media_analytics import (
    RetentionPoint,
    analyse_retention,
    normalize_owned_channel_analytics,
    shorts_to_long_form_funnel,
)
from empire_os.media_attention_graph import (
    AttentionEdge,
    AttentionNode,
    build_attention_graph_packet,
)
from empire_os.media_attribution import (
    MediaAttributionLink,
    build_media_attribution_packet,
    content_value_feature_packet,
)
from empire_os.media_experiments import (
    MediaExperiment,
    prepare_media_experiment,
    record_media_experiment_outcome,
)
from empire_os.media_publishing import (
    MediaCalendarItem,
    build_media_calendar,
    prepare_publish_package,
    publishing_adapter_contract,
)


def test_calendar_and_publish_package_never_publish():
    calendar = build_media_calendar([
        MediaCalendarItem(
            item_id="cal-1",
            channel_id="empire-ai",
            content_type="youtube_long_form",
            production_state="QC",
            priority="P1",
            topic_cluster="AI automation",
            content_ref="content:1",
        )
    ])

    assert calendar["item_count"] == 1
    assert calendar["automatic_public_publish"] is False
    assert calendar["execution_authority"] == "none"

    package = prepare_publish_package(
        content_ref="content:1",
        rendered_asset_ref="asset:video:1",
        thumbnail_ref="asset:thumb:1",
        metadata_ref="metadata:1",
        channel_id="empire-ai",
        rights_manifest={
            "production_id": "prod-1",
            "commercial_release_ready": True,
        },
        qc_gate={
            "publish_ready_candidate": True,
        },
    )

    assert package["publish_candidate_ready"] is True
    assert package["public_publish_authorized"] is False
    assert package["publish_action_performed"] is False
    assert package["execution_authority"] == "none"

    adapter = publishing_adapter_contract()
    assert adapter["live_actions_enabled"] is False
    assert adapter["automatic_publish"] is False


def test_owned_analytics_preserves_platform_revenue_separation():
    row = normalize_owned_channel_analytics(
        {
            "channel_id": "empire-ai",
            "video_id": "video-1",
            "impressions": 10000,
            "impressions_ctr": 0.06,
            "views": 1500,
            "engaged_views": 1100,
            "watch_time_minutes": 5000,
            "subscribers_gained": 45,
            "estimated_revenue": 23.5,
        },
        evidence_refs=("youtube:analytics:video-1",),
    )

    assert row["metrics"]["engaged_views"] == 1100.0
    assert row["estimated_revenue_is_platform_metric_only"] is True
    assert row["revenue_truth_owner"] == "revenue_pulse"
    assert row["actual_revenue"] is False


def test_retention_drop_outputs_hypotheses_not_causal_claims():
    result = analyse_retention(
        (
            RetentionPoint(
                second=0,
                audience_retention=1.0,
                scene_id="s1",
            ),
            RetentionPoint(
                second=30,
                audience_retention=0.88,
                scene_id="s2",
            ),
            RetentionPoint(
                second=60,
                audience_retention=0.70,
                scene_id="s3",
            ),
        ),
        scene_metadata={
            "s3": {
                "static_frame": True,
                "explanation_seconds": 20,
            }
        },
    )

    assert result["drop_count"] >= 1
    assert result["hypotheses_not_causal_findings"] is True
    assert all(
        row["causal_claim"] is False
        for row in result["drops"]
    )
    assert result["experiment_review_owner"] == "experiment_intelligence"


def test_shorts_funnel_is_not_raw_views_only():
    result = shorts_to_long_form_funnel(
        short_views=5000,
        subscribers_gained=80,
        channel_visits=400,
        long_form_continuations=140,
        returning_viewers=90,
        website_visits=20,
        evidence_refs=("youtube:short:1",),
    )

    assert result["optimized_for_raw_views_only"] is False
    assert result["actual_revenue"] is False


def test_media_experiments_delegate_analysis_and_do_not_declare_winner():
    experiment = MediaExperiment(
        experiment_id="exp-1",
        channel_id="empire-ai",
        hypothesis="A clearer thumbnail may improve CTR.",
        variable="thumbnail",
        control_ref="thumb:a",
        candidate_ref="thumb:b",
        primary_metric="impressions_ctr",
    )

    proposal = prepare_media_experiment(experiment)
    assert proposal["state"] == "PROPOSAL_ONLY"
    assert proposal["causal_claim_created"] is False
    assert proposal["public_mutation_authorized"] is False

    outcome = record_media_experiment_outcome(
        experiment,
        control_metrics={"impressions_ctr": 0.04},
        candidate_metrics={"impressions_ctr": 0.055},
        sample_sufficient=True,
    )
    assert outcome["result_state"] == (
        "READY_FOR_EXPERIMENT_INTELLIGENCE_REVIEW"
    )
    assert outcome["winner_declared"] is False
    assert outcome["causal_claim_created"] is False
    assert outcome["analysis_owner"] == "experiment_intelligence"


def test_attention_graph_is_packet_for_existing_intelligence_fabric():
    nodes = (
        AttentionNode(
            node_id="video:1",
            node_type="VIDEO",
            label="Empire video",
            evidence_refs=("youtube:video:1",),
        ),
        AttentionNode(
            node_id="topic:1",
            node_type="TOPIC",
            label="AI automation",
            evidence_refs=("search:topic:1",),
        ),
    )
    edges = (
        AttentionEdge(
            edge_id="edge:1",
            source_node_id="video:1",
            target_node_id="topic:1",
            edge_type="ABOUT",
            evidence_refs=("content:1",),
        ),
    )

    packet = build_attention_graph_packet(
        nodes=nodes,
        edges=edges,
    )

    assert packet["node_count"] == 2
    assert packet["edge_count"] == 1
    assert packet["graph_owner"] == "intelligence_fabric"
    assert packet["second_graph_created"] is False
    assert packet["actual_revenue"] is False


def test_attention_graph_rejects_inference_only_commercial_edges():
    nodes = (
        AttentionNode(
            node_id="video:1",
            node_type="VIDEO",
            label="Video",
            evidence_refs=("youtube:1",),
        ),
        AttentionNode(
            node_id="revenue:1",
            node_type="REVENUE",
            label="Revenue",
            evidence_refs=("revenue:1",),
        ),
    )

    with pytest.raises(ValueError, match="commercial graph edges"):
        build_attention_graph_packet(
            nodes=nodes,
            edges=(
                AttentionEdge(
                    edge_id="edge:revenue",
                    source_node_id="video:1",
                    target_node_id="revenue:1",
                    edge_type="SUPPORTED_REVENUE",
                    evidence_refs=("guess:1",),
                    inferred=True,
                ),
            ),
        )


def test_media_revenue_attribution_requires_real_revenue_evidence():
    link = MediaAttributionLink(
        link_id="attr-1",
        source_type="VIDEO",
        source_id="video-1",
        target_type="REVENUE",
        target_id="revenue-event-1",
        evidence_refs=("session:utm:1", "revenue:event:1"),
        attribution_method="observed_tracking_chain",
        confidence=0.9,
    )

    with pytest.raises(ValueError, match="revenue_evidence_refs"):
        build_media_attribution_packet(
            links=(link,),
            recognized_revenue_cents=25000,
        )

    packet = build_media_attribution_packet(
        links=(link,),
        recognized_revenue_cents=25000,
        revenue_evidence_refs=("revenue:event:1",),
    )

    assert packet["attributed_revenue_state"] == (
        "OBSERVED_EVIDENCE_LINKED"
    )
    assert packet["revenue_truth_owner"] == "revenue_pulse"
    assert packet["actual_revenue_claim_created_by_media_os"] is False


def test_content_value_features_delegate_scoring_to_quant():
    packet = content_value_feature_packet(
        views=10000,
        watch_time_minutes=40000,
        subscribers_gained=200,
        leads=5,
        recognized_revenue_cents=50000,
        production_cost_cents=10000,
        evidence_refs=("analytics:1", "revenue:1"),
    )

    assert packet["score"] is None
    assert packet["score_owner"] == "quant_brain"
    assert packet["views_are_not_revenue"] is True
    assert packet["subscriber_gain_is_not_revenue"] is True
    assert packet["actual_revenue"] is False
