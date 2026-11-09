"""Stage EXACT original source from the founder-supplied pinned archive subset.

One-time offline transfer helper for the existing original API import work.
No database, no deployment, no gateway service mutation, no new runtime API.
"""
from __future__ import annotations
import base64, hashlib, importlib.util, io, json, lzma, os, stat, tarfile, tempfile
from pathlib import Path

ROOT=Path("/home/ubuntu/empire_worktrees/predictive_cloud_founder_session_20261107")
TRANSFER=Path("/home/ubuntu/empire_releases/data_cloud_founder_session_candidate_20261107/original_source_pack_20261107.b64")
DEST=ROOT/"empire_os"/"predictive_cloud_customer_api"
PINNED_PACK_SHA="8582b01eb80fcf32359ea6c83a4a2b15859a9ee8832995562b9b0d4fcfe56ced"
PINNED_ARCHIVE_SHA="718e752945abd27a20ca28f168f8e20e3b7fe0011151a1a270af76cd0c090ff5"
PINNED={
 "durable_store.py":"569234de9bad6ddbb232dd91fb9758f45f077da4297707963fe838181ad22fd1",
 "private_api.py":"a9586b6c2363c6d4fafc5d242040d4b5f90c386b90b6387fff099b5cdf287846",
 "durable_api.py":"cb1822483218cd6fc276640e4b6f843869edc9030e59888c8175ef96a8f76568",
 "empiredb_metering_adapter.py":"81a108cd204a799b804a2f1d7dc33b9bc1a33b6e03efa8a5e3728aeada8a3eb2",
 "gateway_candidate_entrypoint.py":"23e8daa3702268cccfa269cd5bda2fd2e676f0dbfd707cf8a4ceb144eb56eeb4",
}
def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def main():
    if DEST.exists() or DEST.is_symlink():
        raise RuntimeError("destination already exists: do not overwrite owner code")
    if not TRANSFER.is_file() or TRANSFER.is_symlink():
        raise RuntimeError("missing private original source transfer")
    binary=base64.b64decode(TRANSFER.read_text().strip(),validate=True)
    if sha(binary)!=PINNED_PACK_SHA:
        raise RuntimeError("original source pack SHA mismatch")
    with tarfile.open(fileobj=io.BytesIO(lzma.decompress(binary)),mode="r:") as t:
        members=t.getmembers()
        if len(members)!=len(PINNED) or {m.name for m in members}!=set(PINNED):
            raise RuntimeError("unapproved original source files")
        originals={}
        for m in members:
            if not m.isfile() or m.size>256_000 or m.name not in PINNED:
                raise RuntimeError("unsafe or oversized original source")
            b=t.extractfile(m).read()
            if sha(b)!=PINNED[m.name]:raise RuntimeError("original source content SHA mismatch")
            originals[m.name]=b
    stager=ROOT/"scripts"/"stage_original_customer_api_20261107.py"
    spec=importlib.util.spec_from_file_location("original_data_cloud_import_conversion",stager)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if tuple(mod.SOURCE_FILES)!=tuple(PINNED) or mod.PINNED_ARCHIVE_SHA256!=PINNED_ARCHIVE_SHA:
        raise RuntimeError("original pinned source or stager drift")
    converted={}
    for name,body in originals.items():
        txt=body.decode("utf8","strict")
        for old,new in mod.REWRITES.get(name,{}).items():
            if txt.count(old)!=1:
                raise RuntimeError("unexpected import baseline: "+name)
            txt=txt.replace(old,new)
        converted[name]=txt.encode("utf8")
    tmp=Path(tempfile.mkdtemp(prefix=".original-data-cloud-import-",dir=str(DEST.parent)))
    try:
        tmp.chmod(0o700)
        for name,b in converted.items():
            f=tmp/name; f.write_bytes(b); f.chmod(0o600)
        (tmp/"__init__.py").write_text('"""Exact original Empire Data Cloud customer API, staging only."""\n')
        manifest={"source_archive_sha256":PINNED_ARCHIVE_SHA,"source_pack_sha256":PINNED_PACK_SHA,
                  "original_source_sha256":PINNED,"converted_sha256":{n:sha(b) for n,b in converted.items()},
                  "only_import_rewrites":True,"production_migration":False,
                  "public_gateway_activation":False,"customer_delivery_authorized":False}
        (tmp/"SOURCE_PROVENANCE.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
        os.rename(tmp,DEST)
    finally:
        if tmp.exists():
            import shutil;shutil.rmtree(tmp)
    print(json.dumps({"status":"ORIGINAL_CUSTOMER_API_SOURCE_STAGED_VERIFIED",
       "source_archive_sha256":PINNED_ARCHIVE_SHA,
       "source_pack_sha256":PINNED_PACK_SHA,
       "source_file_count":len(PINNED),
       "production_changes":False,
       "client_routes_activated":False}))
if __name__=="__main__":main()
