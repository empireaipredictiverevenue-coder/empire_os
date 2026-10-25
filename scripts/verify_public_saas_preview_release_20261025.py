"""Byte-level public SaaS release acceptance, GET-only, with no buyer submissions.

Two observations:
  --before : current approved HTML and working public catalogue/privacy.
  --after  : exact new HTML + all ten individually pinned GET-served JS/CSS
             assets and current local paired RSC payload.

It does not execute a release or grant publication/CRM/email/money authority.
Existing Empire gateway does NOT expose /predictive-revenue.txt directly.
Therefore this check also requires a separate real-browser navigation acceptance
and protected root-owner release receipt; neither is inferred from GETs.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts import review_saas_evidence_release_candidate_20261025 as qa

ORIGIN = "https://empire-ai.co.uk"
PUBLIC_PAGE = "/predictive-revenue"
PUBLIC_CATALOG = "/v1/checkout/predictive-revenue/products"
PUBLIC_PRIVACY = "/privacy"
MANIFEST = Path(
    "/srv/empire_os/docs/website/release_candidates/"
    "SAAS_EVIDENCE_PAIRED_UNION_20261025.json"
)
FOUNDER = Path(
    "/srv/empire_os/docs/website/release_candidates/"
    "SAAS_EVIDENCE_FOUNDER_APPROVAL_20261025.json"
)


class PublicSaaSReleaseHold(ValueError):
    pass


def fetch_public_get(path: str, *, limit: int = 1_500_000) -> bytes:
    if not isinstance(path, str) or not path.startswith("/") or (
        any(char in path for char in ("?", "#", "\\", "\r", "\n", "%"))
        or "//" in path or ".." in path.split("/")
    ):
        raise PublicSaaSReleaseHold("UNSAFE_PUBLIC_GET_PATH")
    if len(path) > 260 or limit < 1 or limit > 3_000_000:
        raise PublicSaaSReleaseHold("PUBLIC_GET_LIMIT_REJECTED")
    target = ORIGIN + path
    req = Request(target, method="GET", headers={
        "User-Agent": "EmpireOS-SaaS-Public-ReadOnly-Acceptance/1",
        "Accept": "*/*",
    })
    try:
        with urlopen(req, timeout=12) as response:
            if response.status != 200:
                raise PublicSaaSReleaseHold("PUBLIC_GET_NON_200")
            final = urlsplit(response.geturl())
            if (final.scheme != "https" or final.netloc != "empire-ai.co.uk"
                    or final.path != path):
                raise PublicSaaSReleaseHold("PUBLIC_GET_REDIRECTED_OUTSIDE_ALLOWED_PATH")
            payload = response.read(limit + 1)
    except (TimeoutError, OSError) as exc:
        raise PublicSaaSReleaseHold("PUBLIC_GET_UNAVAILABLE") from exc
    if not payload or len(payload) > limit:
        raise PublicSaaSReleaseHold("PUBLIC_GET_EMPTY_OR_OVERSIZE")
    return payload


def _load_pinned_documents(manifest: Path = MANIFEST,
                           founder: Path = FOUNDER) -> dict[str, Any]:
    if manifest.is_symlink() or founder.is_symlink():
        raise PublicSaaSReleaseHold("SYMLINKED_RELEASE_AUTHORITY_REJECTED")
    if not manifest.is_file() or not founder.is_file():
        raise PublicSaaSReleaseHold("MISSING_PINNED_RELEASE_EVIDENCE")
    if manifest.stat().st_size > 100_000 or founder.stat().st_size > 30_000:
        raise PublicSaaSReleaseHold("UNBOUNDED_RELEASE_EVIDENCE")
    m=json.loads(manifest.read_text())
    f=json.loads(founder.read_text())
    if (f.get("manifest_sha256") != sha256(manifest.read_bytes()).hexdigest()
            or f.get("founder_approval_for_exact_candidate") is not True
            or f.get("publication_authorized_now") is not False
            or m.get("status") !=
                "OFFLINE_PAIRED_HTML_RSC_UNION_CANDIDATE_PREPARED_NOT_PUBLISHED"
            or m.get("replacement_routes") != sorted(qa.REPLACE)
            or m.get("candidate_file_count") != 672
            or m.get("approved_live_file_count") != 662
            or m.get("added_static_asset_count") != 10
            or m.get("release_owner_approved") is not False):
        raise PublicSaaSReleaseHold("FOUNDER_AND_RELEASE_SCOPE_NOT_CONSISTENT")
    return m


def assess(mode: str, *, manifest: dict, get: Callable[[str], bytes],
           local_index: dict[str, str] | None = None) -> dict:
    if mode not in ("before","after"):
        raise PublicSaaSReleaseHold("INVALID_PUBLIC_ACCEPTANCE_MODE")
    if manifest.get("schema_version") != "empire.saas.offline_single_route_union.v1":
        raise PublicSaaSReleaseHold("WRONG_RELEASE_SCHEMA")
    page = get(PUBLIC_PAGE)
    expected = (manifest["prior_html_sha256"] if mode == "before"
                else manifest["candidate_html_sha256"])
    actual = sha256(page).hexdigest()
    if actual != expected:
        raise PublicSaaSReleaseHold("PUBLIC_HTML_NOT_MATCHING_" + mode.upper())
    html=page.decode("utf8","replace")
    if ('id="deployment-request"' not in html
            or 'I consent to Empire AI emailing me about this specific deployment'
                not in html
            or '/privacy' not in html):
        raise PublicSaaSReleaseHold("EXISTING_FIRST_PARTY_CONSENT_FORM_MISSING")
    preview=('id="free-evidence-sample"' in html
             and 'Explore a free revenue-evidence example' in html)
    if preview != (mode=="after"):
        raise PublicSaaSReleaseHold("PUBLIC_PREVIEW_VISIBILITY_NOT_EXPECTED")
    catalogue=json.loads(get(PUBLIC_CATALOG))
    if not isinstance(catalogue,dict) or not isinstance(catalogue.get("products"),list):
        raise PublicSaaSReleaseHold("UNTRUSTED_PUBLIC_CATALOGUE")
    if len(catalogue["products"]) != 5:
        raise PublicSaaSReleaseHold("PUBLIC_CATALOGUE_HAS_UNEXPECTED_PRODUCT_COUNT")
    for x in catalogue["products"]:
        if not isinstance(x,dict) or not x.get("product_code"):
            raise PublicSaaSReleaseHold("PUBLIC_CATALOGUE_ENTRY_INVALID")
    privacy=get(PUBLIC_PRIVACY)
    if b"Privacy" not in privacy and b"privacy" not in privacy:
        raise PublicSaaSReleaseHold("PRIVACY_DOCUMENT_NOT_GROUNDED")
    checked_assets=0
    if mode=="after":
        if local_index is None or len(local_index)!=672:
            raise PublicSaaSReleaseHold("LOCAL_POSTPUBLIC_INVENTORY_NOT_672")
        if qa.index_digest(local_index)!=manifest["candidate_inventory_sha256"]:
            raise PublicSaaSReleaseHold("LOCAL_POSTPUBLIC_INVENTORY_NOT_PINNED")
        if local_index.get("predictive-revenue.txt")!=manifest["candidate_rsc_sha256"]:
            raise PublicSaaSReleaseHold("LOCAL_PAIRED_RSC_MISMATCH")
        if local_index.get("predictive-revenue.html")!=manifest["candidate_html_sha256"]:
            raise PublicSaaSReleaseHold("LOCAL_PAIRED_HTML_MISMATCH")
        assets=manifest.get("added_static_assets")
        if not isinstance(assets,list) or len(assets)!=10:
            raise PublicSaaSReleaseHold("MISSING_PINNED_NEW_ASSETS")
        for item in assets:
            path=item.get("path") if isinstance(item,dict) else None
            digest=item.get("sha256") if isinstance(item,dict) else None
            if not isinstance(path,str) or not path.startswith("_next/static/"):
                raise PublicSaaSReleaseHold("UNSAFE_RELEASE_ASSET")
            if local_index.get(path)!=digest:
                raise PublicSaaSReleaseHold("LOCAL_ASSET_NOT_MATCHING_PIN")
            if sha256(get("/"+path)).hexdigest()!=digest:
                raise PublicSaaSReleaseHold("PUBLIC_STATIC_ASSET_NOT_MATCHING_PIN")
            checked_assets+=1
    return {
        "schema_version":"empire.website.public_saas_release_get_acceptance.v1",
        "status":(
            "EXISTING_PUBLIC_PAGE_VERIFIED_NEW_PREVIEW_NOT_LIVE"
            if mode=="before" else
            "PUBLIC_NEW_SAAS_BYTES_VISIBLE_OWNER_RECEIPT_STILL_REQUIRED"
        ),
        "mode":mode,
        "public_html_sha256":actual,
        "public_html_byte_exact":True,
        "public_preview_visible":preview,
        "public_product_catalogue_count":len(catalogue["products"]),
        "public_privacy_get_healthy":True,
        "new_hashed_static_assets_get_verified":checked_assets,
        "local_paired_rsc_inventory_verified":mode=="after",
        "public_rsc_txt_endpoint_verified":False,
        "separate_real_browser_navigation_check_required":True,
        "independent_website_owner_root_receipt_verified":False,
        "publication_authorized_by_this_check":False,
        "database_writes":False,
        "prospect_created":False,
        "outbound_sent":False,
        "payment_action":False,
    }


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--before",action="store_true")
    group.add_argument("--after",action="store_true")
    args=parser.parse_args()
    mode="before" if args.before else "after"
    try:
        manifest=_load_pinned_documents()
        index=qa.read_index(qa.LIVE) if mode=="after" else None
        result=assess(mode,manifest=manifest,get=fetch_public_get,local_index=index)
        print(json.dumps(result,sort_keys=True))
        return 0
    except (PublicSaaSReleaseHold,ValueError,OSError,TypeError,
            UnicodeDecodeError,KeyError) as exc:
        print(json.dumps({
            "status":"PUBLIC_SAAS_RELEASE_ACCEPTANCE_HELD",
            "mode":mode,
            "reason":str(exc) if isinstance(exc,PublicSaaSReleaseHold)
                     else type(exc).__name__,
            "publication_authorized":False,
            "publication_performed":False,
        },sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
