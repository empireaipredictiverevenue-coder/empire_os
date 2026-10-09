from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)
from pathlib import Path


PATH = Path(
    "scripts/materialize_buyer_network_founder_review_packets.py"
)


def module():

    spec = spec_from_file_location(
        "buyer_review",
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


def test_real_domain():

    assert module().valid_domain(
        "leadsmartinc.com"
    )


def test_internal_domain():

    assert not module().valid_domain(
        "empire.buyer"
    )


def test_search_tool():

    assert not module().valid_domain(
        "semrush.com"
    )


def test_genuine_buyer_role():

    mod = module()

    assert mod.genuine(
        {
            "evidence": {
                "publisher_program":
                    True,

                "active_demand":
                    True,

                "integration":
                    True,

                "negative_program":
                    False,
            }
        }
    )


def test_tooling_only_not_genuine():

    mod = module()

    assert not mod.genuine(
        {
            "evidence": {
                "integration":
                    True,

                "economics":
                    True,

                "contactable":
                    True,
            }
        }
    )
