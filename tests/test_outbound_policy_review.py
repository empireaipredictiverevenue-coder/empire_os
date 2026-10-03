from empire_os.outbound_deliverability_snapshot import DeliverabilityThresholds
from empire_os.outbound_policy_review import build_policy_review_packet


def _ready(_):
    return {"posture": "READY", "mutation_authorized": False}


def test_review_packet_combines_shadow_and_counterfactual_evidence():
    contexts = [{"i": i} for i in range(25)]
    windows = [{
        "rows": [{
            "domain": "mail.example.com",
            "sent": 100,
            "delivered": 100,
            "bounced": 0,
            "complained": 0,
        }]
    } for _ in range(4)]

    result = build_policy_review_packet(
        current_manifest={"fingerprint": "a" * 64},
        candidate_manifest={"fingerprint": "b" * 64},
        contexts=contexts,
        historical_windows=windows,
        current_evaluator=_ready,
        candidate_evaluator=_ready,
        proposed_thresholds=DeliverabilityThresholds(),
    )

    assert result["status"] == "READY_FOR_REVIEW"
    assert result["shadow"]["samples"] == 25
    assert result["counterfactual"]["windows"] == 4
    assert result["activation_authorized"] is False
    assert result["review_packet_only"] is True


def test_identical_policy_fingerprint_is_no_change():
    result = build_policy_review_packet(
        current_manifest={"fingerprint": "a" * 64},
        candidate_manifest={"fingerprint": "a" * 64},
        contexts=[],
        historical_windows=[],
        current_evaluator=_ready,
        candidate_evaluator=_ready,
        proposed_thresholds=DeliverabilityThresholds(),
    )
    assert result["status"] == "NO_CHANGE"
    assert result["activation_authorized"] is False
