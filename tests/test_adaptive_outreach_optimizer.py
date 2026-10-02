from empire_os.adaptive_outreach_optimizer import (
    _bucket,
    build_performance_snapshot,
    select_message_arms,
)


SUBJECTS = (
    "company_only",
    "company_question",
    "one_thing",
)
BODIES = (
    "plain_one_page",
    "direct_observation",
    "simple_question",
)


def test_cold_start_is_deterministic_balanced_learning():
    first = select_message_arms(
        assignment_key="review-123",
        subject_arm_ids=SUBJECTS,
        body_arm_ids=BODIES,
        offer_key="managed_service",
        niche="roofing",
        decision_role="economic_buyer",
        snapshot={},
    )
    second = select_message_arms(
        assignment_key="review-123",
        subject_arm_ids=SUBJECTS,
        body_arm_ids=BODIES,
        offer_key="managed_service",
        niche="roofing",
        decision_role="economic_buyer",
        snapshot={},
    )
    assert first == second
    assert first["subject_arm"] in SUBJECTS
    assert first["body_arm"] in BODIES
    assert first["subject_selection"]["mode"] == "balanced_learning"
    assert first["body_selection"]["mode"] == "balanced_learning"
    assert first["uses_open_tracking"] is False


def test_mature_global_evidence_exploits_best_arm():
    snapshot = {
        "segments": {
            "__global__": {
                "delivered": 80,
                "subject_arms": {
                    "company_only": {
                        "delivered": 20,
                        "commercial_replies": 1,
                        "stop_replies": 2,
                    },
                    "company_question": {
                        "delivered": 20,
                        "commercial_replies": 6,
                        "stop_replies": 0,
                    },
                    "one_thing": {
                        "delivered": 20,
                        "commercial_replies": 2,
                        "stop_replies": 1,
                    },
                },
                "body_arms": {
                    "plain_one_page": {
                        "delivered": 20,
                        "commercial_replies": 1,
                        "stop_replies": 2,
                    },
                    "direct_observation": {
                        "delivered": 20,
                        "commercial_replies": 5,
                        "stop_replies": 0,
                    },
                    "simple_question": {
                        "delivered": 20,
                        "commercial_replies": 2,
                        "stop_replies": 1,
                    },
                },
            },
        },
    }
    key = next(
        f"review-{index}"
        for index in range(1000)
        if _bucket(f"explore:subject_arms:review-{index}") >= 2000
        and _bucket(f"explore:body_arms:review-{index}") >= 2000
    )
    result = select_message_arms(
        assignment_key=key,
        subject_arm_ids=SUBJECTS,
        body_arm_ids=BODIES,
        offer_key="managed_service",
        niche="roofing",
        decision_role="economic_buyer",
        snapshot=snapshot,
    )
    assert result["subject_arm"] == "company_question"
    assert result["body_arm"] == "direct_observation"
    assert result["subject_selection"]["mode"] == "adaptive_exploit"
    assert result["body_selection"]["mode"] == "adaptive_exploit"


def test_snapshot_learns_replies_and_stop_signals_only_from_labelled_arms():
    records = [
        {
            "delivered": True,
            "classification": "positive",
            "metadata": {
                "adaptive_outreach": {
                    "exact_segment": "managed_service|roofing|economic_buyer",
                    "subject_arm": "company_question",
                    "body_arm": "direct_observation",
                },
            },
        },
        {
            "delivered": True,
            "classification": "unsubscribe",
            "metadata": {
                "adaptive_outreach": {
                    "exact_segment": "managed_service|roofing|economic_buyer",
                    "subject_arm": "company_only",
                    "body_arm": "plain_one_page",
                },
            },
        },
        {
            "delivered": True,
            "classification": None,
            "metadata": {
                "adaptive_outreach": {
                    "exact_segment": "managed_service|roofing|economic_buyer",
                    "subject_arm": "company_question",
                    "body_arm": "direct_observation",
                },
            },
        },
        {
            "delivered": True,
            "classification": "positive",
            "metadata": {},
        },
    ]
    payload = build_performance_snapshot(
        records,
        generated_at="2026-10-02T20:00:00+00:00",
    )
    assert payload["labelled_intent_count"] == 3
    assert payload["unlabelled_history_count"] == 1
    global_row = payload["segments"]["__global__"]
    assert global_row["delivered"] == 3
    assert (
        global_row["subject_arms"]["company_question"]["commercial_replies"]
        == 1
    )
    assert (
        global_row["subject_arms"]["company_only"]["stop_replies"]
        == 1
    )
    assert payload["uses_open_tracking"] is False
    assert payload["winner_claim_allowed"] is False


def test_specific_segment_is_used_only_after_minimum_evidence():
    exact = "managed_service|roofing|economic_buyer"
    snapshot = {
        "segments": {
            exact: {
                "delivered": 15,
                "subject_arms": {},
                "body_arms": {},
            },
            "__global__": {
                "delivered": 80,
                "subject_arms": {},
                "body_arms": {},
            },
        },
    }
    result = select_message_arms(
        assignment_key="review-segment",
        subject_arm_ids=SUBJECTS,
        body_arm_ids=BODIES,
        offer_key="managed_service",
        niche="roofing",
        decision_role="economic_buyer",
        snapshot=snapshot,
    )
    assert result["subject_selection"]["segment"] == "__global__"
    assert result["body_selection"]["segment"] == "__global__"

    snapshot["segments"][exact]["delivered"] = 16
    result = select_message_arms(
        assignment_key="review-segment",
        subject_arm_ids=SUBJECTS,
        body_arm_ids=BODIES,
        offer_key="managed_service",
        niche="roofing",
        decision_role="economic_buyer",
        snapshot=snapshot,
    )
    assert result["subject_selection"]["segment"] == exact
    assert result["body_selection"]["segment"] == exact
