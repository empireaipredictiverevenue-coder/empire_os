from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)
from pathlib import Path


VERIFY = Path(
    "scripts/verify_buyer_network_candidates.py"
)

QUEUE = Path(
    "scripts/materialize_buyer_network_candidate_queue.py"
)


def load(path, name):
    spec = spec_from_file_location(
        name,
        path,
    )

    mod = module_from_spec(spec)

    assert spec.loader is not None
    spec.loader.exec_module(mod)

    return mod


def test_internal_domains_rejected():

    mod = load(
        VERIFY,
        "verification_hardening_a",
    )

    assert not mod.valid_public_buyer_domain(
        "empire.buyer"
    )

    assert not mod.valid_public_buyer_domain(
        "empire.predictive"
    )

    assert not mod.valid_public_buyer_domain(
        "latest.json"
    )

    assert not mod.valid_public_buyer_domain(
        "2026-09-23.md"
    )


def test_known_search_tools_rejected():

    mod = load(
        VERIFY,
        "verification_hardening_b",
    )

    assert not mod.valid_public_buyer_domain(
        "ahrefs.com"
    )

    assert not mod.valid_public_buyer_domain(
        "semrush.com"
    )

    assert not mod.valid_public_buyer_domain(
        "serpapi.com"
    )


def test_real_candidate_domain_allowed():

    mod = load(
        VERIFY,
        "verification_hardening_c",
    )

    assert mod.valid_public_buyer_domain(
        "callflowmarket.com"
    )

    assert mod.valid_public_buyer_domain(
        "leadsmartinc.com"
    )


def test_verifier_does_not_bind_query_as_evidence():

    text = VERIFY.read_text()

    assert (
        'f"{domain} {query} {text}"'
        not in text
    )

    assert (
        "Never count our own verification query as evidence."
        in text
    )


def test_ready_requires_active_verification():

    mod = load(
        QUEUE,
        "queue_hardening",
    )

    profile = {
        "verticals": {"roofing"},
        "queries": {
            "contextual-runtime-buyer-evidence",
        },
        "runs": 1,
        "evidence_lines": [
            (
                "buyer.example publishers "
                "pay per call payout API "
                "TCPA contact"
            )
        ],
    }

    result = mod.score_profile(
        "buyer.example",
        profile,
        set(),
    )

    assert (
        result["status"]
        == "VERIFY_REQUIREMENTS"
    )

    profile["queries"].add(
        "buyer-network-active-verification"
    )

    result = mod.score_profile(
        "buyer.example",
        profile,
        set(),
    )

    assert (
        result["status"]
        == "READY_TO_APPROACH"
    )
