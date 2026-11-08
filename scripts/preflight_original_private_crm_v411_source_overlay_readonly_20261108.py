"""Read-only comparison of staged V4.11 overlay with ACTUAL live CRM assets."""
from pathlib import Path
import hashlib
import importlib.util
import httpx
import empire_os

ext="/opt/empire-ai/data-cloud-founder-pilot-20261107/empire_os"
if ext not in empire_os.__path__:
    empire_os.__path__.insert(0,ext)
p=Path(__file__).resolve().with_name(
    "private_crm_original_v411_source_review_candidate_20261108.py")
spec=importlib.util.spec_from_file_location("staged_crm_v411_live_overlay_preflight",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

for path,expected,patch in (
    (m.HTML_PATH,m.PINNED_LIVE_HTML_SHA,m.patch_html),
    (m.JS_PATH,m.PINNED_LIVE_JS_SHA,m.patch_js),
):
    response=httpx.get("http://127.0.0.1:8783"+path,timeout=5)
    assert response.status_code==200
    assert response.headers["cache-control"]=="no-store"
    assert hashlib.sha256(response.content).hexdigest()==expected
    staged=patch(response.text)
    if path==m.HTML_PATH:
        assert staged.count('id="verify-predictive-source"')==1
        assert staged.count('id="verify-data-cloud"')==1
        assert "sessionBearer" not in staged
    else:
        assert staged.count('byId("verify-predictive-source").addEventListener')==1
        assert staged.count('byId("verify-data-cloud").addEventListener')==1
        assert "sessionBearer" in staged
        assert "localStorage" not in m.JS_VERIFY
        assert "sessionStorage" not in m.JS_VERIFY
        assert "navigator.clipboard" not in m.JS_VERIFY
    print("LIVE_ORIGINAL_CRM_PROTECTED_ASSET_PATCH_COMPATIBLE",path,
          "current_sha",expected,"staged_length",len(staged))

r=httpx.post("http://127.0.0.1:8783"+m.SOURCE_PATH,timeout=5)
assert r.status_code==404
print("LIVE_PREDICTIVE_SOURCE_VERIFY_ROUTE_HELD_UNMOUNTED_404")
print("PRODUCTION_WRITES",0)
