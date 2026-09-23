from empire_os.media_algorithm_intelligence import (
    DistributionObservation,
    analyse_distribution,
    build_algorithm_hypothesis_packet,
    build_recommendation_chain_packet,
    build_surface_baseline,
    detect_distribution_drift,
)


def test_distribution_engine_observes_surfaces_without_fake_rank_probability():
    result = analyse_distribution(
        (
            DistributionObservation(
                video_id="video-1",
                surface="BROWSE",
                evidence_refs=("youtube:analytics:1",),
                impressions=10000,
                views=800,
                watch_time_minutes=3000,
                average_view_percentage=0.52,
                subscribers_gained=30,
            ),
            DistributionObservation(
                video_id="video-1",
                surface="SEARCH",
                evidence_refs=("youtube:analytics:2",),
                impressions=2500,
                views=400,
                watch_time_minutes=1700,
                average_view_percentage=0.61,
                subscribers_gained=22,
                query="ai lead generation",
            ),
        )
    )

    assert result["surface_count"] == 2
    assert result["private_platform_weights_known"] is False
    assert result["ranking_probability_created"] is False
    assert result["distribution_observation_only"] is True
    assert result["manipulative_engagement_authorized"] is False
    assert result["execution_authority"] == "none"


def test_surface_baseline_and_drift_do_not_claim_platform_algorithm_change():
    historical = (
        analyse_distribution(
            (
                DistributionObservation(
                    video_id="v1",
                    surface="BROWSE",
                    evidence_refs=("a:1",),
                    impressions=1000,
                    views=100,
                    average_view_percentage=0.5,
                    subscribers_gained=5,
                ),
            )
        ),
        analyse_distribution(
            (
                DistributionObservation(
                    video_id="v2",
                    surface="BROWSE",
                    evidence_refs=("a:2",),
                    impressions=1000,
                    views=120,
                    average_view_percentage=0.52,
                    subscribers_gained=6,
                ),
            )
        ),
        analyse_distribution(
            (
                DistributionObservation(
                    video_id="v3",
                    surface="BROWSE",
                    evidence_refs=("a:3",),
                    impressions=1000,
                    views=110,
                    average_view_percentage=0.51,
                    subscribers_gained=5,
                ),
            )
        ),
    )

    baseline = build_surface_baseline(historical)

    current = analyse_distribution(
        (
            DistributionObservation(
                video_id="v4",
                surface="BROWSE",
                evidence_refs=("a:4",),
                impressions=1000,
                views=250,
                average_view_percentage=0.66,
                subscribers_gained=20,
            ),
        )
    )

    drift = detect_distribution_drift(
        current=current,
        baseline=baseline,
        material_delta=0.20,
    )

    assert drift["material_change_count"] >= 1
    assert drift["state"] == "DISTRIBUTION_SHIFT_CANDIDATE"
    assert drift["platform_algorithm_change_claimed"] is False
    assert drift["causal_explanation_created"] is False
    assert drift["experiment_review_required"] is True


def test_recommendation_chain_uses_observed_suggested_edges_only():
    packet = build_recommendation_chain_packet(
        (
            DistributionObservation(
                video_id="target-1",
                surface="SUGGESTED",
                source_video_id="source-1",
                evidence_refs=("youtube:suggested:1",),
                views=200,
                engaged_views=160,
            ),
            DistributionObservation(
                video_id="target-2",
                surface="SEARCH",
                evidence_refs=("youtube:search:1",),
                views=100,
            ),
        )
    )

    assert packet["edge_count"] == 1
    assert packet["edges"][0]["source_video_id"] == "source-1"
    assert packet["edges"][0]["target_video_id"] == "target-1"
    assert packet["graph_owner"] == "intelligence_fabric"
    assert packet["observed_edges_only"] is True
    assert packet["private_recommendation_graph_claimed"] is False


def test_algorithm_hypothesis_delegates_review_to_existing_systems():
    distribution = analyse_distribution(
        (
            DistributionObservation(
                video_id="video-1",
                surface="BROWSE",
                evidence_refs=("youtube:analytics:1",),
                impressions=5000,
                views=500,
            ),
        )
    )

    packet = build_algorithm_hypothesis_packet(
        video_id="video-1",
        distribution=distribution,
        retention_ref="retention:video-1",
        creative_package_ref="creative:video-1",
        audience_cluster_ref="audience:founders",
        evidence_refs=("youtube:analytics:1", "retention:video-1"),
    )

    assert packet["ranking_probability"] is None
    assert packet["private_algorithm_weights_known"] is False
    assert packet["causal_claim_created"] is False
    assert packet["review_owner"] == "experiment_intelligence"
    assert packet["portfolio_owner"] == "quant_brain"
    assert packet["public_action_authorized"] is False
    assert packet["execution_authority"] == "none"
