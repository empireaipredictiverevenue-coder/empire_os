"""V12 proposed single Chicago addendum never alters the original 5 release."""
import hashlib
import json
from pathlib import Path
import pytest

from empire_os.microsite_original_gateway_addendum_v12 import (
    APPROVAL_SCHEMA, CAMPAIGN_ID, CANDIDATE, ORIGINAL_PREVIEW_SHA,
    SCHEMA, original_owner_chicago_html,
)

HTML = (
    '<!doctype html><html><head>'
    '<meta name="robots" content="noindex,nofollow,noarchive">'
    '</head><body><main><h1>Research example</h1>'
    '<img src="data:image/png;base64,YWJj" alt="Private reference" />'
    '<p>Official source research only</p></main></body></html>'
)
ROLES = ("seo", "brand", "website")


@pytest.fixture
def site(tmp_path):
    def file(name: str, data: str):
        p=tmp_path/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(data)
        return p
    def jsonfile(name, record):
        return file(name,json.dumps(record))
    old_release=jsonfile("runtime/astra/owned_campaign_deployed_release.json",{
        "existing_release":"preserve_five"
    })
    first_sha=hashlib.sha256(old_release.read_bytes()).hexdigest()
    exact_html=hashlib.sha256(HTML.encode()).hexdigest()
    deployed=file(f"apps/empire-public-site/out/research/{CAMPAIGN_ID}.html",HTML)
    addendum={
        "schema_version":SCHEMA,
        "candidate_id":CANDIDATE,
        "campaign_id":CAMPAIGN_ID,
        "source_preview_sha256":ORIGINAL_PREVIEW_SHA,
        "deployed_html_sha256":exact_html,
        "original_five_release_sha256":first_sha,
        "zero_paid_media":True,
        "indexation_enabled":False,
        "lead_form_enabled":False,
        "outbound_authorized":False,
        "execution_authority":"none",
        "original_site_owner_staged_export_verified":True,
        "staged_export_sha256":exact_html,
        "site_owner_live_readback_verified":False, # must be possible pre-launch
        "original_site_owner_release_approved":True,
        "url":f"https://empire-ai.co.uk/research/{CAMPAIGN_ID}",
    }
    receipt=jsonfile("runtime/public_website/one_chicago_research_release.json",addendum)
    role_paths={}
    for role in ROLES:
        record={
            "schema_version":APPROVAL_SCHEMA,
            "review_lane":role,
            "independently_approved":True,
            "owner_ref":f"controlled-fixture-{role}",
            "candidate_id":CANDIDATE,
            "source_preview_sha256":ORIGINAL_PREVIEW_SHA,
            "deployed_html_sha256":exact_html,
            "approval_scope":"single_chicago_citywide_research",
        }
        role_paths[role]=jsonfile(
            f"runtime/public_website/approvals/chicago_research_{role}.json",
            record
        )
    return {"root":tmp_path,"receipt":receipt,"old":old_release,
            "deployed":deployed,"roles":role_paths}


def _old(root):
    return {"campaigns":[{"id":i} for i in range(5)]}


def _paths(root):
    return [f"/research/campaign_{i:024x}" for i in range(5)]


def check(site, **kw):
    return original_owner_chicago_html(
        CAMPAIGN_ID,root=site["root"],
        existing_release_reader=kw.get("old",_old),
        existing_paths_reader=kw.get("paths",_paths),
    )


def _edit_json(path, change):
    record=json.loads(path.read_text())
    change(record)
    path.write_text(json.dumps(record))


def test_dormant_proposed_route_rejects_unknown_campaign(site):
    assert original_owner_chicago_html(
        "campaign_"+"0"*24,root=site["root"],
        existing_release_reader=_old,existing_paths_reader=_paths
    ) is None


def test_original_owner_fixture_can_admit_one_separately_reviewed_page(site):
    """Synthetic approvals only inside test fixture; no real approval implied."""
    assert check(site) == HTML
    assert len(_paths(site["root"])) == 5


@pytest.mark.parametrize("field,value",[
    ("zero_paid_media",False),
    ("indexation_enabled",True),
    ("lead_form_enabled",True),
    ("outbound_authorized",True),
    ("execution_authority","activate"),
    ("original_site_owner_staged_export_verified",False),
    ("staged_export_sha256","f"*64),
    ("original_site_owner_release_approved",False),
    ("source_preview_sha256","0"*64),
    ("deployed_html_sha256","0"*64),
    ("url","https://example.net/research/garbage"),
    ("original_five_release_sha256","f"*64),
])
def test_any_tampered_release_receipt_denies_html(site,field,value):
    _edit_json(site["receipt"],lambda x:x.update({field:value}))
    assert check(site) is None


@pytest.mark.parametrize("role",ROLES)
def test_missing_original_owner_decision_denies_html(site,role):
    site["roles"][role].unlink()
    assert check(site) is None


@pytest.mark.parametrize("role",ROLES)
def test_wrong_approval_scope_or_source_sha_denies_html(site,role):
    _edit_json(site["roles"][role],lambda x:x.update(
        {"source_preview_sha256":"a"*64}))
    assert check(site) is None


def test_deployed_asset_changed_after_owner_review_denies_html(site):
    site["deployed"].write_text(HTML+"TAMPERED")
    assert check(site) is None


def test_original_five_release_is_mandatory(site):
    assert check(site,old=lambda root:None) is None
    assert check(site,old=lambda root:{"campaigns":[]}) is None
    assert check(site,paths=lambda root:_paths(root)[:4]) is None


def test_deployed_asset_symlink_denied(site):
    p=site["deployed"]
    bytes_=p.read_bytes()
    p.unlink()
    target=site["root"]/"some_other_file"
    target.write_bytes(bytes_)
    p.symlink_to(target)
    assert check(site) is None


def test_receipt_symlink_denied(site):
    receipt=site["receipt"]
    data=receipt.read_bytes()
    receipt.unlink()
    other=site["root"]/"fake_release.json"
    other.write_bytes(data)
    receipt.symlink_to(other)
    assert check(site) is None


def test_refuse_script_or_form_even_with_forged_hash_and_approval(site):
    site["deployed"].write_text(HTML+"<script>alert(1)</script>")
    altered=hashlib.sha256(site["deployed"].read_bytes()).hexdigest()
    _edit_json(site["receipt"],lambda x:x.update({"deployed_html_sha256":altered}))
    for path in site["roles"].values():
        _edit_json(path,lambda x:x.update({"deployed_html_sha256":altered}))
    assert check(site) is None
