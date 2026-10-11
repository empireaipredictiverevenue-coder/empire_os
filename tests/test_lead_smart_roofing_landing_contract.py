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



def test_frozen_roofing_cta_remains_disabled_with_additional_backend_legal_gate():
    from empire_os.lead_smart_launch_readiness import build_launch_readiness

    text = source()
    all_flags = {
        "tracking_verified": "TRACKING_VERIFIED",
        "zip_targeting_verified": "ZIP_COVERAGE_VERIFIED",
        "routing_runtime_verified": "ROUTING_VERIFIED",
        "operating_hours_verified": "OPERATING_HOURS_VERIFIED",
        "caller_id_pass_through_verified": "CALLER_ID_PASS_THROUGH_VERIFIED",
        "buyer_landing_page_approved": "BUYER_LANDING_PAGE_APPROVED",
        "landing_publication_authorized": "LANDING_PUBLICATION_AUTHORIZED",
        "founder_live_traffic_authorized": "FOUNDER_LIVE_TRAFFIC_AUTHORIZED",
    }
    readiness = build_launch_readiness(tracking={}, zip_gate={}, routing={})
    # Preserve the buyer-approved static source. Its eight constants stay
    # false; the readiness backend now additionally blocks on legal release.
    assert set(readiness["gates"]) == set(all_flags) | {"legal_release_verified", "pilot_stop_verified"}
    assert readiness["gates"]["legal_release_verified"] is False
    assert readiness["call_cta_enabled"] is False

    compact = normalized(text)
    for flag in all_flags.values():
        assert f"const {flag} = false;" in text

    required_expression = (
        "const CALL_ROUTE_ENABLED = "
        + " && ".join([
            "TRACKING_VERIFIED",
            "ZIP_COVERAGE_VERIFIED",
            "ROUTING_VERIFIED",
            "OPERATING_HOURS_VERIFIED",
            "CALLER_ID_PASS_THROUGH_VERIFIED",
            "BUYER_LANDING_PAGE_APPROVED",
            "LANDING_PUBLICATION_AUTHORIZED",
            "FOUNDER_LIVE_TRAFFIC_AUTHORIZED",
        ])
        + ";"
    )
    assert required_expression in compact
    assert "{CALL_ROUTE_ENABLED ? (" in text
    assert "Call route pending verification" in text
    assert 'href="tel:' not in text



def test_roofing_page_mounts_read_only_zip_preview():
    page = source()
    client = Path(
        "apps/empire-public-site/src/app/roofing/coverage-check.tsx"
    ).read_text()
    assert 'import RoofingCoverageCheck from "./coverage-check";' in page
    assert "<RoofingCoverageCheck />" in page
    assert 'fetch("/roofing/coverage-check"' in client
    assert 'method: "POST"' in client
    assert 'cache: "no-store"' in client
    assert "Date.parse(item.source_expires_at)" in client
    assert 'item.call_authorized === false' in client
    assert 'item.call_authorized === true' in client
    assert 'action="/roofing/pilot-handoff"' in client
    assert 'item.execution_authority === "NONE"' in client
    assert 'item.execution_authority === "LIVE_TRAFFIC"' in client
    assert "a listed zip does not guarantee" in client.lower()
    assert "daylight saving applies" in client.lower()
    assert 'href="tel:' not in client
    assert "No phone number will be enabled by this preview" in client


def test_roofing_page_public_and_template_source_remain_identical():
    canonical = PAGE.read_bytes()
    site = Path("apps/empire-public-site/src/app/roofing/page.tsx").read_bytes()
    assert canonical == site
