from empire_os.lead_sources import recc_solar


def test_recc_detail_ignores_group_site_and_keeps_member_website(monkeypatch):
    html = """
    <html>
      <body>
        <a href="https://www.biofertiliser.org.uk">BCS</a>
        <h1>4 Seasons Air Conditioning Limited</h1>
        <a href="https://www.4seasonssolutions.co.uk">
          WWW.4SEASONSSOLUTIONS.CO.UK
        </a>
        <p>80 Langstone Drive Exmouth Devon EX8 4JD</p>
        <p>Tel: 01395266118</p>
        <h4>Sectors:</h4>
        <ul><li>Solar PV</li></ul>
      </body>
    </html>
    """
    monkeypatch.setattr(recc_solar, "_get", lambda _url: html)

    candidate = recc_solar._detail(
        "4 Seasons Air Conditioning Limited",
        "https://www.recc.org.uk/scheme/members/example",
    )

    assert candidate is not None
    assert candidate.raw["business_website"] == (
        "https://www.4seasonssolutions.co.uk"
    )
    assert candidate.phone == "01395266118"
    assert candidate.raw["postcode"] == "EX8 4JD"


def test_recc_label_host_match_rejects_generic_group_label():
    assert recc_solar._label_matches_host(
        "BCS",
        "www.biofertiliser.org.uk",
    ) is False
    assert recc_solar._label_matches_host(
        "WWW.4SEASONSSOLUTIONS.CO.UK",
        "www.4seasonssolutions.co.uk",
    ) is True
