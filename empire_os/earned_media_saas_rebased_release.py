"""Offline reconciliation of ASTRA's SaaS page and Empire earned-media CTA.

Makes a fresh, user-owned *candidate only*, preserving current live pages.
Never applies to live, changes approval/receipts, or restarts a service.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import json
import os
import re
import shutil

# Match the original ASTRA release index contract (bounded files, paths and bytes)
# without importing or mutating its production publisher module.
def read_index(root: Path) -> dict[str, str]:
    if root.is_symlink() or not root.is_dir():
        raise ReleaseHeld("SITE_DIRECTORY_MISSING_OR_SYMLINK")
    result: dict[str, str] = {}
    size = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ReleaseHeld("RELEASE_TREE_SYMLINK_FORBIDDEN")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ReleaseHeld("RELEASE_TREE_NONFILE_ENTRY")
        rel = path.relative_to(root).as_posix()
        if (not rel or rel.startswith(".") or ".." in Path(rel).parts
                or "\\" in rel):
            raise ReleaseHeld("RELEASE_PATH_UNSAFE")
        if len(result) >= 1000 or path.stat().st_size > 20_000_000:
            raise ReleaseHeld("SITE_FILE_LIMIT_EXCEEDED")
        content = path.read_bytes()
        size += len(content)
        if size > 120_000_000:
            raise ReleaseHeld("SITE_BYTES_LIMIT_EXCEEDED")
        result[rel] = sha256(content).hexdigest()
    return result


def index_digest(index: dict[str, str]) -> str:
    return sha256("".join(
        f"{rel} {digest}\n" for rel, digest in sorted(index.items())
    ).encode()).hexdigest()

SCHEMA = "empire.website.earned_media_saas_rebased_static_candidate.v1"
REPLACE = frozenset(("predictive-revenue.html", "predictive-revenue.txt"))
CURRENT_LIVE_COUNT = 662
LIVE_DRIFT = frozenset((
    # 26 Oct 15:05 UTC newer commercial page: buyer-readiness copy/SEO meta.
    # Preserve the live page; do not revert to the 24 October owner's pin.
    "commercial.html",
    "industries/roofing.html",
    "industries/hvac.html",
    "industries/property.html",
    "industries/legal-mass-tort.html",
))
ORIGINAL_LIVE_PAGE_SHA = "7144c99317d5a38d2f44e94bdd992bb26a6544a1626a0cab8973d25b9e0c9e9a"
ORIGINAL_LIVE_RSC_SHA = "6d730f3f9c34a0052c944e05bbddfcaa940fcbdd5056d7dc61afb1ef6c9d9f43"
ORIGINAL_ASTRA_PREVIEW_PAGE_SHA = "1eaaa66e633967d553b18ebe3ed5180af36a555778c2efce4235679e1fc31053"
ORIGINAL_ASTRA_PREVIEW_RSC_SHA = "9ec0c0306c41b0b8c3311027d662abe9334033d46a8fba1b660a98857c988563"
LINK = "/commercial?entry=%2Fpredictive-revenue#commercial-enquiry"
OLD_LINK = "/commercial#commercial-enquiry"
PIN_ARRAY = "private_candidate_sha256"
STATIC_REF_RE = re.compile(
    r"(?<![\w/])static/(?:chunks|css)/[a-zA-Z0-9_./-]+\.(?:js|css)"
)


class ReleaseHeld(ValueError):
    pass


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


class LocalAssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs: set[str] = set()

    def handle_starttag(self, tag, attrs):
        if tag not in {"script", "link"}:
            return
        for key, value in attrs:
            if key in {"src", "href"} and isinstance(value, str) and value.startswith("/_next/static/"):
                if "?" in value or "#" in value or ".." in value or "\\\\" in value:
                    raise ReleaseHeld("ASSET_REFERENCE_UNSAFE")
                self.refs.add(value.lstrip("/"))


def route_static_references(html: str, rsc: str) -> set[str]:
    parser = LocalAssetParser()
    parser.feed(html)
    refs = set(parser.refs)
    refs.update("_next/" + x for x in STATIC_REF_RE.findall(rsc))
    if not 4 <= len(refs) <= 50:
        raise ReleaseHeld("NEXT_ROUTE_STATIC_REFERENCE_COUNT_INVALID")
    for ref in refs:
        if (not ref.startswith("_next/static/") or ".." in ref or "\\\\" in ref
                or ref.startswith("_next/static/.")
                or not re.fullmatch(r"[a-zA-Z0-9_./-]+", ref)):
            raise ReleaseHeld("NEXT_ROUTE_STATIC_REFERENCE_UNSAFE")
    return refs


def validate_inputs(
    live_index: dict[str, str], pin_index: dict[str, str],
    current_source: dict[str, str], original_preview: dict[str, str],
    *,
    expected_live_count: int = CURRENT_LIVE_COUNT,
    expected_owner_delta: frozenset[str] = LIVE_DRIFT,
) -> dict:
    if (len(live_index) != expected_live_count or len(pin_index) != expected_live_count
            or set(live_index) != set(pin_index)):
        raise ReleaseHeld("LIVE_SITE_SOURCE_INVENTORY_SHAPE_DRIFT")
    drift = {rel for rel in live_index if live_index[rel] != pin_index[rel]}
    if drift != expected_owner_delta:
        raise ReleaseHeld("CONCURRENT_OWNER_PAGE_DRIFT_MUST_BE_RECONCILED")
    if (live_index.get("predictive-revenue.html") != ORIGINAL_LIVE_PAGE_SHA
            or live_index.get("predictive-revenue.txt") != ORIGINAL_LIVE_RSC_SHA
            or original_preview.get("predictive-revenue.html") != ORIGINAL_ASTRA_PREVIEW_PAGE_SHA
            or original_preview.get("predictive-revenue.txt") != ORIGINAL_ASTRA_PREVIEW_RSC_SHA):
        raise ReleaseHeld("ORIGINAL_LIVE_OR_ASTRA_RELEASE_NOT_MATCHING_RECEIPTS")
    if not REPLACE.issubset(current_source):
        raise ReleaseHeld("REBUILT_SOURCE_ROUTE_PAIR_MISSING")
    return {
        "live_file_count": len(live_index),
        "historical_pin_mismatched_owner_pages": sorted(drift),
        "original_preview_route_sha256": {name: original_preview[name] for name in sorted(REPLACE)},
        "live_route_sha256": {name: live_index[name] for name in sorted(REPLACE)},
    }


def plan_rebased_delta(
    live_index: dict[str, str],
    built_index: dict[str, str],
    built_html: str, built_rsc: str, built_js: dict[str, bytes],
) -> tuple[dict, set[str]]:
    if (built_html.count(LINK) != 1 or OLD_LINK in built_html
            or built_html.count("Request a commercial proposal") != 1
            or 'id="deployment-request"' not in built_html
            or 'id="free-evidence-sample"' not in built_html):
        raise ReleaseHeld("BUILT_SAAS_HTML_CTA_OR_ORIGINAL_FUNNEL_DRIFT")
    if LINK in built_rsc or OLD_LINK in built_rsc:
        raise ReleaseHeld("RSC_UNEXPECTED_INLINE_GUIDE_CTA")
    refs = route_static_references(built_html, built_rsc)
    route_chunks = sorted(
        k for k in refs if re.fullmatch(
            r"_next/static/chunks/app/predictive-revenue/page-[a-f0-9]+\.js", k
        )
    )
    if len(route_chunks) != 1:
        raise ReleaseHeld("REBUILT_NEXT_PAGE_CHUNK_AMBIGUOUS")
    code = built_js.get(route_chunks[0])
    # The browser bundle calculates the same href using encodeURIComponent;
    # only the pre-rendered HTML contains the final literal %2F string.
    expected_client_expression = (
        b'"/commercial?entry="+encodeURIComponent("/predictive-revenue")'
        b'+"#commercial-enquiry"'
    )
    if (not isinstance(code, bytes) or
            code.count(expected_client_expression) != 1 or
            OLD_LINK.encode() in code or
            b"Request a commercial proposal" not in code):
        raise ReleaseHeld("CLIENT_HYDRATION_CTA_DOES_NOT_MATCH_STATIC_HTML")
    additions = set()
    for k in refs:
        newhash = built_index.get(k)
        if not newhash:
            raise ReleaseHeld("REBUILT_REFERENCED_STATIC_ASSET_MISSING")
        if k in live_index:
            if live_index[k] != newhash:
                raise ReleaseHeld("REBUILT_ASSET_COLLIDES_WITH_EXISTING_LIVE_ASSET")
        else:
            additions.add(k)
    if not additions:
        raise ReleaseHeld("REBUILD_NEW_ASSETS_NOT_FOUND")
    if len(additions) > 35:
        raise ReleaseHeld("REBUILD_ADDITION_SCOPE_TOO_LARGE")
    return {
        "new_asset_count": len(additions),
        "new_asset_paths": sorted(additions),
        "paired_routes_replaced": sorted(REPLACE),
        "original_build_chunk": route_chunks[0],
        "next_static_refs_checked": len(refs),
        "html_new_cta_count": 1,
        "client_hydration_new_cta_count": 1,
        "original_consent_form_preserved_in_html": True,
        "public_site_mounted_backend_changed": False,
    }, additions


def prepare_private_candidate(
    *, live_root: Path, prior_pin: Path, prior_preview: Path,
    rebuilt_root: Path, output_root: Path,
) -> dict:
    sources = (live_root, prior_preview, rebuilt_root)
    for p in sources:
        if p.is_symlink() or not p.is_dir():
            raise ReleaseHeld("UNSAFE_SOURCE_DIRECTORY")
    if output_root.exists() or output_root.is_symlink():
        raise ReleaseHeld("CANDIDATE_DESTINATION_ALREADY_EXISTS_NO_OVERWRITE")
    real_source_paths = [p.resolve() for p in sources]
    intended = output_root.resolve(strict=False)
    if any(intended == s or s in intended.parents or intended in s.parents
           for s in real_source_paths):
        raise ReleaseHeld("STAGING_DESTINATION_OVERLAPS_EXISTING_OWNER_OR_PUBLIC_SOURCE")
    if prior_pin.is_symlink() or not prior_pin.is_file() or prior_pin.stat().st_size > 500000:
        raise ReleaseHeld("PRIOR_PIN_MISSING_OR_UNSAFE")
    try:
        pin_data = json.loads(prior_pin.read_text(encoding="utf8"))[PIN_ARRAY]
    except (KeyError, TypeError, ValueError, OSError):
        raise ReleaseHeld("ORIGINAL_APPROVED_PIN_UNTRUSTED") from None
    if not isinstance(pin_data, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in pin_data.items()):
        raise ReleaseHeld("PIN_ORIGINAL_INDEX_INVALID")

    live_index = read_index(live_root)
    preview_index = read_index(prior_preview)
    built_index = read_index(rebuilt_root)
    source = validate_inputs(live_index, pin_data, built_index, preview_index)
    html = (rebuilt_root / "predictive-revenue.html").read_text(encoding="utf8")
    rsc = (rebuilt_root / "predictive-revenue.txt").read_text(encoding="utf8")
    refs = route_static_references(html, rsc)
    code = {k: (rebuilt_root / k).read_bytes()
            for k in refs if "/app/predictive-revenue/page-" in k}
    plan, additions = plan_rebased_delta(live_index, built_index, html, rsc, code)

    tmp = output_root.with_name(output_root.name + ".incomplete")
    if tmp.exists() or tmp.is_symlink():
        raise ReleaseHeld("PRIVATE_STAGE_TEMP_PATH_ALREADY_EXISTS")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copytree(live_root, tmp, symlinks=False)
        for rel in sorted(REPLACE | additions):
            src = rebuilt_root / rel
            dst = tmp / rel
            if src.is_symlink() or not src.is_file() or dst.is_symlink():
                raise ReleaseHeld("REBUILT_RELEASE_FILE_UNSAFE")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        index = read_index(tmp)
        changed = {k for k in live_index if live_index[k] != index.get(k)}
        added = set(index) - set(live_index)
        if changed != REPLACE or added != additions or set(live_index) - set(index):
            raise ReleaseHeld("REBASED_CANDIDATE_SCOPE_INVALID")
        if any(index[k] != live_index[k] for k in LIVE_DRIFT):
            raise ReleaseHeld("LATER_INDUSTRY_OWNER_WORK_WOULD_BE_LOST")
        if live_index != read_index(live_root):
            raise ReleaseHeld("LIVE_SITE_CONCURRENTLY_CHANGED_DURING_PRIVATE_COPY")
        if built_index != read_index(rebuilt_root):
            raise ReleaseHeld("REBUILT_SOURCE_CONCURRENTLY_CHANGED_DURING_PRIVATE_COPY")
        receipt = {
            "schema_version": SCHEMA,
            "status": "OFFLINE_REBASED_CTA_SAAS_CANDIDATE_NOT_OWNER_APPROVED",
            "mode": "OBSERVE",
            "execution_authority": "none",
            "source": source,
            "build": plan,
            "source_live_inventory_sha256": index_digest(live_index),
            "rebased_candidate_inventory_sha256": index_digest(index),
            "rebased_candidate_file_count": len(index),
            "old_site_owner_pinned_receipt_matches_live": False,
            "independent_astra_website_owner_approval_verified": False,
            "original_founder_exact_payload_approval_carries_over": False,
            "new_founder_approval_verified": False,
            "production_publication_authorized": False,
            "production_mutated": False,
            "static_route_deployed": False,
            "customer_enquiry_submitted": False,
            "smart_crm_writes": False,
            "outbound_sent": False,
            "money_moved": False,
            "actual_revenue_verified": False,
            "private_candidate_path": str(output_root),
        }
        os.replace(tmp, output_root)
        return receipt
    except Exception:
        if tmp.exists() and tmp.is_dir() and not tmp.is_symlink():
            shutil.rmtree(tmp)
        raise
