from pathlib import Path

from empire_os.architecture_gap_radar import (
    REQUIRED_CONTROLS,
)


RUNNER = Path(
    "scripts/run_architecture_gap_radar.py"
)


def test_runner_exists():

    assert RUNNER.exists()


def test_required_controls_cover_core_gates():

    for name in (
        "input_quality_detection",
        "output_quality_detection",
        "quarantine",
        "canonical_identity_resolution",
        "active_verification",
        "ranked_queue",
        "verification_backlog",
        "founder_review_gate",
    ):

        assert name in REQUIRED_CONTROLS


def test_runtime_outputs_defined():

    text = RUNNER.read_text()

    assert (
        "architecture_gap_latest.json"
        in text
    )

    assert (
        "detection_fusion_latest.json"
        in text
    )


def test_no_execution_authority():

    text = RUNNER.read_text()

    assert (
        '"authority":\n                "OBSERVE"'
        in text
    )
