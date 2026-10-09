from empire_os.detection_fusion import (
    ControlSignal,
    double_counted_events,
    duplicate_keys,
    entity_risk,
    fuse_signals,
    lane_verdict,
    task_collisions,
)


def test_signal_fusion_deduplicates():

    signals = [
        ControlSignal(
            code=
                "MISSING_EVIDENCE",
            severity=
                "MEDIUM",
            entity=
                "buyer.com",
            source=
                "input",
            reason=
                "Missing proof",
        ),
        ControlSignal(
            code=
                "MISSING_EVIDENCE",
            severity=
                "HIGH",
            entity=
                "buyer.com",
            source=
                "output",
            reason=
                "Missing proof",
        ),
    ]

    fused = fuse_signals(
        signals
    )

    assert len(fused) == 1
    assert fused[0][
        "severity"
    ] == "HIGH"

    assert fused[0][
        "source_independence_count"
    ] == 2


def test_entity_risk():

    fused = fuse_signals(
        [
            ControlSignal(
                code=
                    "STATE_CONFLICT",
                severity=
                    "CRITICAL",
                entity=
                    "buyer.com",
                source=
                    "queue",
                reason=
                    "conflict",
                blocks_entity=
                    True,
            )
        ]
    )

    risk = entity_risk(
        fused
    )

    assert risk[0][
        "held"
    ]

    assert risk[0][
        "max_severity"
    ] == "CRITICAL"


def test_duplicate_keys():

    found = duplicate_keys(
        [
            {"domain": "a.com"},
            {"domain": "a.com"},
            {"domain": "b.com"},
        ],
        key="domain",
    )

    assert found == {
        "a.com": 2
    }


def test_task_collision_detection():

    result = task_collisions(
        [
            {
                "task_id":
                    "task-1",
                "work_fingerprint":
                    "same-work",
            },
            {
                "task_id":
                    "task-2",
                "work_fingerprint":
                    "same-work",
            },
        ]
    )

    assert result[
        "same-work"
    ] == [
        "task-1",
        "task-2",
    ]


def test_double_count_detection():

    result = double_counted_events(
        [
            {
                "canonical_event_id":
                    "payment-1"
            },
            {
                "canonical_event_id":
                    "payment-1"
            },
        ]
    )

    assert result[
        "payment-1"
    ] == 2


def test_lane_verdict():

    assert lane_verdict(
        []
    ) == "PASS"

    assert lane_verdict(
        [
            {
                "severity":
                    "HIGH"
            }
        ]
    ) == "HOLD_FOR_REMEDIATION"

    assert lane_verdict(
        [
            {
                "severity":
                    "CRITICAL"
            }
        ]
    ) == "BLOCK"
