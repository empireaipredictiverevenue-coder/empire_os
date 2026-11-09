"""Bounded CRM search route release; no database writes or binding provisioning."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
import urllib.error

SERVICE = "empire-revenue-crm-pilot.service"
RELEASE = Path("/opt/empire-ai/crm-pilot-releases/smart-crm-work-queue-20261104v1")
STAGE = Path(__file__).resolve().parent
BACKUP = Path("/var/backups/empire-crm-search/route-20261109")
OLD = {
    "revenue_crm_api.py": "d5ce55e7306f27c56d2ff053e3bafbd73779860a7a53789aac32d0f949c16a05",
    "revenue_crm_search_growth.py": "e2bcb699a4ee9e21fceaf94bf9417f3851b04c8e29ab18c19185789a13be9d55",
    "revenue_crm_search_evidence_api.py": None,
}
NEW = {
    "revenue_crm_api.py": "e916552359d65f27696159b357d536b070cc7e0342d62f9bd0dbb3fa76672f1a",
    "revenue_crm_search_growth.py": "d6beff1ea4c483bf9ef4349c9c0412867d0a2f5ad51e745ab74874aef9426721",
    "revenue_crm_search_evidence_api.py": "fd213b4c1f703af860c40582ba2901c1dc97a3e3c2298ab97abed33de568995e",
}
def digest(p):
    if p.is_symlink():
        raise RuntimeError("symlink rejected: " + str(p))
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None

def run(args):
    return subprocess.check_output(args, text=True, timeout=30).strip()

def service_property(name):
    return run(["systemctl", "show", SERVICE, "-p", name, "--value"])

def preflight():
    if os.geteuid() != 0:
        raise RuntimeError("run with sudo for bounded database readback and release")
    if service_property("WorkingDirectory") != str(RELEASE):
        raise RuntimeError("CRM working directory changed")
    if "private_crm_original_v411_source_entrypoint_20261108:app" not in service_property("ExecStart"):
        raise RuntimeError("CRM entrypoint changed")
    if service_property("ActiveState") != "active":
        raise RuntimeError("CRM not active")
    for name, expected in OLD.items():
        if digest(RELEASE / "empire_os" / name) != expected:
            raise RuntimeError("deployed source changed: " + name)
    if digest(RELEASE / "empire_os/revenue_crm_transport.py") != "ec24791ed8a8d91914085f70a2f610c21415d77582a38734257eff62be4bf3c3":
        raise RuntimeError("CRM transport changed")
    for name, expected in NEW.items():
        if digest(STAGE / name) != expected:
            raise RuntimeError("candidate changed: " + name)
        compile((STAGE / name).read_text(), name, "exec")
    sql = """
BEGIN READ ONLY;
SET LOCAL statement_timeout='4s';
SELECT json_build_object(
 'body_matches', (SELECT md5(prosrc)='06b1cd54d49364214c954fe6a91418d8'
   AND prosecdef AND provolatile='s'
   AND proowner='empiredb_migrator'::regrole
   AND proconfig @> ARRAY['search_path=""','row_security=on']
   FROM pg_proc WHERE oid='public.empire_crm_search_evidence(uuid,uuid,text,text,integer)'::regprocedure),
 'binding_count', (SELECT count(*) FROM public.crm_search_site_bindings),
 'binding_acl_sealed', NOT EXISTS (
   SELECT 1 FROM pg_class c, LATERAL aclexplode(c.relacl) a
   WHERE c.oid='public.crm_search_site_bindings'::regclass AND a.grantee<>c.relowner),
 'reader_acl_sealed', NOT EXISTS (
   SELECT 1 FROM pg_proc p, LATERAL aclexplode(p.proacl) a
   WHERE p.oid='public.empire_crm_search_evidence(uuid,uuid,text,text,integer)'::regprocedure
     AND a.grantee NOT IN (p.proowner,'empire_revenue_crm_reader'::regrole)),
 'reader_execute', has_function_privilege('empire_revenue_crm_reader',
   'public.empire_crm_search_evidence(uuid,uuid,text,text,integer)','EXECUTE')
);
ROLLBACK;
"""
    raw = run(["/usr/sbin/runuser", "-u", "postgres", "--", "/usr/bin/psql",
               "-X", "-Atq", "-d", "empiredb", "-v", "ON_ERROR_STOP=1", "-c", sql])
    result = json.loads(raw)
    if result != {"body_matches": True, "binding_count": 0,
                  "binding_acl_sealed": True, "reader_acl_sealed": True, "reader_execute": True}:
        raise RuntimeError("database post-install verification failed: " + json.dumps(result))
    return result

def main():
    raise RuntimeError("WITHDRAWN: violates frozen CRM checksum; do not deploy")
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-readonly", action="store_true")
    parser.add_argument("--apply-founder-approved", action="store_true")
    args = parser.parse_args()
    if args.preflight_readonly == args.apply_founder_approved:
        parser.error("select exactly one operation")
    db = preflight()
    if args.preflight_readonly:
        print(json.dumps({"status": "PREFLIGHT_PASS", "database": db, "production_writes": False}))
        return
    if BACKUP.exists():
        raise RuntimeError("existing release backup; inspect previous attempt before retry")
    # Only two existing files are backed up, not the database or full application.
    BACKUP.mkdir(parents=True, mode=0o700)
    os.chmod(BACKUP, 0o700)
    for name, expected in OLD.items():
        if expected is not None:
            shutil.copyfile(RELEASE / "empire_os" / name, BACKUP / name)
            os.chmod(BACKUP / name, 0o600)
            if digest(BACKUP / name) != expected:
                raise RuntimeError("backup verification failed")
    (BACKUP / "manifest.json").write_text(json.dumps({"old": OLD, "new": NEW}, indent=2))
    # Recheck all preconditions immediately before changing source files.
    preflight()
    for name in NEW:
        destination = RELEASE / "empire_os" / name
        temporary = destination.with_name(name + ".crm-search-new")
        with temporary.open("xb") as stream:
            stream.write((STAGE / name).read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, destination)
        if digest(destination) != NEW[name]:
            raise RuntimeError("installed hash mismatch: " + name)
    subprocess.run(["systemctl", "restart", SERVICE], check=True, timeout=45)
    url = ("http://127.0.0.1:8783/v1/revenue-crm/prospects/"
           "00000000-0000-0000-0000-000000000000/search-growth"
           "?site_id=00000000-0000-0000-0000-000000000000&query=release-check&engine=release-check")
    verified = False
    for attempt in range(15):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                raise RuntimeError("unsigned route unexpectedly succeeded")
        except urllib.error.HTTPError as error:
            body = json.loads(error.read())
            if error.code == 401 and body.get("detail") == "authenticated_crm_scope_required":
                verified = True
                break
            raise RuntimeError("unexpected unsigned response: " + str(error.code))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1)
    if not verified or service_property("ActiveState") != "active":
        raise RuntimeError("runtime verification failed; preserve backup and inspect, do not retry")
    receipt = {"status": "ROUTE_INSTALLED_UNSIGNED_401_VERIFIED",
               "database": db, "installed": NEW, "backup": str(BACKUP),
               "service_restarted": SERVICE, "database_writes": False,
               "signed_founder_session_verified": False}
    (BACKUP / "receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt))

if __name__ == "__main__":
    main()
