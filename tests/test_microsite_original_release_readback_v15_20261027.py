"""Tests for the original website's separate post-publication readback."""
import pytest

from empire_os import microsite_original_release_readback_v15 as readback


@pytest.fixture
def original_six(monkeypatch, tmp_path):
    five = [f"/research/campaign_{i:024x}" for i in range(5)]
    asset_map = {
        p: f'<html><meta name="robots" content="index,follow">{p}</html>'.encode()
        for p in five
    }
    chicago = (
        '<html><meta name="robots" content="noindex,nofollow,noarchive">'
        '<div>Authentic source backed Chicago research fixture</div></html>'
    ).encode()
    asset_map[f"/research/{readback.CAMPAIGN_ID}"] = chicago
    monkeypatch.setattr(readback, "released_paths", lambda root: five[:])
    monkeypatch.setattr(
        readback, "released_html",
        lambda campaign_id,root=None: asset_map.get("/research/"+campaign_id,b"").decode()
    )
    monkeypatch.setattr(
        readback, "original_owner_chicago_html",
        lambda campaign_id,root=None: chicago.decode() if campaign_id==readback.CAMPAIGN_ID else None
    )
    requests = []
    def fetch(url, method):
        requests.append((url,method))
        page = asset_map[url.removeprefix(readback.ORIGIN)]
        return (200, {"cache-control":"no-store"}, page if method=="GET" else b"")
    return {"root":tmp_path,"fetch":fetch,"requests":requests,"assets":asset_map}


def test_exact_five_and_one_true_external_byte_readbacks_pass(original_six):
    r=readback.verify_original_owner_site_readback(original_six["root"],fetcher=original_six["fetch"])
    assert r["status"]=="ORIGINAL_SIX_EXACT_GET_HEAD_READBACK_PASS"
    assert len(r["verified"]) == 6
    assert r["original_campaigns"]==5 and r["new_chicago_pages"]==1
    assert len(original_six["requests"])==12
    assert r["recorded_revenue"] is None
    assert r["no_publication_performed_by_check"] is True


def test_unapproved_stage_refuses_any_outbound_probe(monkeypatch,original_six):
    monkeypatch.setattr(readback,"original_owner_chicago_html",lambda campaign_id,root:None)
    with pytest.raises(ValueError,match="No original-owner-approved"):
        readback.verify_original_owner_site_readback(original_six["root"],fetcher=original_six["fetch"])
    assert original_six["requests"]==[]


def test_existing_five_must_remain_intact(monkeypatch,original_six):
    monkeypatch.setattr(readback,"released_paths",lambda root: list(original_six["assets"])[:4])
    with pytest.raises(ValueError,match="five"):
        readback.verify_original_owner_site_readback(original_six["root"],fetcher=original_six["fetch"])
    assert original_six["requests"]==[]


@pytest.mark.parametrize("fault",["wrong_hash","head_body","no_store","head_no_store","not_200"])
def test_a_bad_live_readback_is_never_marked_as_verified(original_six,fault):
    old=original_six["fetch"]
    chicago_url=readback.ORIGIN+"/research/"+readback.CAMPAIGN_ID
    def broken(url,method):
        status,headers,body=old(url,method)
        if url==chicago_url and method=="GET":
            if fault=="wrong_hash": body+=b"TAMPERED"
            if fault=="no_store": headers["cache-control"]="public, max-age=1000"
            if fault=="not_200": status=404
        if url==chicago_url and method=="HEAD":
            if fault=="head_body": body=b"unexpected"
            if fault=="head_no_store": headers["cache-control"]="public, max-age=1000"
        return (status,headers,body)
    with pytest.raises(ValueError,match="failed|Missing"):
        readback.verify_original_owner_site_readback(original_six["root"],fetcher=broken)


def test_original_five_live_mismatch_blocks_chicago_success(original_six):
    first=sorted(original_six["assets"])[0]
    old=original_six["fetch"]
    def altered(url,method):
        status,headers,body=old(url,method)
        if url==readback.ORIGIN+first and method=="GET":
            return status,headers,body+b"replaced"
        return status,headers,body
    with pytest.raises(ValueError,match="readback failed"):
        readback.verify_original_owner_site_readback(original_six["root"],fetcher=altered)


@pytest.mark.parametrize("url,method", [
    ("https://attacker.invalid/research/campaign_fake", "GET"),
    ("http://empire-ai.co.uk/research/campaign_fake", "GET"),
    ("https://empire-ai.co.uk/checkout", "GET"),
    ("https://empire-ai.co.uk/research/campaign_fake", "POST"),
])
def test_direct_http_probe_rejects_noncanonical_targets_without_io(url, method):
    with pytest.raises(ValueError,match="canonical|GET and HEAD"):
        readback._http_read(url, method)
