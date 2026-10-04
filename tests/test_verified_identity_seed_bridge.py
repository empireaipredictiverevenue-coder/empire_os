from pathlib import Path

from empire_os.verified_identity_seed_bridge import (
    build_verified_identity_seed_records,
)


ROOT = Path(
    __file__
).resolve().parents[1]


def fixtures(
    *,
    state_status="identity_verified",
    identity_decision="IDENTITY_VERIFIED",
    confidence=0.91,
    first_party=True,
):
    queue = {
        "jobs": {
            "job-1": {
                "status":
                    "completed",
                "source_ref":
                    "signal_inbox:sig-1",
                "payload": {
                    "signal_id":
                        "sig-1",
                    "source":
                        "reddit_intent",
                    "title":
                        "Need more qualified roofing appointments",
                    "text":
                        "Google Ads has not been consistently profitable.",
                    "url":
                        "https://reddit.com/r/Roofing/example",
                    "niche":
                        "roofing",
                    "metro":
                        "Phoenixville PA",
                    "intent_score":
                        86,
                    "intent_band":
                        "high",
                    "pain_points": [
                        "lead_generation",
                        "revenue_growth",
                    ],
                    "observed_at":
                        "2026-10-04T07:45:00+00:00",
                },
                "result": {
                    "decision":
                        "RESOLVE_IDENTITY",
                    "governance": {
                        "execution_authority":
                            "none",
                    },
                    "output": {
                        "intent_brain": {
                            "niche":
                                "roofing",
                        },
                    },
                },
            },
        },
    }

    state = {
        "execution_authority":
            "none",
        "jobs": {
            "job-1": {
                "status":
                    state_status,
                "intent_decision":
                    "RESOLVE_IDENTITY",
                "business_decision":
                    "BUSINESS_IDENTITY_VERIFIED",
                "identity_decision":
                    identity_decision,
                "business_name":
                    "3 Point Contracting LLC",
                "website":
                    "https://3pointcontracting.com",
                "execution_authority":
                    "none",
                "first_party_result": {
                    "decision":
                        identity_decision,
                    "governance": {
                        "execution_authority":
                            "none",
                    },
                    "output": {
                        "business_name":
                            "3 Point Contracting LLC",
                        "website":
                            "https://3pointcontracting.com",
                        "business_site_verified":
                            True,
                        "identity_verified":
                            (
                                identity_decision
                                == "IDENTITY_VERIFIED"
                            ),
                        "decision_maker": {
                            "name":
                                "Wade Rudzik",
                            "title":
                                "Owner",
                            "source":
                                "first_party_site",
                            "source_url":
                                "https://3pointcontracting.com/about",
                            "confidence":
                                confidence,
                            "first_party":
                                first_party,
                        },
                    },
                },
            },
        },
    }

    return state, queue


def test_verified_identity_becomes_buyer_scout_seed():
    state, queue = fixtures()

    seeds = (
        build_verified_identity_seed_records(
            state,
            queue,
        )
    )

    assert len(seeds) == 1

    seed = seeds[0]

    assert (
        seed[
            "business_name"
        ]
        == "3 Point Contracting LLC"
    )

    assert (
        seed[
            "website"
        ]
        == "https://3pointcontracting.com"
    )

    assert (
        seed[
            "seed_canonical_identity_verified"
        ]
        is True
    )

    assert (
        seed[
            "seed_intent_signal_id"
        ]
        == "sig-1"
    )

    assert (
        seed[
            "seed_first_party_people"
        ][0][
            "name"
        ]
        == "Wade Rudzik"
    )

    assert (
        seed[
            "seed_first_party_people"
        ][0][
            "first_party"
        ]
        is True
    )

    assert (
        seed[
            "outreach_authorized"
        ]
        is False
    )

    assert (
        seed[
            "execution_authority"
        ]
        == "none"
    )


def test_non_verified_identity_does_not_seed_buyer_scout():
    state, queue = fixtures(
        state_status=
            "identity_unresolved",
        identity_decision=
            "IDENTITY_UNRESOLVED",
    )

    seeds = (
        build_verified_identity_seed_records(
            state,
            queue,
        )
    )

    assert seeds == []


def test_weak_person_identity_does_not_seed_buyer_scout():
    state, queue = fixtures(
        confidence=0.69,
    )

    seeds = (
        build_verified_identity_seed_records(
            state,
            queue,
        )
    )

    assert seeds == []


def test_non_first_party_person_does_not_seed_buyer_scout():
    state, queue = fixtures(
        first_party=False,
    )

    seeds = (
        build_verified_identity_seed_records(
            state,
            queue,
        )
    )

    assert seeds == []


def test_production_runner_contains_verified_identity_bridge():
    text = (
        ROOT
        / "scripts"
        / "run_buyer_acquisition_scout.py"
    ).read_text()

    assert (
        "load_verified_identity_seed_records"
        in text
    )

    assert (
        "verified_identity_seeds"
        in text
    )


def test_scout_preserves_verified_identity_marker():
    text = (
        ROOT
        / "empire_os"
        / "buyer_acquisition_scout.py"
    ).read_text()

    assert (
        '"canonical_identity_verified"'
        in text
    )

    assert (
        "seed_canonical_identity_verified"
        in text
    )
