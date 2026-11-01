"""Guarded one-shot direct BSC buyer-status release.

Never enables payment execution, revenue recognition, automatic approval,
outbound email or wallet transfers. Existing orders remain founder-authorised.
Only explicit --apply with exact founder release flag can modify systemd.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

from empire_os.direct_bsc_status_key_custody import (
    KEY_FILE,read_key,install_key,
)
from scripts.provision_direct_bsc_buyer_status_logins import (
    checkout_financial_execution_held,_verified_controlled_order_release
)

ROOT=Path("/srv/empire_os")
DROP_DIR=Path("/etc/systemd/system/empire-self-serve-checkout.service.d")
TARGET=DROP_DIR/"50-direct-bsc-buyer-status-release.conf"
LOGIN_FILE=Path("/etc/empire_direct_bsc_buyer_status.env")
APPROVAL="--approved-direct-bsc-buyer-status-release-only"

class SafeReleaseHold(RuntimeError):
    """A fixed stage identifier only; no secrets, URLs or HTTP bodies."""

    def __init__(self,stage: str):
        self.stage=stage
        super().__init__("direct_bsc_status_release_held")

REVIEW_FILES=(
    "empire_os/direct_bsc_status_key_custody.py",
    "empire_os/direct_bsc_buyer_receipt_bridge.py",
    "empire_os/direct_bsc_buyer_checkout_release.py",
    "empire_os/direct_bsc_buyer_status_runtime.py",
    "empire_os/direct_bsc_buyer_status_http.py",
    "empire_os/direct_bsc_buyer_status_private_reader.py",
    "empire_os/direct_bsc_buyer_status_private_issuer.py",
    "empire_os/self_serve_checkout_api.py",
    "empire_os/public_gateway.py",
    "apps/empire-public-site/src/app/buy/page.tsx",
    "docs/commercial/DIRECT_BSC_BUY_UI_STATIC_EXPORT_MANIFEST_20261013.json",
    "scripts/deploy_direct_bsc_buyer_status_release.py",
)
DROPIN=(
    "[Service]\n"
    "# Exact founder-gated first-party buyer-status release only.\n"
    "# NO payment approval, settlement, send, new role or treasury change.\n"
    "LoadCredential=empire_direct_bsc_buyer_status_hmac.key:"
    "/etc/empire_direct_bsc_buyer_status_hmac.key\n"
    "LoadCredential=empire_direct_bsc_buyer_status.env:"
    "/etc/empire_direct_bsc_buyer_status.env\n"
    "Environment=EMPIRE_DIRECT_BSC_BUYER_STATUS_RELEASE=ON\n"
)


def _run(*args: str, timeout: float=20)->str:
    result=subprocess.run(
        args,check=True,timeout=timeout,cwd=ROOT,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
    )
    return result.stdout.strip()


def _reviewed()->None:
    for filename in REVIEW_FILES:
        local=ROOT/filename
        if not local.is_file():
            raise ValueError("reviewed source missing")
        path_check=_run("git","-c",f"safe.directory={ROOT}","status",
                        "--porcelain","--",filename)
        if path_check:
            raise ValueError("reviewed source changed")
        sha=_run("git","-c",f"safe.directory={ROOT}","hash-object",filename)
        committed=_run("git","-c",f"safe.directory={ROOT}","rev-parse",
                       "HEAD:"+filename)
        if sha!=committed:
            raise ValueError("source does not match committed release")


def _health()->dict:
    request=urllib.request.Request("http://127.0.0.1:8098/health")
    with urllib.request.urlopen(request,timeout=5) as response:
        result=json.load(response)
    if not isinstance(result,dict):
        raise ValueError("invalid checkout health")
    return result


def _snapshot()->tuple:
    data=_health()
    return tuple(data.get(field) for field in (
        "status","checkout_settlement_mode",
        "payment_proposal_authorized",
        "binding_order_creation_authorized",
        "payment_execution","revenue_recognition",
    ))


def _verify_unit_targets()->None:
    if DROP_DIR.is_symlink() or not DROP_DIR.is_dir():
        raise ValueError("untrusted checkout drop-in directory")
    if TARGET.exists() or TARGET.is_symlink():
        raise ValueError("existing status drop-in requires reconciliation")
    unit=Path("/etc/systemd/system/empire-self-serve-checkout.service")
    gateway=Path("/etc/systemd/system/empire-public-gateway.service")
    for item in (unit,gateway):
        if item.is_symlink() or not item.is_file():
            raise ValueError("original unit missing")
    if not _verified_controlled_order_release():
        raise ValueError("existing founder-approved order release not verified")


def _verify_login_file()->None:
    if LOGIN_FILE.is_symlink() or not LOGIN_FILE.is_file():
        raise ValueError("dedicated DSN credential file absent")
    stat=LOGIN_FILE.stat()
    if stat.st_uid != 0 or stat.st_mode & 0o777 != 0o600:
        raise ValueError("dedicated DSN credential unsafe")
    result=_run(sys.executable,"-m",
          "scripts.inspect_direct_bsc_status_logins_readonly",
          "--verify-only",timeout=20)
    data=json.loads(result)
    if data.get("status")!="DEDICATED_STATUS_LOGINS_LIVE_READBACK_VERIFIED":
        raise ValueError("dedicated login readback failed")


def _chain_verified()->dict:
    from empire_os.self_serve_payment_readiness import verify_checkout_bsc_chain
    from empire_os.bsc_usdt_verifier import BSC_USDT_CONTRACT,BscUsdtConfig
    config=BscUsdtConfig(
        rpc_url="https://bsc-dataseed.bnbchain.org",
        treasury_address="0x1339b487046B0ad924a10c20b1791608EA8595a8",
        token_contract=BSC_USDT_CONTRACT,
        min_confirmations=12,
    )
    result=verify_checkout_bsc_chain(config=config)
    if result.get("chain_verified") is not True or result.get("chain_id")!=56 or result.get("token_decimals")!=18:
        raise ValueError("chain / canonical token not independently verified")
    return {
        "chain_verified":True,"chain_id":56,"token_decimals":18,
        "fresh_block_anchor":True,
    }


def _wait_until_services_ready(*, seconds: float=12.0) -> None:
    """Bounded, read-only startup wait; systemctl restart is not HTTP readiness."""
    import time
    deadline=time.monotonic()+seconds
    while True:
        try:
            snapshot=_health()
            if snapshot.get("status")=="online":
                req=urllib.request.Request(
                    "http://127.0.0.1/buy",
                    headers={"Host":"empire-ai.co.uk"},
                )
                with urllib.request.urlopen(req,timeout=2.0) as resp:
                    if resp.status==200:
                        return
        except (OSError,ValueError,TimeoutError):
            pass
        if time.monotonic() >= deadline:
            raise ValueError("checkout or gateway did not become HTTP-ready")
        time.sleep(0.25)


def _status_probe()->None:
    # Correctly formatted but never-issued fixed bearer. No DB writes,
    # no order UUID, no buyer PII, no bearer disclosed to logs.
    unknown="ecs1_"+"A"*43
    payload=json.dumps({"token":unknown}).encode("utf-8")
    for target,url in (
        ("PRIVATE","http://127.0.0.1:8098/v1/checkout/payment-status"),
        ("PUBLIC","http://127.0.0.1/v1/checkout/payment-status"),
    ):
        request=urllib.request.Request(
            url, data=payload,
            headers={"Origin":"https://empire-ai.co.uk",
                     "Sec-Fetch-Site":"same-origin",
                     "Content-Type":"application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request,timeout=15) as response:
                code=response.status
                body=json.load(response)
        except urllib.error.HTTPError as error:
            code=error.code
            body=json.loads(error.read())
        if code==404 and body=={"detail":"Not Found"}:
            raise SafeReleaseHold(target+"_STATUS_ROUTE_NOT_MOUNTED")
        if code==503 and body=={"error":"buyer_status_unavailable"}:
            raise SafeReleaseHold(target+"_STATUS_ROUTE_HELD_BY_RUNTIME")
        if code!=404 or body!={"error":"payment_status_unavailable"}:
            raise SafeReleaseHold(target+"_STATUS_RESPONSE_MISMATCH")


def _write_dropin()->None:
    fd,temp=tempfile.mkstemp(prefix=".empire-bsc-status-",dir=DROP_DIR)
    try:
        with os.fdopen(fd,"w") as file:
            file.write(DROPIN)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temp,0o644)
        os.replace(temp,TARGET)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


# The original October 13 manifest pins the older approved /buy HTML.
# Later, founder-approved 747->753 and 753->756 website releases changed
# that HTML WITHOUT replacing /buy in either scoped release. Check the two
# original signed-off, hash-pinned release *sources*, not a new manifest or a
# hash copied from the currently served page. This is read-only and specific
# to /buy; unrelated future site pages cannot erase checkout evidence.
PRICING_RELEASE_MANIFEST=Path(
    "/srv/empire_os/docs/commercial/original_release_evidence/"
    "RELEASE_PRICE_PINNED_MANIFEST_20261030.json"
)
SCOPED_RELEASE_MANIFEST=Path(
    "/srv/empire_os/docs/commercial/original_release_evidence/"
    "WEB_SCOPED_INTAKE_PINNED_MANIFEST_20261030.json"
)
PRICING_RELEASE_SHA="cd02971236fd268ead2ea261ffbea68cecda96dd7337dcb6f56774ec5c0463f7"
SCOPED_RELEASE_SHA="46eb6eafa943fa7f58d6eeb606c264617a0084ca953fcd836ad16939e932d55b"
APPROVED_LATER_BUY_SHA="435cd7b1fed3490998ec2ca74cd0fc68f1a6ff0a324a10adba6428def4e92552"
# Original ASTRA/Design Studio founder horizontal mark already published on
# Commercial. This *new* /buy page must have an independent, exact owner
# manifest and desktop+mobile private browser QA before it is accepted.
BUY_BRAND_RELEASE_MANIFEST=Path(
    "/srv/empire_os/docs/commercial/original_release_evidence/"
    "SCOPED_BUY_BRAND_MANIFEST_20261101.json"
)
BUY_BRAND_BROWSER_QA=Path(
    "/srv/empire_os/docs/commercial/original_release_evidence/"
    "BUY_BRAND_BROWSER_QA_20261101.json"
)
BUY_BRAND_MANIFEST_SHA="e91c7216ab336575a701105537fb850d9d682d059c570e2155d1ff04840f6554"
BUY_BRAND_QA_SHA="01222263be3b2bff473410a9f691401a5b039486e7417973c556f459eba8e721"
BUY_BRAND_HTML_SHA="fbdae60ae1741b43276253f3153dc0f7f7edd68a48e5df3ccaf878670e61c4dd"
BUY_BRAND_LOGO_SHA="55e98ad2ae182991d95908738135779102beb81818cd7c3607a3a49e1f2aa596"
BUY_BRAND_REPLACES=frozenset({
    "buy.html", "buy.txt", "buy/__next._tree.txt",
    "buy/__next._full.txt", "buy/__next.buy.__PAGE__.txt",
})
BUY_BRAND_ADDS=frozenset({
    "_next/static/css/93002b73242723fc.css",
    "_next/static/chunks/app/layout-ed51d8ad8107b67e.js",
    "_next/static/chunks/app/buy/page-4e23bc78c94f5a9c.js",
})


def _approved_brand_buy_sha256()->str:
    """Approve only the exact browser-reviewed newer logo/checkout HTML.

    Never derive the expected checksum from the mutable published HTML and
    never drop the original Oct 13 36 immutable-asset checks.
    """
    from hashlib import sha256
    def read_pinned(path:Path,checksum:str)->dict:
        if path.is_symlink() or not path.is_file() or path.stat().st_size>250000:
            raise ValueError("brand owner evidence missing")
        raw=path.read_bytes()
        if sha256(raw).hexdigest()!=checksum:
            raise ValueError("brand owner evidence digest drift")
        result=json.loads(raw)
        if not isinstance(result,dict):
            raise ValueError("brand owner evidence invalid")
        return result
    m=read_pinned(BUY_BRAND_RELEASE_MANIFEST,BUY_BRAND_MANIFEST_SHA)
    q=read_pinned(BUY_BRAND_BROWSER_QA,BUY_BRAND_QA_SHA)
    previous=_approved_later_checkout_buy_sha256()
    old=m.get("baseline_live_sha256")
    changed=m.get("replace_sha256")
    added=m.get("add_sha256")
    if (m.get("schema_version")!="empire.website.buy_brand_design_studio_scoped_release.v1"
            or m.get("source_brand")!="ASTRA original website owner logo already published on /commercial"
            or m.get("owner_source_commit")!="77b8be145"
            or m.get("brand_studio_commit")!="d72941ff7"
            or m.get("brandlockup_source_sha256")!="8637715cbbea797fc45168312c4e084f22c050f84e9410823b63c89729a4464e"
            or m.get("brand_asset_sha256")!=BUY_BRAND_LOGO_SHA
            or m.get("brand_asset_ref")!="/brand/empire-ai-primary-orbital-a-founder-approved.png"
            or m.get("source_art_reuse_only") is not True
            or m.get("no_new_brand_asset") is not True
            or m.get("baseline_live_count")!=758
            or m.get("final_count")!=761
            or m.get("unrelated_files_unchanged_count")!=753
            or m.get("buyer_main_visible_text_unchanged") is not True
            or m.get("founder_commercial_terms_unchanged") is not True
            or m.get("payment_flags_unchanged") is not True
            or m.get("checkout_runtime_unchanged") is not True
            or m.get("publication_performed") is not False
            or m.get("private_browser_qa_status")!="BUY_BRAND_PRIVATE_BROWSER_PASS"
            or m.get("private_browser_qa_sha256")!=BUY_BRAND_QA_SHA
            or not isinstance(old,dict) or len(old)!=758
            or old.get("buy.html")!=previous
            or not isinstance(changed,dict) or set(changed)!=BUY_BRAND_REPLACES
            or not isinstance(added,dict) or set(added)!=BUY_BRAND_ADDS
            or (set(changed)-set(old)) or (set(added)&set(old))
            or changed.get("buy.html")!=BUY_BRAND_HTML_SHA
            or len({**old,**changed,**added})!=761):
        raise ValueError("brand owner checkout scope lineage mismatch")
    if (q.get("schema_version")!="empire.website.buy_brand_exact_source_qa.v1"
            or q.get("status")!="BUY_BRAND_PRIVATE_BROWSER_PASS"
            or q.get("original_source_asset_sha")!=BUY_BRAND_LOGO_SHA
            or q.get("real_customer_post_attempts")!=0
            or q.get("payment_requests_created")!=0
            or q.get("live_site_mutated") is not False
            or q.get("missing_paths")!=[]
            or not isinstance(q.get("results"),list)
            or len(q["results"])!=2
            or {r.get("name") for r in q["results"]}!={"desktop","mobile"}
            or any(r.get("pass") is not True or r.get("headerLogo")!=m["brand_asset_ref"]
                   or r.get("footerLogo")!=m["brand_asset_ref"]
                   or r.get("termsUnchecked") is not True
                   or r.get("createPaymentButton") is not True
                   or r.get("errors") or r.get("failed") or r.get("blocked")
                   for r in q["results"])):
        raise ValueError("brand owner actual browser QA invalid")
    root=ROOT/"apps/empire-public-site/out"
    logo=root/m["brand_asset_ref"].lstrip("/")
    if logo.is_symlink() or not logo.is_file() or sha256(logo.read_bytes()).hexdigest()!=BUY_BRAND_LOGO_SHA:
        raise ValueError("brand owner original logo digest invalid")
    for filename,digest in added.items():
        asset=root/filename
        if asset.is_symlink() or not asset.is_file() or sha256(asset.read_bytes()).hexdigest()!=digest:
            raise ValueError("brand owner new immutable checkout asset mismatch")
    return BUY_BRAND_HTML_SHA




def _approved_later_checkout_buy_sha256()->str:
    """Follow two exact owner-reviewed scopes, never repin a live HTML file."""
    from hashlib import sha256

    def load_pinned(path: Path, digest: str) -> dict:
        if path.is_symlink() or not path.is_file() or path.stat().st_size>300000:
            raise ValueError("later website owner receipt absent")
        raw=path.read_bytes()
        if sha256(raw).hexdigest()!=digest:
            raise ValueError("later website owner receipt changed")
        data=json.loads(raw)
        if not isinstance(data,dict):
            raise ValueError("later website owner receipt invalid")
        return data

    pricing=load_pinned(PRICING_RELEASE_MANIFEST,PRICING_RELEASE_SHA)
    scoped=load_pinned(SCOPED_RELEASE_MANIFEST,SCOPED_RELEASE_SHA)
    if (pricing.get("schema_version")!="empire.website.predictive.focused_pricing.scoped_v1"
            or pricing.get("founder_publication_approval")!=
                 "2026-10-30 explicit: publish the pricing"
            or pricing.get("qa_status")!="PRIVATE_BROWSER_QA_PASS"
            or pricing.get("customer_checkout_and_terms_remain_disabled") is not True
            or pricing.get("no_database_checkout_card_payment_or_outbound_change") is not True
            or pricing.get("publication_performed") is not False
            or pricing.get("live_static_file_count")!=747
            or pricing.get("target_static_file_count")!=753
            or scoped.get("schema_version")!="empire.website.predictive.scoped_crm_form.v1"
            or scoped.get("merged_browser_qa_status")!="OFFLINE_SCOPED_CRM_BROWSER_PASS"
            or scoped.get("payment_or_binding_terms_authorized") is not False
            or scoped.get("no_real_database_customer_or_payment_calls") is not True
            or scoped.get("published") is not False
            or scoped.get("live_original_file_count")!=753
            or scoped.get("target_file_count")!=756):
        raise ValueError("later website owner release scope unverified")
    maps=[]
    for document,expected_count in ((pricing,747),(scoped,753)):
        base=document.get("live_all_sha256")
        replacements=document.get("replace_sha256")
        additions=document.get("add_sha256")
        if (not all(isinstance(x,dict) for x in (base,replacements,additions))
                or len(base)!=expected_count
                or set(replacements)&set(additions)
                or (set(replacements)-set(base))
                or (set(additions)&set(base))
                or "buy.html" in replacements
                or "buy.html" in additions):
            raise ValueError("later website owner hash inventory invalid")
        maps.append({**base,**replacements,**additions})
    if (len(maps[0])!=753 or maps[0]!=scoped["live_all_sha256"]
            or len(maps[1])!=756
            or pricing["live_all_sha256"].get("buy.html")!=APPROVED_LATER_BUY_SHA
            or scoped["live_all_sha256"].get("buy.html")!=APPROVED_LATER_BUY_SHA):
        raise ValueError("later website owner release lineage mismatch")
    return APPROVED_LATER_BUY_SHA


def _published_checkout_verified()->None:
    """Insist on the already-released, content-hashed buyer checkout UI."""
    from hashlib import sha256
    manifest=ROOT/"docs/commercial/DIRECT_BSC_BUY_UI_STATIC_EXPORT_MANIFEST_20261013.json"
    page=ROOT/"apps/empire-public-site/out/buy.html"
    if manifest.is_symlink() or page.is_symlink() or not manifest.is_file() or not page.is_file():
        raise ValueError("published checkout evidence absent")
    values=json.loads(manifest.read_text())
    observed_buy_sha=sha256(page.read_bytes()).hexdigest()
    if observed_buy_sha!=values.get("buy_sha256"):
        # The current approved /buy HTML differs from the October 13 source.
        # Do not accept a new hash from a mutable live file or rewrite the
        # original manifest. Later approved release lineage must prove it.
        if observed_buy_sha!=_approved_later_checkout_buy_sha256():
            try:
                approved_new_buy_sha=_approved_brand_buy_sha256()
            except (OSError,ValueError) as exc:
                raise ValueError("published checkout page not verified") from exc
            if observed_buy_sha!=approved_new_buy_sha:
                raise ValueError("published checkout page not verified")
    assets=values.get("assets")
    if type(assets) is not list or len(assets)>150:
        raise ValueError("published checkout asset manifest invalid")
    for entry in assets:
        name=entry.get("path") if type(entry) is dict else None
        if (type(name) is not str or not name.startswith("_next/static/")
            or any(part in {"",".",".."} for part in Path(name).parts)
            or any(ch not in
              "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-./[]"
              for ch in name)):
            raise ValueError("published checkout asset path invalid")
        asset=page.parent/name
        if asset.is_symlink() or not asset.is_file():
            raise ValueError("published checkout asset absent")
        if sha256(asset.read_bytes()).hexdigest()!=entry.get("sha256"):
            raise ValueError("published checkout immutable asset changed")


def release()->dict:
    if os.geteuid()!=0:
        raise ValueError("root release operator required")
    _reviewed()
    _published_checkout_verified()
    _verify_unit_targets()
    _verify_login_file()
    checkout_financial_execution_held()
    original=_snapshot()
    evidence=_chain_verified()
    if KEY_FILE.exists() or KEY_FILE.is_symlink():
        read_key()
        key_action="EXISTING_KEY_VERIFIED"
    else:
        install_key()
        key_action="NEW_KEY_CREATED_0600"
    changed=False
    phase="write_dropin"
    try:
        _write_dropin()
        changed=True
        phase="daemon_reload"
        _run("systemctl","daemon-reload")
        phase="restart_checkout"
        _run("systemctl","restart","empire-self-serve-checkout.service")
        phase="restart_gateway"
        _run("systemctl","restart","empire-public-gateway.service")
        phase="http_readiness"
        _wait_until_services_ready()
        phase="financial_snapshot"
        if _snapshot()!=original:
            raise ValueError("checkout financial admission changed")
        phase="financial_guards"
        checkout_financial_execution_held()
        phase="fresh_chain"
        _chain_verified()
        phase="private_and_public_status_probe"
        _status_probe()
    except Exception as exc:
        rollback_ok=False
        if changed:
            # Preserve the original key and financial release configuration.
            TARGET.unlink(missing_ok=True)
            try:
                _run("systemctl","daemon-reload")
                _run("systemctl","restart","empire-self-serve-checkout.service")
                _run("systemctl","restart","empire-public-gateway.service")
                rollback_ok=True
            except Exception:
                rollback_ok=False
        held=exc.stage if isinstance(exc,SafeReleaseHold) else phase
        # Report only fixed enums; never emit exception messages.
        raise SafeReleaseHold(
            held+("_ROLLBACK_OK" if rollback_ok else "_READBACK_REQUIRED")
        ) from None
    return {
        "status":"DIRECT_BSC_PRIVATE_BUYER_STATUS_RELEASE_VERIFIED",
        "key":key_action,
        "logins":"EXISTING_TWO_REUSED",
        "frontend_deployed":True,
        "status_token_issued":False,
        "public_status_route_unknown_token_denied":True,
        "order_gate_unchanged":True,
        "payment_execution":False,
        "revenue_recognition":False,
        **evidence,
    }


def main(argv: list[str]|None=None)->int:
    argv=sys.argv[1:] if argv is None else argv
    if argv!=["--apply",APPROVAL]:
        print(json.dumps({"status":"STAGED_NOT_APPLIED",
                          "separate_release_approval_required":True}))
        return 0 if not argv else 3
    try:
        result=release()
    except SafeReleaseHold as hold:
        print(json.dumps({
            "status":"HELD_RELEASE_OR_ROLLBACK_NEEDS_READBACK",
            "release_failure_stage":hold.stage,
            "no_secrets_printed":True,
            "do_not_retry_without_inspection":True,
        },sort_keys=True))
        return 4
    except Exception:
        print(json.dumps({
            "status":"HELD_RELEASE_OR_ROLLBACK_NEEDS_READBACK",
            "release_failure_stage":"PRECHECK_OR_UNKNOWN",
            "no_secrets_printed":True,
            "do_not_retry_without_inspection":True,
        },sort_keys=True))
        return 4
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
