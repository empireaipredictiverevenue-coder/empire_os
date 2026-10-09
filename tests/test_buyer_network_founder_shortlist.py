from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)
from pathlib import Path


PATH = Path(
    "scripts/materialize_buyer_network_founder_shortlist.py"
)


def module():

    spec = spec_from_file_location(
        "buyer_founder_shortlist",
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


def strong_candidate():

    return {
        "domain":
            "buyer.example",

        "status":
            "READY_TO_APPROACH",

        "score":
            82,

        "already_known":
            False,

        "verticals":
            ["roofing"],

        "evidence": {
            "publisher_program":
                True,

            "active_demand":
                True,

            "integration":
                True,

            "economics":
                True,

            "compliance":
                True,

            "contactable":
                True,

            "negative_program":
                False,

            "evidence_count":
                6,
        },
    }


def test_file_exists():

    assert PATH.exists()


def test_strong_candidate_is_founder_review():

    mod = module()

    assert (
        mod.classify(
            strong_candidate()
        )
        == "A_FOUNDER_REVIEW"
    )


def test_missing_economics_is_gap():

    mod = module()

    candidate = strong_candidate()

    candidate["evidence"][
        "economics"
    ] = False

    assert (
        "verify_payout_economics"
        in mod.evidence_gaps(
            candidate
        )
    )


def test_never_invents_revenue():

    mod = module()

    result = mod.enrich(
        strong_candidate()
    )

    assert (
        result[
            "predictive_revenue"
        ]["forecast_revenue"]
        is None
    )


def test_outbound_remains_false():

    mod = module()

    result = mod.enrich(
        strong_candidate()
    )

    assert (
        result[
            "outbound_authority"
        ]
        is False
    )
