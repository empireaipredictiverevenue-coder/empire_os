from pathlib import Path
import re


PAGE = Path(
    "templates/lead_smart/roofing/page.tsx"
)


def source() -> str:
    assert PAGE.exists()
    return PAGE.read_text()


def normalized(value: str) -> str:
    return " ".join(value.split())


def test_roofing_page_contains_required_lead_smart_disclosure():
    text = normalized(source())

    required = normalized(
        """
        This site is a free service to assist homeowners in connecting
        with local service contractors. All contractors are independent
        and this site does not warrant or guarantee any work performed.
        It is the responsibility of the homeowner to verify that the
        hired contractor furnishes the necessary license and insurance
        required for the work being performed. All persons depicted in
        a photo or video are actors or models and not contractors listed
        on this site.
        """
    )

    assert required in text


def test_roofing_page_tracking_number_is_bound_but_fail_closed():
    text = source()

    assert 'const TRACKING_NUMBER_E164 = "+18883579305";' in text
    assert 'const TRACKING_NUMBER_DISPLAY = "(888) 357-9305";' in text

    assert "const TRACKING_VERIFIED = false;" in text
    assert "const ZIP_COVERAGE_VERIFIED = false;" in text

    compact = " ".join(
        text.split()
    )

    assert (
        "TRACKING_VERIFIED && "
        "ZIP_COVERAGE_VERIFIED"
        in compact
    )

    # The public asset remains preactivation/noindex.
    assert "robots: { index: false, follow: false }" in text

    # No unconditional literal telephone href may exist.
    assert re.search(r'href=["\']tel:', text, re.I) is None

    # The only call path is controlled by CALL_ROUTE_ENABLED.
    assert "{CALL_ROUTE_ENABLED ? (" in text
    assert "Call route pending verification" in text


def test_roofing_page_excludes_prohibited_marketing_claims():
    text = source().lower()

    forbidden = (
        "free quote",
        "free quotes",
        "free estimate",
        "free estimates",
        "discount",
        "rebate",
        "promotion",
        "lowest price",
        "best roofer",
        "top-rated roofer",
        "facebook marketplace",
        "craigslist",
    )

    for phrase in forbidden:
        assert phrase not in text, phrase

    # No synthetic review/testimonial treatment.
    assert "★★★★★" not in text
    assert "customer testimonial" not in text
    assert "verified customer review" not in text


def test_roofing_page_is_consumer_initiated_and_zip_gated():
    text = source()

    assert "property ZIP code" in text
    assert "ZIP_COVERAGE_VERIFIED" in text

    assert (
        "you decide whether to place the call"
        in text.lower()
    )

    assert (
        "homeowner-initiated service request"
        in text.lower()
    )



def test_roofing_cta_requires_tracking_zip_routing_and_founder_authority():
    text = source()

    assert (
        'const TRACKING_VERIFIED = false;'
        in text
    )

    assert (
        'const ZIP_COVERAGE_VERIFIED = false;'
        in text
    )

    assert (
        'const ROUTING_VERIFIED = false;'
        in text
    )

    assert (
        'const FOUNDER_LIVE_TRAFFIC_AUTHORIZED = false;'
        in text
    )

    compact = " ".join(
        text.split()
    )

    assert (
        "const CALL_ROUTE_ENABLED = "
        "TRACKING_VERIFIED && "
        "ZIP_COVERAGE_VERIFIED && "
        "ROUTING_VERIFIED && "
        "FOUNDER_LIVE_TRAFFIC_AUTHORIZED;"
        in compact
    )
