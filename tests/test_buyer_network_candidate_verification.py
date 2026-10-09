from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)
from pathlib import Path


PATH = Path(
    "scripts/verify_buyer_network_candidates.py"
)


def module():

    spec = spec_from_file_location(
        "buyer_network_verification",
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


def test_verifier_exists():

    assert PATH.exists()


def test_signal_detection():

    mod = module()

    result = mod.signal_map(
        "publisher program pay per call "
        "API payout TCPA contact us"
    )

    assert result[
        "publisher_program"
    ]

    assert result[
        "active_demand"
    ]

    assert result[
        "integration"
    ]

    assert result[
        "economics"
    ]

    assert result[
        "compliance"
    ]

    assert result[
        "contactable"
    ]


def test_queries_are_domain_specific():

    mod = module()

    candidate = {
        "domain":
            "buyer.example",

        "status":
            "WATCH",

        "score":
            40,

        "verticals":
            ["roofing"],

        "evidence":
            {},
    }

    queries = mod.queries_for(
        candidate
    )

    assert queries

    assert all(
        "buyer.example"
        in query
        for query in queries
    )


def test_dangerous_callable_names_are_blocked():

    mod = module()

    for name in (
        "send",
        "persist",
        "activate",
        "delete",
        "write",
        "update",
        "create",
        "dispatch",
    ):
        assert (
            name
            in mod.BLOCKED_NAME_TERMS
        )


def test_internal_domains_fail_closed():

    mod = module()

    assert not mod.valid_public_buyer_domain(
        "empire.buyer"
    )

    assert not mod.valid_public_buyer_domain(
        "latest.json"
    )


def test_real_buyer_domains_allowed():

    mod = module()

    assert mod.valid_public_buyer_domain(
        "leadsmartinc.com"
    )

    assert mod.valid_public_buyer_domain(
        "callflowmarket.com"
    )


def test_search_tool_domains_fail_closed():

    mod = module()

    assert not mod.valid_public_buyer_domain(
        "ahrefs.com"
    )

    assert not mod.valid_public_buyer_domain(
        "semrush.com"
    )

    assert not mod.valid_public_buyer_domain(
        "serpapi.com"
    )


def test_verifier_is_bounded():

    mod = module()

    assert (
        mod.MAX_CANDIDATES
        <= 20
    )
