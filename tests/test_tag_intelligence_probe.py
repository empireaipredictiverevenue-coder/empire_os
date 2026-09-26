from empire_os.tag_intelligence_probe import observe_tag_surface


class FakeResponse:
    status_code = 200
    url = "https://example.com/final"
    headers = {"X-Robots-Tag": "index,follow"}
    text = """
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width">
        <title>Example</title>
        <meta name="description" content="Example description">
        <link rel="canonical" href="/canonical">
        <meta property="og:title" content="Example">
        <meta property="og:description" content="Example description">
        <meta property="og:url" content="https://example.com/final">
        <meta property="og:image" content="https://example.com/og.jpg">
        <meta name="twitter:card" content="summary_large_image">
        <link rel="alternate" hreflang="en-gb" href="/gb">
        <script type="application/ld+json">
          {"@context":"https://schema.org","@type":"Organization"}
        </script>
        <script>
          var gtm = "GTM-ABC123";
          var ga4 = "G-ABC123";
          var ads = "AW-123456";
          fbq('init', '999999');
          gtag('event', 'purchase');
        </script>
      </head>
      <body>
        <h1>Example</h1>
        <img src="/hero.jpg">
      </body>
    </html>
    """


def test_probe_observes_static_search_and_measurement_evidence():
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    result = observe_tag_surface(
        "https://example.com",
        get=fake_get,
    )

    assert result["ok"] is True
    assert result["mode"] == "OBSERVE"
    assert result["execution_authority"] == "none"
    assert result["page_tags"]["title"] == "Example"
    assert result["page_tags"]["canonical_url"] == (
        "https://example.com/canonical"
    )
    assert result["page_tags"]["json_ld_types"] == ["Organization"]
    assert result["page_tags"]["images_missing_alt"] == 1
    assert result["measurement_tags"]["gtm_container_ids"] == [
        "GTM-ABC123"
    ]
    assert result["measurement_tags"]["ga4_measurement_ids"] == [
        "G-ABC123"
    ]
    assert result["measurement_tags"]["google_ads_conversion_ids"] == [
        "AW-123456"
    ]
    assert result["measurement_tags"]["meta_pixel_ids"] == ["999999"]
    assert result["measurement_tags"]["observed_events"] == ["purchase"]
    assert result["measurement_tags"]["meta_capi_enabled"] is None
    assert result["measurement_tags"]["revenue_truth_linked"] is None
    assert "static_markup_observation_only" in result["limitations"]
    assert len(calls) == 1


def test_probe_rejects_private_network_target_before_request():
    called = False

    def fake_get(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("request should not run")

    try:
        observe_tag_surface("http://127.0.0.1", get=fake_get)
    except ValueError as exc:
        assert "private network targets" in str(exc)
    else:
        raise AssertionError("private target should be rejected")

    assert called is False
