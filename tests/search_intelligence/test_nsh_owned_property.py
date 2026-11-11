from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from empire_os.search_intelligence import nsh_owned_property as module
from empire_os.search_intelligence.search_console import GoogleSearchConsoleAdapter, SearchConsoleUnavailable
from empire_os.search_intelligence.service import build_search_intelligence_service


def _adapter(tmp_path,*,site="sc-domain:empire-ai.co.uk",page_rows=None):
    credential=tmp_path/"test.json";credential.write_text("{}")
    def fake_post(url,headers,payload):
        assert "sc-domain%3Anationalstormhub.com" in url
        assert payload["dimensions"]==["page"]
        assert payload["dataState"]=="final"
        return {"rows":page_rows or []}
    return GoogleSearchConsoleAdapter(site,credential,token_provider=lambda _:"scope-limited-token",post_json=fake_post)


def test_status_and_pages_separate_second_property_without_overwriting_primary(monkeypatch,tmp_path):
    primary=_adapter(tmp_path,page_rows=[{"keys":["https://nationalstormhub.com/roofing"],"clicks":1,"impressions":7}])
    monkeypatch.setattr(module,"configured_search_console_adapter",lambda:primary)
    seen=[]
    class Resp:
        def raise_for_status(self):pass
        def json(self):return {"siteEntry":[{"siteUrl":"sc-domain:empire-ai.co.uk","permissionLevel":"siteOwner"},{"siteUrl":"sc-domain:nationalstormhub.com","permissionLevel":"siteFullUser"}]}
    def get(url,headers,timeout):
        seen.append((url,headers,timeout));return Resp()
    monkeypatch.setattr(module.requests,"get",get)
    client=TestClient(build_search_intelligence_service())
    status=client.get("/v1/search/search-console/national-storm-hub/status")
    assert status.status_code==200
    assert status.json()["available"] is True
    assert status.json()["site_url"]=="sc-domain:nationalstormhub.com"
    assert status.json()["original_empire_ai_property_binding_changed"] is False
    found=client.get("/v1/search/search-console/national-storm-hub/pages?start_date=2026-10-20&end_date=2026-11-05")
    assert found.status_code==200
    assert found.json()["items"]==[{"keys":["https://nationalstormhub.com/roofing"],"clicks":1,"impressions":7}]
    assert primary.site_url=="sc-domain:empire-ai.co.uk"
    assert all(x[0]==module.SITES_URL and x[1]["Authorization"]=="Bearer scope-limited-token" for x in seen)
    assert found.json()["revenue_verified"] is False


def test_missing_service_account_property_does_not_claim_access(monkeypatch,tmp_path):
    monkeypatch.setattr(module,"configured_search_console_adapter",lambda:_adapter(tmp_path))
    class Resp:
        def raise_for_status(self):pass
        def json(self):return {"siteEntry":[{"siteUrl":"sc-domain:empire-ai.co.uk","permissionLevel":"siteOwner"}]}
    monkeypatch.setattr(module.requests,"get",lambda *args,**kwargs:Resp())
    app=TestClient(build_search_intelligence_service())
    assert app.get("/v1/search/search-console/national-storm-hub/status").json()["available"] is False
    res=app.get("/v1/search/search-console/national-storm-hub/pages?start_date=2026-10-20&end_date=2026-11-05")
    assert res.status_code==503
    assert res.json()["detail"]=="nsh_gsc_property_or_source_unavailable"


def test_reject_untrusted_role_and_different_primary_property(monkeypatch,tmp_path):
    monkeypatch.setattr(module,"configured_search_console_adapter",lambda:_adapter(tmp_path))
    class Resp:
        def raise_for_status(self):pass
        def json(self):return {"siteEntry":[{"siteUrl":"sc-domain:nationalstormhub.com","permissionLevel":"siteUnverifiedUser"}]}
    monkeypatch.setattr(module.requests,"get",lambda *args,**kwargs:Resp())
    with pytest.raises(SearchConsoleUnavailable,match="not_granted"):
        module._read_authenticated_nsh()
    monkeypatch.setattr(module,"configured_search_console_adapter",lambda:_adapter(tmp_path,site="sc-domain:unrelated.org"))
    with pytest.raises(SearchConsoleUnavailable,match="primary_gsc_owner_not_ready"):
        module._read_authenticated_nsh()


def test_refuses_non_nsh_rows_and_bad_dates(monkeypatch,tmp_path):
    monkeypatch.setattr(module,"configured_search_console_adapter",lambda:_adapter(tmp_path,page_rows=[{"keys":["https://example.com/"],"clicks":40}]))
    class Resp:
        def raise_for_status(self):pass
        def json(self):return {"siteEntry":[{"siteUrl":"sc-domain:nationalstormhub.com","permissionLevel":"siteOwner"}]}
    monkeypatch.setattr(module.requests,"get",lambda *args,**kwargs:Resp())
    app=TestClient(build_search_intelligence_service())
    res=app.get("/v1/search/search-console/national-storm-hub/pages?start_date=2026-10-20&end_date=2026-11-05")
    assert res.status_code==503 and res.json()["detail"]=="nsh_gsc_page_scope_untrusted"
    assert app.get("/v1/search/search-console/national-storm-hub/pages?start_date=2026-01-01&end_date=2026-03-01").status_code==422
    monkeypatch.setattr(module,"configured_search_console_adapter",lambda:_adapter(tmp_path,page_rows=[{"keys":["https://nationalstormhub.com.evil.example/"],"clicks":10}]))
    assert app.get("/v1/search/search-console/national-storm-hub/pages?start_date=2026-10-20&end_date=2026-11-05").status_code==503
