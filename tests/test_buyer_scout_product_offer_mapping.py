from empire_os.buyer_discovery import (
    build_candidate,
)
from empire_os.buyer_review_materializer import (
    REVIEWABLE_OFFER_KEYS,
)


def test_private_capital_product_survives_canonicalization():
    candidate = build_candidate({
        "id": "primus-test",
        "business_name": "Primus Capital",
        "niche": "private_capital_rollup",
        "website": "https://primuscapital.com/",
    })

    assert (
        candidate.offer_key
        == "private_capital_rollup"
    )

    assert (
        "private_capital_rollup"
        in REVIEWABLE_OFFER_KEYS
    )


def test_permit_product_survives_canonicalization():
    candidate = build_candidate({
        "id": "cooper-test",
        "business_name": "CooperBuild",
        "niche": "permit_intelligence",
        "website": "https://cooperbuild.com/",
    })

    assert (
        candidate.offer_key
        == "permit_intelligence"
    )

    assert (
        "permit_intelligence"
        in REVIEWABLE_OFFER_KEYS
    )
