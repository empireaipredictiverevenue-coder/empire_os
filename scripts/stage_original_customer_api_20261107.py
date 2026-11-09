"""Stage original packaged customer API into the existing EmpireOS package.

Dry/isolated staging only. No DB connection, route mount or service restart.
Pin full archive SHA256 and per-file source SHA256. Never overwrite a staged package.
"""
from __future__ import annotations
import argparse, hashlib, json, stat, zipfile
from pathlib import Path

PINNED_ARCHIVE_SHA256="718e752945abd27a20ca28f168f8e20e3b7fe0011151a1a270af76cd0c090ff5"
SOURCE_FILES=("durable_store.py","private_api.py","durable_api.py",
              "empiredb_metering_adapter.py","gateway_candidate_entrypoint.py")
REWRITES={
 "durable_api.py":{
  "from gateway_attestation import verify_gateway_attestation":"from empire_os.predictive_cloud_gateway_attestation import verify_gateway_attestation",
  "from durable_store import DurablePilotStore, ActiveTenant, AdmissionError":"from .durable_store import DurablePilotStore, ActiveTenant, AdmissionError",
  "from private_api import AuditRequest, SearchRequest, parse_safe_http_url":"from .private_api import AuditRequest, SearchRequest, parse_safe_http_url"},
 "empiredb_metering_adapter.py":{
  "from durable_store import ActiveTenant, AdmissionError":"from .durable_store import ActiveTenant, AdmissionError"},
 "gateway_candidate_entrypoint.py":{
  "from durable_api import create_metered_private_app":"from .durable_api import create_metered_private_app",
  "from empiredb_metering_adapter import EmpireDbMeteringStore":"from .empiredb_metering_adapter import EmpireDbMeteringStore"}}

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def stage(archive:Path,dest:Path,expected_sha256:str)->dict:
    if not archive.is_file() or archive.is_symlink():raise ValueError("original archive missing or unsafe")
    b=archive.read_bytes()
    if expected_sha256!=PINNED_ARCHIVE_SHA256 or sha(b)!=expected_sha256:
        raise ValueError("wrong original customer API archive hash")
    if dest.exists() or dest.is_symlink() or not dest.parent.is_dir():
        raise ValueError("destination exists or parent missing")
    original={}
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError("duplicate zip entries")
        for name in SOURCE_FILES:
            entries=[x for x in names if x.endswith("/"+name) and x.count("/")==1]
            if len(entries)!=1:raise ValueError("missing or duplicate source "+name)
            info=z.getinfo(entries[0])
            if info.file_size>256000 or stat.S_ISLNK(info.external_attr>>16):
                raise ValueError("unsafe source file")
            original[name]=z.read(info)
    converted={}
    for name,body in original.items():
        text=body.decode("utf-8","strict")
        for before,after in REWRITES.get(name,{}).items():
            if text.count(before)!=1:raise ValueError("original import contract drift: "+name)
            text=text.replace(before,after)
        converted[name]=text.encode()
    dest.mkdir(mode=0o700)
    for name,body in converted.items():
        path=dest/name;path.write_bytes(body);path.chmod(0o600)
    (dest/"__init__.py").write_text('"""Original Empire customer API, guarded import only."""\n')
    manifest={"archive_sha256":sha(b),
              "original_source_sha256":{n:sha(v) for n,v in original.items()},
              "converted_sha256":{n:sha(v) for n,v in converted.items()},
              "only_import_rewrites":True,"autodeploy":False,"external_access":False}
    (dest/"SOURCE_PROVENANCE.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return manifest

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--archive",required=True,type=Path)
    ap.add_argument("--dest",required=True,type=Path)
    ap.add_argument("--expected-sha256",required=True)
    args=ap.parse_args()
    print(json.dumps(stage(args.archive,args.dest,args.expected_sha256),indent=2))
