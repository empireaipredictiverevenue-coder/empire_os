"""Original checkout immutable asset guard with exact approved brand-only /buy.

Private files: fake checkout records; zero customer POSTs or production writes.
"""
from pathlib import Path
from hashlib import sha256
import json
import shutil
import pytest

from scripts import deploy_direct_bsc_buyer_status_release as r

BASE = Path('/home/ubuntu/empire_releases/buy_brand_lockup_20261101')
OWNER=Path(__file__).resolve().parents[1]
M=OWNER/'docs/commercial/original_release_evidence/SCOPED_BUY_BRAND_MANIFEST_20261101.json'
QA=OWNER/'docs/commercial/original_release_evidence/BUY_BRAND_BROWSER_QA_20261101.json'
LOGO=Path('/home/ubuntu/empire_worktrees/empire_design_studio_20261018/apps/empire-public-site/public/brand/empire-ai-primary-orbital-a-founder-approved.png')


def _setup(tmp_path,monkeypatch):
    manifest=json.loads(M.read_text())
    root=tmp_path/'empire_os'
    static=root/'apps/empire-public-site/out'
    docs=root/'docs/commercial'
    docs.mkdir(parents=True)
    static.mkdir(parents=True)
    original=docs/'DIRECT_BSC_BUY_UI_STATIC_EXPORT_MANIFEST_20261013.json'
    original.write_text(json.dumps({
        'buy_sha256':'0'*64,
        'assets':[{'path':'_next/static/chunks/immutable-old.js',
                   'sha256':sha256(b'original-immutable').hexdigest()}],
    }))
    legacy=static/'_next/static/chunks/immutable-old.js'
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b'original-immutable')
    for name in ['buy.html',*manifest['add_sha256']]:
        src=BASE/'stage'/name
        dest=static/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dest)
    logo=static/manifest['brand_asset_ref'].lstrip('/')
    logo.parent.mkdir(parents=True)
    shutil.copyfile(LOGO,logo)
    monkeypatch.setattr(r,'ROOT',root)
    monkeypatch.setattr(r,'BUY_BRAND_RELEASE_MANIFEST',M)
    monkeypatch.setattr(r,'BUY_BRAND_BROWSER_QA',QA)
    monkeypatch.setattr(r,'_approved_later_checkout_buy_sha256',
                        lambda:'435cd7b1fed3490998ec2ca74cd0fc68f1a6ff0a324a10adba6428def4e92552')
    return static,manifest


def test_reviewed_original_horizontal_brand_buy_passes_with_legacy_asset_guard(tmp_path,monkeypatch):
    static,manifest=_setup(tmp_path,monkeypatch)
    assert r._approved_brand_buy_sha256()==manifest['replace_sha256']['buy.html']
    r._published_checkout_verified()


@pytest.mark.parametrize('target',[
    'buy.html',
    '_next/static/css/93002b73242723fc.css',
    '_next/static/chunks/app/layout-ed51d8ad8107b67e.js',
    '_next/static/chunks/app/buy/page-4e23bc78c94f5a9c.js',
    'brand/empire-ai-primary-orbital-a-founder-approved.png',
    '_next/static/chunks/immutable-old.js',
])
def test_any_approved_buy_logo_or_asset_mutation_refused(tmp_path,monkeypatch,target):
    static,_=_setup(tmp_path,monkeypatch)
    path=static/target
    path.write_bytes(path.read_bytes()+b'MUTATION')
    with pytest.raises(ValueError,match='published checkout page not verified|immutable asset changed'):
        r._published_checkout_verified()


def test_reviewed_brand_manifest_byte_change_refused(tmp_path,monkeypatch):
    _setup(tmp_path,monkeypatch)
    altered=tmp_path/'manifest_changed.json'
    altered.write_bytes(M.read_bytes()+b'\n')
    monkeypatch.setattr(r,'BUY_BRAND_RELEASE_MANIFEST',altered)
    with pytest.raises(ValueError,match='not verified'):
        r._published_checkout_verified()


def test_reviewed_brand_browser_receipt_missing_refused(tmp_path,monkeypatch):
    _setup(tmp_path,monkeypatch)
    monkeypatch.setattr(r,'BUY_BRAND_BROWSER_QA',tmp_path/'missing.json')
    with pytest.raises(ValueError,match='not verified'):
        r._published_checkout_verified()


def test_rejected_unreviewed_buy_digest_even_if_source_manifest_exists(tmp_path,monkeypatch):
    static,_=_setup(tmp_path,monkeypatch)
    (static/'buy.html').write_bytes(b'something else')
    with pytest.raises(ValueError,match='not verified'):
        r._published_checkout_verified()


def test_original_checkout_guard_document_locations_survive_protecthome():
    assert str(r.BUY_BRAND_RELEASE_MANIFEST).startswith('/srv/empire_os/docs/commercial/original_release_evidence/')
    assert str(r.BUY_BRAND_BROWSER_QA).startswith('/srv/empire_os/docs/commercial/original_release_evidence/')
    assert sha256(M.read_bytes()).hexdigest()==r.BUY_BRAND_MANIFEST_SHA
    assert sha256(QA.read_bytes()).hexdigest()==r.BUY_BRAND_QA_SHA
