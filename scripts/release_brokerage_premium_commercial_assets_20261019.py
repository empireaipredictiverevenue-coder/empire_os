#!/usr/bin/env python3
"""Surgical publication of one reviewed /commercial HTML and additive assets.

No gateway/service restart, no form POST, no checkout, mail, DB or other page
mutation. An exact byte-pinned live HTML and staged page is required.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
import os
from pathlib import Path
import shutil
import tempfile
import urllib.request
from urllib.error import URLError

LIVE = Path("/srv/empire_os/apps/empire-public-site/out")
STAGED = Path("/home/ubuntu/empire_worktrees/brokerage_premium_exact_live_site_20261019/apps/empire-public-site/out")
BACKUP = Path("/home/ubuntu/empire_worktrees/brokerage_premium_exact_live_site_20261019/release_receipts")
EXPECTED_OLD = "7566e7711d46bbed84651db4967d47636e9c6cb13a096107d524d3bd73568d9c"
EXPECTED_NEW = "89e78031318d3a0a3cba2d9e23289bce52e9e3401fb90b1897dab8924d7f9567"
PREMIUM_PATH = b"/v1/checkout/brokerage/premium-discovery"

class Visible(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip=0
        self.strings=[]
        self.scripts=[]
    def handle_starttag(self, tag, attrs):
        if tag in {"script","style"}:self.skip+=1
        if tag=="script":
            v=dict(attrs).get("src")
            if isinstance(v,str):self.scripts.append(v)
    def handle_endtag(self,tag):
        if tag in {"script","style"}:self.skip-=1
    def handle_data(self,data):
        if not self.skip and data.strip():self.strings.append(data.strip())

def digest(data:bytes)->str:
    return sha256(data).hexdigest()

@dataclass(frozen=True)
class Evidence:
    baseline:bytes
    candidate:bytes
    added:tuple[Path,...]
    new_page_js:str

def plan(live:Path=LIVE, staged:Path=STAGED)->Evidence:
    a=(live/"commercial.html").read_bytes()
    b=(staged/"commercial.html").read_bytes()
    if digest(a)!=EXPECTED_OLD: raise ValueError("LIVE_COMMERCIAL_HTML_CHANGED")
    if digest(b)!=EXPECTED_NEW:raise ValueError("STAGED_PREMIUM_HTML_CHANGED")
    text_a=Visible();text_b=Visible()
    text_a.feed(a.decode("utf-8"));text_b.feed(b.decode("utf-8"))
    if len(text_a.strings)!=109 or text_a.strings!=text_b.strings:
        raise ValueError("VISIBLE_COMMERCIAL_CONTENT_NOT_PRESERVED")
    page_js=[v for v in text_b.scripts
             if v.startswith("/_next/static/chunks/app/commercial/page-")
             and v.endswith(".js")]
    if len(page_js)!=1:raise ValueError("PREMIUM_PAGE_BUNDLE_NOT_UNIQUE")
    js=staged/page_js[0].lstrip("/")
    if (not js.is_file() or js.stat().st_size>8_000_000
        or PREMIUM_PATH not in js.read_bytes()
        or b"Request an intelligence scope" not in js.read_bytes()):
        raise ValueError("PREMIUM_COMPONENT_NOT_COMPILED_INTO_EXACT_PAGE")
    for url in text_b.scripts:
        if not url.startswith("/_next/static/"):continue
        path=staged/url.lstrip("/")
        if not path.is_file():raise ValueError("REFERENCED_JS_NOT_IN_CANDIDATE")
    staged_static=staged/"_next/static"
    live_static=live/"_next/static"
    if not staged_static.is_dir() or not live_static.is_dir():
        raise ValueError("STATIC_BUILD_ASSETS_MISSING")
    additions=[]
    for path in staged_static.rglob("*"):
        if not path.is_file():continue
        relative=path.relative_to(staged_static)
        if ".." in relative.parts or path.is_symlink():
            raise ValueError("UNSAFE_STATIC_SOURCE_ASSET")
        current=live_static/relative
        if current.exists():
            if not current.is_file() or current.is_symlink() or digest(current.read_bytes())!=digest(path.read_bytes()):
                raise ValueError("EXISTING_SHARED_STATIC_ASSET_CONFLICT")
        else:
            additions.append(relative)
    if len(additions)!=11:
        raise ValueError("CHANGED_PREMIUM_STATIC_DELTA_NEEDS_REVIEW")
    if sum((staged_static/x).stat().st_size for x in additions)>2_000_000:
        raise ValueError("NEW_ASSET_PAYLOAD_TOO_LARGE")
    return Evidence(a,b,tuple(sorted(additions)),page_js[0])

def _atomic_write(path:Path,contents:bytes)->None:
    fd,tmp=tempfile.mkstemp(prefix=".premium-commercial-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(contents);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o644)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def install(evidence:Evidence,*,live:Path=LIVE,staged:Path=STAGED,backup:Path=BACKUP)->dict:
    if digest((live/"commercial.html").read_bytes())!=EXPECTED_OLD:
        raise ValueError("CONCURRENT_HTML_CHANGE_REFUSAL")
    backup.mkdir(parents=True,exist_ok=True)
    original=backup/("commercial-"+EXPECTED_OLD[:16]+".html")
    if original.exists():
        if original.read_bytes()!=evidence.baseline:
            raise ValueError("ROLLBACK_SNAPSHOT_CONFLICT")
    else:
        fd,tmp=tempfile.mkstemp(prefix=".rollback-",dir=str(backup))
        try:
            with os.fdopen(fd,"wb") as f:
                f.write(evidence.baseline);f.flush();os.fsync(f.fileno())
            os.chmod(tmp,0o600)
            os.replace(tmp,original)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    for relative in evidence.added:
        src=staged/"_next/static"/relative
        dst=live/"_next/static"/relative
        dst.parent.mkdir(parents=True,exist_ok=True)
        if dst.exists():
            if digest(dst.read_bytes())!=digest(src.read_bytes()):
                raise ValueError("NEW_ASSET_CONCURRENT_COLLISION")
            continue
        fd,tmp=tempfile.mkstemp(prefix=".prem-",dir=str(dst.parent))
        try:
            with os.fdopen(fd,"wb") as f:
                f.write(src.read_bytes());f.flush();os.fsync(f.fileno())
            os.chmod(tmp,0o644)
            os.replace(tmp,dst)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    _atomic_write(live/"commercial.html",evidence.candidate)
    if digest((live/"commercial.html").read_bytes())!=EXPECTED_NEW:
        _atomic_write(live/"commercial.html",evidence.baseline)
        raise ValueError("POST_SWAP_PAGE_DIGEST_FAILED_ROLLED_BACK")
    return {"status":"SURGICAL_BROKERAGE_PREMIUM_COMMERCIAL_HTML_PUBLISHED",
            "backup_sha256":EXPECTED_OLD,
            "new_html_sha256":EXPECTED_NEW,
            "new_static_assets":len(evidence.added),
            "site_other_pages_changed":False,
            "database_writes":False,"payments_changed":False,
            "outbound_sent":False,"public_premium_api_activated":False}

def main(argv:list[str]|None=None)->int:
    a=argparse.ArgumentParser()
    a.add_argument("--preflight",action="store_true")
    a.add_argument("--apply-founder-approved-premium-commercial-page",action="store_true")
    o=a.parse_args(argv)
    if o.preflight==o.apply_founder_approved_premium_commercial_page:
        print("HOLD_EXACTLY_ONE_RELEASE_FLAG_REQUIRED");return 2
    try:
        proof=plan()
        print("BROKERAGE_PREMIUM_EXACT_LIVE_SITE_CONTENT_AND_ASSET_PREFLIGHT_PASS")
        print("ADD_ONLY_STATIC_ASSETS",len(proof.added))
        if o.preflight:return 0
        response=install(proof)
        print(__import__("json").dumps(response,sort_keys=True))
        return 0
    except (OSError,ValueError,UnicodeError) as exc:
        print("BROKERAGE_PREMIUM_SITE_RELEASE_HOLD="+str(exc))
        return 2

if __name__=="__main__":raise SystemExit(main())
