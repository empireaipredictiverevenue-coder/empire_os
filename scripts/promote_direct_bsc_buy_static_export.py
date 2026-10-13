"""Promote ONLY the buyer checkout static export and hashed Next assets.

No broad website redeploy, no DB, no systemd restart or paid action.
Must have an independently built, SHA256-verified manifest checked into Git.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ROOT=Path("/srv/empire_os")
MANIFEST=ROOT/"docs/commercial/DIRECT_BSC_BUY_UI_STATIC_EXPORT_MANIFEST_20261013.json"
BACKUP=Path("/var/tmp/empire-direct-bsc-buy-static-backup-20261013")
APPROVAL="--approved-direct-bsc-buy-page-only"


def sha(path: Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda:f.read(256*1024),b""):
            h.update(part)
    return h.hexdigest()


def _exact_git(path: str)->None:
    cmd=["git","-c",f"safe.directory={ROOT}"]
    def git(*args: str):
        p=subprocess.run(cmd+list(args),cwd=ROOT,text=True,
             stdout=subprocess.PIPE,stderr=subprocess.PIPE,
             check=True,timeout=8)
        return p.stdout.strip()
    if git("status","--porcelain","--",path) or (
        git("hash-object",path)!=git("rev-parse","HEAD:"+path)
    ):
        raise ValueError("source or manifest commit drift")


def _validated()->tuple[dict,Path,Path]:
    for rel in (
        "apps/empire-public-site/src/app/buy/page.tsx",
        "docs/commercial/DIRECT_BSC_BUY_UI_STATIC_EXPORT_MANIFEST_20261013.json",
        "scripts/promote_direct_bsc_buy_static_export.py",
    ):
        _exact_git(rel)
    data=json.loads(MANIFEST.read_text())
    if data.get("schema_version")!="empire.direct-bsc-buyer-ui-static-release.v1":
        raise ValueError("unreviewed export version")
    preview=Path(data["preview_root"])
    live=Path(data["live_root"])
    if (preview!=Path("/var/tmp/empire-direct-bsc-buyer-ui-preview-20261013/out")
        or live!=ROOT/"apps/empire-public-site/out"
        or preview.is_symlink() or live.is_symlink()
        or not preview.is_dir() or not live.is_dir()):
        raise ValueError("unreviewed export directories")
    source=ROOT/"apps/empire-public-site/src/app/buy/page.tsx"
    if sha(source)!=data["buyer_source_sha256"]:
        raise ValueError("buyer checkout source changed")
    buy=preview/"buy.html"
    if buy.is_symlink() or not buy.is_file() or sha(buy)!=data["buy_sha256"]:
        raise ValueError("buy HTML hash mismatch")
    old=live/"buy.html"
    if old.is_symlink() or not old.is_file() or sha(old)!=data["prior_live_buy_sha256"]:
        raise ValueError("existing buy page changed since preview")
    assets=data.get("assets")
    if not isinstance(assets,list) or not 1<=len(assets)<=150:
        raise ValueError("unbounded export assets")
    seen=set()
    total=0
    for a in assets:
        name=a.get("path")
        if (type(name) is not str or name in seen or not name.startswith("_next/static/")
            or not all(x not in {".","..",""} for x in Path(name).parts)
            or Path(name).is_absolute() or any(c not in
               "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-./[]"
               for c in name)):
            raise ValueError("unapproved asset path")
        seen.add(name)
        src=preview/name
        dest=live/name
        if src.is_symlink() or not src.is_file() or src.stat().st_size!=a["size"]:
            raise ValueError("missing or altered export asset")
        if sha(src)!=a["sha256"]:
            raise ValueError("export asset digest drift")
        if dest.is_symlink() or (dest.exists() and sha(dest)!=a["sha256"]):
            raise ValueError("existing immutable asset collision")
        total+=a["size"]
    if total>20_000_000:
        raise ValueError("unbounded export size")
    if BACKUP.exists() or BACKUP.is_symlink():
        raise ValueError("existing backup; inspect before retry")
    return data,preview,live


def _new_file(source: Path,target: Path)->None:
    if target.exists() or target.is_symlink():
        raise ValueError("destination already populated")
    target.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
    if any(p.is_symlink() for p in (target.parent,*target.parent.parents)
           if p.exists() and p!=Path("/")):
        raise ValueError("symlinked destination ancestor")
    fd,temp=tempfile.mkstemp(prefix=".bsc-buy-",dir=target.parent)
    try:
        with os.fdopen(fd,"wb") as out,source.open("rb") as inp:
            shutil.copyfileobj(inp,out)
            out.flush();os.fsync(out.fileno())
        os.chmod(temp,0o644)
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _serve_hash()->str:
    req=urllib.request.Request("http://127.0.0.1/buy",
                               headers={"Host":"empire-ai.co.uk"})
    with urllib.request.urlopen(req,timeout=8) as response:
        if response.status!=200:
            raise ValueError("gateway buy not serving")
        body=response.read(90_000)
    return hashlib.sha256(body).hexdigest()


def apply()->dict:
    data,preview,live=_validated()
    BACKUP.mkdir(mode=0o700)
    backup=BACKUP/"buy.html"
    shutil.copy2(live/"buy.html",backup)
    if sha(backup)!=data["prior_live_buy_sha256"]:
        raise ValueError("buy backup not verified")
    new_assets=0
    try:
        for a in data["assets"]:
            asset=live/a["path"]
            if not asset.exists():
                _new_file(preview/a["path"],asset)
                new_assets+=1
            if sha(asset)!=a["sha256"]:
                raise ValueError("new asset did not match manifest")
        target=live/"buy.html"
        # Replacement is atomic, no unrelated HTML export touched.
        fd,temp=tempfile.mkstemp(prefix=".bsc-buy-page-",dir=live)
        try:
            with os.fdopen(fd,"wb") as out, (preview/"buy.html").open("rb") as inp:
                shutil.copyfileobj(inp,out)
                out.flush();os.fsync(out.fileno())
            os.chmod(temp,0o644)
            os.replace(temp,target)
        finally:
            if os.path.exists(temp):os.unlink(temp)
        if sha(target)!=data["buy_sha256"] or _serve_hash()!=data["buy_sha256"]:
            raise ValueError("buyer checkout public readback mismatch")
    except Exception:
        if sha(live/"buy.html")!=data["prior_live_buy_sha256"]:
            fd,temp=tempfile.mkstemp(prefix=".bsc-buy-rollback-",dir=live)
            try:
                with os.fdopen(fd,"wb") as out,backup.open("rb") as inp:
                    shutil.copyfileobj(inp,out)
                    out.flush();os.fsync(out.fileno())
                os.chmod(temp,0o644)
                os.replace(temp,live/"buy.html")
            finally:
                if os.path.exists(temp):os.unlink(temp)
        raise
    return {"status":"CHECKOUT_BUY_STATIC_PAGE_RELEASE_VERIFIED",
            "only_checkout_page_changed":True,
            "new_immutable_assets":new_assets,
            "buyer_status_button_exported":True,
            "database_writes":False,"payment_execution":False,
            "services_restarted":False}


def main(argv: list[str]|None=None)->int:
    argv=sys.argv[1:] if argv is None else argv
    if argv!=["--apply",APPROVAL]:
        print(json.dumps({"status":"STAGED_NOT_APPLIED",
                          "checkout_static_page_untouched":True}))
        return 0 if not argv else 3
    try:
        result=apply()
    except Exception:
        print(json.dumps({"status":"HELD_BUY_PAGE_STATIC_RELEASE",
            "reconcile_backup_before_retry":True}))
        return 4
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
