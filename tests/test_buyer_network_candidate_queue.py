from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)
from pathlib import Path


PATH = Path(
    "scripts/materialize_buyer_network_candidate_queue.py"
)


def module():

    spec = spec_from_file_location(
        "buyer_candidate_queue",
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


def test_file_exists():

    assert PATH.exists()


def test_domain_normalisation():

    mod = module()

    assert (
        mod.normalize_domain(
            "https://www.example.com/publishers"
        )
        == "example.com"
    )


def test_negative_evidence_rejects():

    mod = module()

    profile = {
        "verticals":
            {"roofing"},

        "queries":
            {"roofing buyers"},

        "runs":
            1,

        "evidence_lines": [
            "example.com publisher program closed",
        ],
    }

    result = mod.score_profile(
        "example.com",
        profile,
        set(),
    )

    assert (
        result["status"]
        == "REJECT"
    )


def test_search_presence_alone_not_ready():

    mod = module()

    profile = {
        "verticals":
            {"roofing"},

        "queries":
            {"roofing buyers"},

        "runs":
            1,

        "evidence_lines": [
            "https://example.com",
        ],
    }

    result = mod.score_profile(
        "example.com",
        profile,
        set(),
    )

    assert (
        result["status"]
        != "READY_TO_APPROACH"
    )


def test_strong_evidence_can_be_ready():

    mod = module()

    profile = {
        "verticals":
            {"roofing"},

        "queries":
            {
                "roofing publisher program",
                "buyer-network-active-verification",
            },

        "runs":
            1,

        "evidence_lines": [
            (
                "example.com publishers pay per call "
                "payout API TCPA contact"
            ),
        ],
    }

    result = mod.score_profile(
        "example.com",
        profile,
        set(),
    )

    assert (
        result["status"]
        == "READY_TO_APPROACH"
    )
