"""Original customer API accepts only provenance-safe existing DDG fallback.

Synthetic metering only, no live network, tenant grants, external paid
provider, browser secret, or real consumption.
"""
from tests.test_data_cloud_first_party_search_bridge_20261109 import (
    build, search, SOURCE,
)


def test_existing_first_party_ddg_result_keeps_exact_source_and_no_fee(monkeypatch):
    row = {
        "title": "UK Roofing Leads: Exclusive Roofing Leads",
        "link": "https://www.ukroofingleads.com/pages/roofing-leads",
        "snippet": "Relevant UK roofing-lead service information.",
        "engine": "duckduckgo_html",
    }
    app, meter, calls = build(monkeypatch, rows=[row])
    response = search(app)
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["title"] == row["title"]
    assert result["source"]["source_id"] == SOURCE
    assert result["source"]["upstream_engine"] == "duckduckgo_html"
    assert result["source"]["url"] == row["link"]
    assert len(meter.reserves) == len(meter.settlements) == 1
    assert meter.settlements[0][0] == "completed"
    assert meter.settlements[0][1]["actual_usd_micros"] == 0
    assert meter.settlements[0][1]["cost_source_ref"] == (
        "empire_fabric_direct_public_no_paid_api_v1"
    )


def test_unknown_supplier_engine_still_fails_closed(monkeypatch):
    row = {
        "title": "UK Roofing Leads",
        "link": "https://www.ukroofingleads.com/roofing-leads",
        "snippet": "UK",
        "engine": "unknown_new_supplier",
    }
    app, meter, _ = build(monkeypatch, rows=[row])
    response = search(app)
    assert response.status_code == 503
    assert meter.settlements[0][0] == "provider_error"
    assert meter.settlements[0][1]["actual_usd_micros"] == 0
