from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)
from pathlib import Path


PATH = Path(
    "scripts/materialize_buyer_network_contextual_evidence.py"
)


def module():

    spec = spec_from_file_location(
        "buyer_contextual_evidence",
        PATH,
    )

    mod = module_from_spec(
        spec
    )

    assert spec.loader is not None

    spec.loader.exec_module(
        mod
    )

    return mod


def test_exists():
    assert PATH.exists()


def test_extract_domain():

    mod = module()

    assert (
        "buyer.example"
        in mod.domains(
            "https://buyer.example/publishers"
        )
    )


def test_signal_categories():

    mod = module()

    matched = mod.match_signals(
        "publisher program pay per call "
        "API payout TCPA contact"
    )

    assert matched[
        "publisher"
    ]

    assert matched[
        "demand"
    ]

    assert matched[
        "integration"
    ]

    assert matched[
        "economics"
    ]

    assert matched[
        "compliance"
    ]


def test_vertical_detection():

    mod = module()

    assert (
        "roofing"
        in mod.detect_verticals(
            "roofing pay per call"
        )
    )


def test_unrelated_text_has_no_buyer_signals():

    mod = module()

    matched = mod.match_signals(
        "ordinary company website"
    )

    assert not any(
        matched[
            category
        ]

        for category
        in (
            "publisher",
            "demand",
            "integration",
            "economics",
        )
    )
