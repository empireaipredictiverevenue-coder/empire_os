"""Release transaction tests on disposable directories. Never touch public site."""
from hashlib import sha256
from pathlib import Path

import pytest

from scripts.release_predictive_roofing_two_page_20261022 import (
    TwoPageReleaseHeld, apply_four_pages_and_eight_assets,
)


def put(root:Path,rel:str,bytes_:bytes) -> None:
    file=root/rel
    file.parent.mkdir(parents=True,exist_ok=True)
    file.write_bytes(bytes_)


def sh(b:bytes)->str:
    return sha256(b).hexdigest()


@pytest.fixture()
def sample(tmp_path):
    live=tmp_path/"live"
    stage=tmp_path/"stage"
    live.mkdir();stage.mkdir()
    before={
        "predictive-revenue.html":b"old-predictive-html",
        "predictive-revenue.txt":b"old-predictive-rsc",
        "industries/roofing.html":b"old-roofing-html",
        "industries/roofing.txt":b"old-roofing-rsc",
    }
    new={
        "predictive-revenue.html":b"new-predictive-html",
        "predictive-revenue.txt":b"new-predictive-rsc",
        "industries/roofing.html":b"new-roofing-html",
        "industries/roofing.txt":b"new-roofing-rsc",
    }
    assets={
        "_next/static/chunks/new-predictive-hash.js":b"new-app-bundle",
        "_next/static/a-new-id/_buildManifest.js":b"build-manifest",
    }
    for k,v in before.items():put(live,k,v)
    put(live,"commercial.html",b"unrelated-commercial-original")
    put(live,"roofing.html",b"unrelated-homeowner-original")
    for k,v in {**new,**assets}.items():put(stage,k,v)
    return live,stage,before,new,assets


def call(sample,*,probe=None,additions=None):
    live,stage,old,new,assets=sample
    return apply_four_pages_and_eight_assets(
        live=live,stage=stage,
        baseline={k:sh(v) for k,v in old.items()},
        replacements={k:sh(v) for k,v in new.items()},
        additions={k:sh(v) for k,v in (assets if additions is None else additions).items()},
        final_probe=probe,
    )


def test_exact_two_page_patch_and_untouched_other_pages(sample):
    live,_,_,new,assets=sample
    r=call(sample)
    assert r["status"]=="EXACT_TWO_PAGE_STATIC_RELEASE_APPLIED"
    assert r["page_navigation_files_replaced"]==4
    assert r["new_hashed_assets_installed"]==2
    assert r["unrelated_routes_replaced"]==0
    assert all((live/k).read_bytes()==v for k,v in new.items())
    assert all((live/k).read_bytes()==v for k,v in assets.items())
    assert (live/"commercial.html").read_bytes()==b"unrelated-commercial-original"
    assert (live/"roofing.html").read_bytes()==b"unrelated-homeowner-original"


def test_post_swap_failure_rolls_back_every_file_and_new_asset(sample):
    live,_,old,_,assets=sample
    def fail():
        raise TwoPageReleaseHeld("synthetic-post-deploy-canary-failed")
    with pytest.raises(TwoPageReleaseHeld,match="synthetic-post-deploy"):
        call(sample,probe=fail)
    assert all((live/k).read_bytes()==v for k,v in old.items())
    assert all(not (live/k).exists() for k in assets)
    assert (live/"commercial.html").read_bytes()==b"unrelated-commercial-original"
    assert (live/"roofing.html").read_bytes()==b"unrelated-homeowner-original"


def test_original_page_changed_fails_without_any_write(sample):
    live,_,_,_,assets=sample
    put(live,"predictive-revenue.html",b"updated-by-other-agent")
    with pytest.raises(TwoPageReleaseHeld,match="CHANGED_PRIOR_PUBLIC_PAGE"):
        call(sample)
    assert (live/"predictive-revenue.html").read_bytes()==b"updated-by-other-agent"
    assert all(not (live/k).exists() for k in assets)


def test_asset_collision_fails_without_touching_pages(sample):
    live,_,old,_,assets=sample
    name=next(iter(assets))
    put(live,name,b"other-site-owned-hash")
    with pytest.raises(TwoPageReleaseHeld,match="STAGED_BUNDLE_PATH_COLLISION"):
        call(sample)
    assert (live/name).read_bytes()==b"other-site-owned-hash"
    assert all((live/k).read_bytes()==v for k,v in old.items())


def test_source_payload_tampered_fails_closed(sample):
    _,stage,_,_,_=sample
    put(stage,"industries/roofing.txt",b"tampered-source")
    with pytest.raises(TwoPageReleaseHeld,match="CANDIDATE_CONTENT_DRIFT"):
        call(sample)


def test_nonreluctant_rollback_with_failure_on_last_page(sample,monkeypatch):
    import scripts.release_predictive_roofing_two_page_20261022 as module
    live,_,old,_,assets=sample
    underlying=module._atomic
    state={"count":0}
    def flaky(p,blob,*args,**kwargs):
        state["count"]+=1
        if state["count"]==4:
            raise OSError("synthetic-fourth-page-write-failure")
        return underlying(p,blob,*args,**kwargs)
    monkeypatch.setattr(module,"_atomic",flaky)
    with pytest.raises(OSError,match="synthetic"):
        call(sample)
    assert all((live/k).read_bytes()==v for k,v in old.items())
    assert all(not (live/k).exists() for k in assets)
