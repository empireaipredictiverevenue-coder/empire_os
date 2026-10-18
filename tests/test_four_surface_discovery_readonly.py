"""Contract and fail-closed tests for the standalone public discovery observer."""
import json
from urllib.error import HTTPError
import pytest
from empire_os.search_intelligence import four_surface_discovery as f


def response(body, status=200):
    return {"status": status, "body": body.encode() if isinstance(body, str) else body,
            "error": None}


def fixture():
    pages = {
        "/commercial": '<html><head><title>Commercial</title><link rel="canonical" href="https://empire-ai.co.uk/commercial"></head><main><h1>Service</h1><h2>Assessment</h2><a href="/commercial">Enquire</a></main></html>',
        "/industries/roofing": '<html><head><title>Roofing</title><link rel="canonical" href="https://empire-ai.co.uk/industries/roofing"></head><main><h1>Roofing</h1><h2>Evidence</h2><a href="/commercial">Proposal</a></main></html>',
        "/aeo/roofing/DFW/": '<html><head><title>DFW</title><link rel="canonical" href="https://empire-ai.co.uk/aeo/roofing/DFW"></head><main><h1>Local roofing</h1><h2>Market</h2><a href="https://empire-ai.co.uk">Home</a></main></html>',
    }
    obs = {p: response(v) for p, v in pages.items()}
    obs["/sitemap.xml"] = response('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://empire-ai.co.uk/</loc></url></urlset>')
    names = ["growth.seo.audit", "growth.aeo.audit", "growth.geo.visibility"]
    obs["/.well-known/agent-card.json"] = response(json.dumps({
        "skills": [{"id": "empire." + n} for n in names],
        "supportedInterfaces": [{"url": "https://empire-ai.co.uk/a2a/v1", "protocolBinding": "HTTP+JSON"}],
    }))
    obs["/agent-web/capabilities"] = response(json.dumps({"capabilities": [{"name": n} for n in names], "privilegedActionsExposed": False}))
    obs["/a2a/v1/discovery"] = response(json.dumps({"privileged_actions_exposed": False, "payments_exposed": False, "allocations_exposed": False}))
    return obs


def test_four_layers_and_no_fake_citations():
    d = f.review(fixture())
    assert d["authority"] == "OBSERVE"
    assert d["production_mutation"] is False
    assert d["seo"]["sitemap_declared_url_count"] == 1
    assert d["seo"]["pages"]["/aeo/roofing/DFW/"]["self_canonical"] is True
    assert d["aeo"]["contextual_roofing_pillar_link"] is False
    assert d["geo"]["external_ai_mentions_or_citations"] == "UNKNOWN"
    assert d["a2a"]["catalogue_skills_agree"] is True
    assert d["a2a"]["seo_aeo_geo_advertised"] is True
    assert d["a2a"]["no_privileged_actions_exposed"] is True
    assert d["a2a"]["authenticated_agent_transactions_proven"] == "UNKNOWN"


def test_unsafe_a2a_card_or_revealed_privileges_fails_closed():
    obs = fixture()
    obs["/a2a/v1/discovery"] = response('{"privileged_actions_exposed":true,"payments_exposed":false,"allocations_exposed":false}')
    obs["/.well-known/agent-card.json"] = response('{"skills":[],"supportedInterfaces":[{"url":"http://example.com/a2a","protocolBinding":"HTTP+JSON"}]}')
    d = f.review(obs)
    assert d["a2a"]["no_privileged_actions_exposed"] is False
    assert d["a2a"]["https_transport_declared"] is False
    assert d["a2a"]["catalogue_skills_agree"] is False


def test_unavailable_endpoints_cannot_be_reported_as_verified():
    obs = fixture()
    obs["/agent-web/capabilities"] = response("not json", status=503)
    obs["/aeo/roofing/DFW/"] = response("", status=404)
    d = f.review(obs)
    assert d["aeo"]["answer_headings"] is None
    assert d["a2a"]["catalogue_skills_agree"] is False
    assert d["seo"]["pages"]["/aeo/roofing/DFW/"]["available"] is False


def test_input_collection_is_exact_allowlisted_get(monkeypatch):
    requested = []
    class Res:
        status = 200
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self,n): return b'{}'
    class Opener:
        def open(self,req,timeout):
            requested.append((req.full_url,req.get_method(),timeout))
            return Res()
    monkeypatch.setattr(f,"build_opener",lambda *args:Opener())
    with pytest.raises(ValueError,match="unapproved_public_url"):
        f.fetch_public("/v1/checkout/commercial/interests")
    assert not requested
    r = f.fetch_public("/.well-known/agent-card.json")
    assert r["status"] == 200
    assert requested == [("https://empire-ai.co.uk/.well-known/agent-card.json","GET",10)]


def test_malformed_json_shapes_fail_closed():
    obs = fixture()
    obs["/.well-known/agent-card.json"] = response('["bad", "shape"]')
    obs["/agent-web/capabilities"] = response('{"capabilities":null}')
    obs["/a2a/v1/discovery"] = response('{"privileged_actions_exposed":false,"payments_exposed":false,"allocations_exposed":false}')
    d = f.review(obs)
    assert d["a2a"]["skills_advertised"] == 0
    assert d["a2a"]["catalogue_skills_agree"] is False
    assert d["a2a"]["https_transport_declared"] is False
