# EMPIRE_WAVE_091C
from pathlib import Path


def test_completion_runner_never_claims_write_authority():

    text = Path(
        "scripts/complete_economic_memory_controls.py"
    ).read_text()

    forbidden = (
        'completion["action_allowed"]',
        'completion["execution_authority"]',
        'completion["founder_gate"]',
    )

    for token in forbidden:
        assert token not in text


def test_completion_requires_real_outcome_id():

    text = Path(
        "scripts/complete_economic_memory_controls.py"
    ).read_text()

    assert (
        'first_link.get('
        in text
    )

    assert (
        '"outcome_id"'
        in text
    )
