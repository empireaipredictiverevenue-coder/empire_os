from fastapi.testclient import TestClient

from empire_os.public_gateway import _sitemap_xml, app

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

    xml = _sitemap_xml(tmp_path)
    assert "/aeo/roofing/DFW/" in xml
    assert "notes.txt" not in xml
    assert xml.count("<url>") == 2
