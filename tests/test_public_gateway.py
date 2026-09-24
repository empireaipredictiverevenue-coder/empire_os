from pathlib import Path
from fastapi.testclient import TestClient

from empire_os.public_gateway import (
    _inline_script_hashes,
    _public_site_urls,
    _public_trust_manifest,
    _site_csp,
    _site_html_path,
    _sitemap_xml,
    app,
)

client = TestClient(app)


def test_health_is_read_only_public_surface():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "online"
    assert body["execution"] == "read-only-public-surface"


def test_home_is_public_landing():
    r = client.get("/")
    assert r.status_code == 200
    assert "Empire AI" in r.text
    assert "Predictive Revenue" in r.text


def test_no_openapi_surface():
    assert client.get("/openapi.json").status_code == 404


def test_security_headers_present():
    r = client.get("/")
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_robots_advertises_sitemap():
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert "Sitemap:" in r.text
    assert "/sitemap.xml" in r.text


def test_sitemap_helper_lists_only_aeo_index_pages(tmp_path):
    page = tmp_path / "roofing" / "DFW" / "index.html"
    page.parent.mkdir(parents=True)
    page.write_text("<html></html>")
    ignored = tmp_path / "roofing" / "DFW" / "notes.txt"
    ignored.write_text("ignore")

    xml = _sitemap_xml(tmp_path, tmp_path / "empty-site")
    assert "/aeo/roofing/DFW/" in xml
    assert "notes.txt" not in xml
    assert xml.count("<url>") == 2


def test_public_trust_manifest_fails_closed(tmp_path):
    result = _public_trust_manifest(tmp_path / "missing.json")
    assert result["available"] is False
    assert result["trust_center_ready"] is False
    assert result["verified_claims"] == []


def test_public_trust_manifest_exposes_only_snapshot_manifest(tmp_path):
    path = tmp_path / "trust.json"
    path.write_text(
        '{"assessment":{"internal_score":99},"public_manifest":'
        '{"schema_version":"empire.public_trust_manifest.v1",'
        '"verified_claims":[{"key":"incident_response","evidence_refs":["ops:1"]}],'
        '"self_awarded_score":null,"trust_center_ready":false,'
        '"unknowns_hidden":false,"fabricated_social_proof":false}}'
    )
    result = _public_trust_manifest(path)
    assert result["available"] is True
    assert result["verified_claims"][0]["key"] == "incident_response"
    assert "internal_score" not in result


def test_public_site_route_resolution_is_allowlisted(tmp_path):
    (tmp_path / "industries").mkdir()
    (tmp_path / "index.html").write_text("home")
    (tmp_path / "trust.html").write_text("trust")
    (tmp_path / "industries.html").write_text("industries")
    (tmp_path / "buy.html").write_text("buy")
    (tmp_path / "industries/property.html").write_text("property")
    assert _site_html_path("", tmp_path).name == "index.html"
    assert _site_html_path("trust", tmp_path).name == "trust.html"
    assert _site_html_path("industries/property", tmp_path).name == "property.html"
    assert _site_html_path("buy", tmp_path).name == "buy.html"
    assert _site_html_path("../secret", tmp_path) is None
    assert _site_html_path("industries/../../secret", tmp_path) is None


def test_public_site_urls_are_added_to_sitemap(tmp_path):
    aeo = tmp_path / "aeo"
    site = tmp_path / "site"
    (aeo / "roofing/DFW").mkdir(parents=True)
    (aeo / "roofing/DFW/index.html").write_text("aeo")
    (site / "industries").mkdir(parents=True)
    (site / "trust.html").write_text("trust")
    (site / "industries.html").write_text("industries")
    (site / "buy.html").write_text("buy")
    (site / "industries/property.html").write_text("property")
    xml = _sitemap_xml(aeo, site)
    assert "/trust" in xml
    assert "/industries" in xml
    assert "/buy" in xml
    assert "/industries/property" in xml
    assert "/aeo/roofing/DFW/" in xml


def test_inline_script_hashes_ignore_external_scripts(tmp_path):
    page = tmp_path / "index.html"
    page.write_text(
        '<script>window.__BOOT__=1</script>'
        '<script src="/_next/app.js"></script>'
    )
    hashes = _inline_script_hashes(page)
    assert len(hashes) == 1
    assert hashes[0].startswith("'sha256-")


def test_csp_allows_only_hashed_inline_scripts(monkeypatch, tmp_path):
    page = tmp_path / "index.html"
    page.write_text('<script>window.__BOOT__=1</script>')
    monkeypatch.setattr(
        "empire_os.public_gateway._site_html_path",
        lambda route: page,
    )
    csp = _site_csp("/")
    assert "script-src 'self' 'sha256-" in csp
    assert "'unsafe-inline'" not in csp.split("style-src", 1)[0]


def test_brand_asset_is_served_from_export(monkeypatch, tmp_path):
    brand_dir = tmp_path / "brand"
    brand_dir.mkdir()
    mark = brand_dir / "empire-mark.svg"
    mark.write_text("<svg></svg>")
    monkeypatch.setattr("empire_os.public_gateway.SITE_OUT", tmp_path)
    from empire_os.public_gateway import brand_asset

    response = brand_asset("empire-mark.svg")
    assert Path(response.path) == mark
    assert response.media_type == "image/svg+xml"


def test_unknown_brand_asset_is_rejected():
    from empire_os.public_gateway import brand_asset

    response = brand_asset("../secret.svg")
    assert response.status_code == 404


def test_site_icon_is_served_from_export(monkeypatch, tmp_path):
    icon = tmp_path / "icon.svg"
    icon.write_text("<svg></svg>")
    monkeypatch.setattr("empire_os.public_gateway.SITE_OUT", tmp_path)
    from empire_os.public_gateway import site_icon

    response = site_icon()
    assert Path(response.path) == icon
    assert response.media_type == "image/svg+xml"


def test_favicon_alias_is_served_from_export(monkeypatch, tmp_path):
    icon = tmp_path / "icon.svg"
    icon.write_text("<svg></svg>")
    monkeypatch.setattr("empire_os.public_gateway.SITE_OUT", tmp_path)
    from empire_os.public_gateway import favicon

    response = favicon()
    assert Path(response.path) == icon
    assert response.media_type == "image/svg+xml"


def test_checkout_proxy_rejects_non_json():
    response = client.post(
        "/v1/checkout/orders",
        content="not-json",
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 415
    assert response.json()["error"] == "application_json_required"
