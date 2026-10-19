"""Regression for failed 2026-10-19 release check against nested H1 HTML.

We keep the validator strict but validate visible semantics, not contiguous
HTML source substrings (React inserts spans/whitespace, escapes ampersands).
"""
import pytest
import re
from scripts.verify_private_empire_analytics_html_20261019 import (
    AnalyticsRenderHeld, MAX_HTML_BYTES, verify_html,
)


def document(*, heading='<h1>Analytics <span>Command Centre</span></h1>',
             labels='Visitors &amp; sessions', hidden='', extra='') -> bytes:
    return ("""
<!doctype html><html><head>
<meta name="robots" content="noindex, nofollow" />
</head><body>
<img alt="Empire AI Predictive Revenue" src="/_next/image?url=%2Fbrand%2Fempire-ai-official-brand-logo-lockup.png&amp;w=256" />
""" + heading +
"""<main><p>Observed organic search trend</p>
<section aria-label="First-party daily search trend">
  <h3>Observed daily impressions</h3>
  <h3>Observed daily clicks</h3>
  <svg aria-label="Google Search Console reported clicks for observed dates"></svg>
</section>
<section><h3>Source availability</h3>
  <p>Google Search Console</p>
  <p>Attributed revenue: Not connected</p><p>""" + labels + """</p>
</section><a href="/department/evidence">Detailed evidence</a>
""" + hidden + extra + """
</main></body></html>""").encode("utf8")


def test_original_styled_heading_and_html_entities_are_verified():
    # Old script looked for 'analytics command centre' in raw HTML, hence
    # rejected the real release despite an actual H1 in a nested <span>.
    assert b"analytics command centre" not in document().lower()
    verify_html(document())


def test_extra_markup_and_whitespace_do_not_falsely_block_actual_h1():
    verify_html(document(heading="<h1> Analytics\n<span> Command </span> Centre </h1>"))


@pytest.mark.parametrize("missing", [
    "Analytics <span>Command Centre</span>",
    "noindex, nofollow",
    "Empire AI Predictive Revenue",
    "empire-ai-official-brand-logo-lockup.png",
    "Observed daily impressions",
    "Observed daily clicks",
    "Source availability",
    "First-party daily search trend",
    "Google Search Console reported clicks for observed dates",
    "visitors &amp; sessions",
    'href="/department/evidence"',
    "not connected",
])
def test_missing_any_actual_rendered_evidence_is_still_rejected(missing):
    source = document().decode()
    assert missing.casefold() in source.casefold()
    source = re.sub(re.escape(missing), "REMOVED_EVIDENCE", source, flags=re.IGNORECASE)
    with pytest.raises(AnalyticsRenderHeld):
        verify_html(source.encode())


def test_fake_nextjs_hydration_does_not_satisfy_required_visible_metrics():
    source=document().decode().replace(
        "Observed daily impressions",
        "<script>Observed daily impressions</script>")
    with pytest.raises(AnalyticsRenderHeld):
        verify_html(source.encode())


@pytest.mark.parametrize("fallback",[
    "Analytics data unavailable",
    "Department evidence unavailable",
])
def test_private_backend_fallbacks_fail_closed(fallback):
    with pytest.raises(AnalyticsRenderHeld):
        verify_html(document(extra=f"<section>{fallback}</section>"))


def test_bad_html_size_rejected_without_echoing_private_contents():
    for value in (b"",b"PRIVATE_EMAIL"+b" "*(MAX_HTML_BYTES+1)):
        with pytest.raises(AnalyticsRenderHeld) as exc:
            verify_html(value)
        assert "PRIVATE_EMAIL" not in str(exc.value)


def test_no_mutating_control_or_bypass_needed():
    verify_html(document(extra='<button type="button">Private preview only</button>'))
