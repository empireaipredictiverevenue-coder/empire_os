from empire_os.tag_intelligence_probe import observe_tag_surface


class Response:
    status_code = 200
    url = "https://example.com/"
    headers = {"X-Robots-Tag": "index,follow"}
    text = """
    <html>
      <head>
        <title>Example</title>
        <meta name="description" content="Example description">
        <meta name="robots" content="index,follow">
        <meta name="viewport" content="width=device-width">
        <meta charset="utf-8">
        <link rel="canonical" href="/">
        <link rel="alternate" hreflang="en-gb" href="/gb">
        <meta property="og:title" content="Example">
        <meta property="og:description" content="Example description">
        <meta property="og:url" content="https://example.com/">
        <meta property="og:image" content="https://example.com/a.jpg">
        <meta name="twitter:card" content="summary_large_image">
        <script type="application/ld+json">
          {"@context":"https://schema.org","@type":"Organization"}
        </script>
        <script>
          GTM-AAAA;
          GT-AAAA;
          G-AAAA;
          AW-12345;
          fbq('init', '999');
          gtag('event', 'generate_lead');
          gtag('consent', 'default', {});
        </script>
      </head>
      <body>
        <h1>Example</h1>
        <img src="/x.jpg" alt="Example">
      </body>
    </html>
    """


def test_static_tag_probe_extracts_search_and_measurement_tags():
    result = observe_tag_surface(
        "https://example.com",
        get=lambda *args, **kwargs: Response(),
    )

    assert result["ok"] is True
    page = result["page_tags"]
    tags = result["measurement_tags"]

    assert page["title"] == "Example"
    assert page["canonical_url"] == "https://example.com/"
    assert page["json_ld_types"] == ["Organization"]
    assert page["h1_count"] == 1
    assert page["images_missing_alt"] == 0

    assert tags["gtm_container_ids"] == ["GTM-AAAA"]
    assert tags["google_tag_ids"] == ["GT-AAAA"]
    assert tags["ga4_measurement_ids"] == ["G-AAAA"]
    assert tags["google_ads_conversion_ids"] == ["AW-12345"]
    assert tags["meta_pixel_ids"] == ["999"]
    assert tags["observed_events"] == ["generate_lead"]
    assert tags["consent_mode_enabled"] is True

    assert tags["meta_capi_enabled"] is None
    assert tags["meta_event_id_dedup"] is None
    assert tags["server_side_tagging"] is None
    assert result["execution_authority"] == "none"


def test_tag_probe_rejects_private_targets():
    try:
        observe_tag_surface("http://127.0.0.1")
    except ValueError as exc:
        assert "private network" in str(exc)
    else:
        raise AssertionError("private target should be rejected")


def test_tag_probe_does_not_claim_event_delivery():
    result = observe_tag_surface(
        "https://example.com",
        get=lambda *args, **kwargs: Response(),
    )

    assert result["measurement_tags"]["event_observation_level"] == (
        "SOURCE_DECLARATION"
    )
    assert "event_declaration_is_not_event_delivery" in result["limitations"]
