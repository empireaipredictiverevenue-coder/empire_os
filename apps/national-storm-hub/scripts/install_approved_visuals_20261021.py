#!/usr/bin/env python3
"""Fail-closed local image asset installer for the isolated Storm Hub design worktree."""
import hashlib, json, os, sys, tempfile, zipfile
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
TARGET=BASE/"public"/"visuals"
WORKTREE=Path("/home/ubuntu/empire_worktrees/nsh_approved_visual_assets_20261021/apps/national-storm-hub")
EXPECTED={
"storm-hub-mark.webp":"50e587878ce20a25a4548202fa964a005ca5848ce6cedce2242e8c9c82c70cf3",
"national-storm-hub-logo.webp":"bfd0fb667f344c740cca1655aa46123f83960f2aaf819ba510c747a907bd6fdd",
"storm-prepare.webp":"5cc464b8303b41ed11b76c95da6cc91043eebad4ca08c937c8a75e029a2bfee3",
"storm-understand.webp":"194df28a3292b585b7bfaf1eeddffdf6ebefbca24bbf50c782e1dbc8a6e5332d",
"storm-recover.webp":"8e3df67456ed95ed5102651d0c5f1fba8e0f68c71b92b34c2f54295dbc446719",
"storm-intelligence-background.webp":"68d8bcf14a78967dc664199ad8ad2691590e8d0d2dae4aa194ecac5e17516f13",
}
def install(zip_path):
    if BASE.resolve()!=WORKTREE.resolve():raise ValueError("isolated_worktree_required")
    if not zip_path.is_file() or zip_path.stat().st_size>2_000_000:raise ValueError("archive_missing_or_unbounded")
    with zipfile.ZipFile(zip_path) as z:
        allowed={f"visuals/{name}" for name in EXPECTED}|{"MANIFEST.json"}
        names=z.namelist()
        if len(names)!=len(set(names)) or set(names)!=allowed:raise ValueError("unexpected_zip_entries")
        originals={}
        for name,digest in EXPECTED.items():
            data=z.read(f"visuals/{name}")
            if len(data)>1_000_000 or hashlib.sha256(data).hexdigest()!=digest:raise ValueError("digest_mismatch:"+name)
            if data[:4]!=b"RIFF" or data[8:12]!=b"WEBP":raise ValueError("invalid_webp:"+name)
            originals[name]=data
        manifest=json.loads(z.read("MANIFEST.json"))
        if sorted(manifest.get("visuals",{}))!=sorted(EXPECTED):raise ValueError("manifest_mismatch")
    TARGET.mkdir(parents=True,exist_ok=True)
    for name,data in originals.items():
        fd,tmp=tempfile.mkstemp(prefix=".nsh-",dir=TARGET)
        try:
            with os.fdopen(fd,"wb") as stream:stream.write(data)
            os.chmod(tmp,0o644);os.replace(tmp,TARGET/name)
        finally:
            if Path(tmp).exists():Path(tmp).unlink()
    return {"status":"STAGED_VERIFIED","count":len(originals),"production_changed":False}
if __name__=="__main__":
    try:print(json.dumps(install(Path(sys.argv[1]).resolve())))
    except (IndexError,OSError,ValueError,KeyError,zipfile.BadZipFile) as e:
        print(json.dumps({"status":"REJECTED","reason":str(e)[:150]}),file=sys.stderr)
        raise SystemExit(1)
