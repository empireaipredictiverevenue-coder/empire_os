from empire_os.outbound_counterfactual_replay import replay_threshold_policy
from empire_os.outbound_deliverability_snapshot import DeliverabilityThresholds


def test_counterfactual_replay_is_observe_only():
    result = replay_threshold_policy(
        [{
            "rows": [{
                "domain": "mail.example.com",
                "sent": 100,
                "delivered": 98,
                "bounced": 2,
                "complained": 0,
            }]
        }],
        proposed=DeliverabilityThresholds(
            green_bounce_rate=0.005,
            amber_bounce_rate=0.01,
            red_bounce_rate=0.015,
        ),
    )
    assert result["counts"]["HOLD"] == 1
    assert result["production_mutation_authorized"] is False
