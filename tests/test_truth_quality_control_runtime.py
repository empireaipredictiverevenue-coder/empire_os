from pathlib import Path

from empire_os.truth_quality_control import (
    ALLOWED_BUYER_TLDS,
    input_domain_decision,
)


RUNNER = Path(
    "scripts/run_truth_quality_control.py"
)


def test_runner_exists():

    assert RUNNER.exists()


def test_detection_contract_has_quarantine():

    text = RUNNER.read_text()

    assert (
        "buyer_quarantine_latest.json"
        in text
    )

    assert (
        "buyer_output_blocked_latest.json"
        in text
    )


def test_no_outbound_execution():

    text = RUNNER.read_text()

    assert (
        '"outbound":\n                False'
        in text
        or
        '"outbound":\n                        False'
        in text
    )


def test_good_candidate_can_pass():

    result = input_domain_decision(
        "realbuyer.com",

        peers=[
            "realbuyer.com"
        ],

        evidence_lines=[
            "publisher program pay per call",
            "independent compliance evidence",
        ],

        source_ids=[
            "direct-site",
            "public-research",
        ],

        allowed_tlds=
            ALLOWED_BUYER_TLDS,
    )

    assert result.verdict == "PASS"

    assert result.action_allowed
