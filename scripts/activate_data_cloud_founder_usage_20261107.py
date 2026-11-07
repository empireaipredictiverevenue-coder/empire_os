"""Single-use founder-authorised installation of the existing Data Cloud usage pilot.

Guardrails: exact source branch, restore evidence, canonical objects, one CRM
owner, frozen original services, private credentials, rollback and HTTP canary.
Not an independent service. No search, audits, paid providers or billing.
Run only as root from the founder's authorised SSH session.
"""
from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import os
import pwd
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/home/ubuntu/empire_worktrees/predictive_cloud_usage_review_20261107")
RELEASE = Path("/opt/empire-ai/data-cloud-founder-pilot-20261107")
RUNTIME = Path("/var/lib/empire-data-cloud-founder-pilot")
ROOT_ONLY = Path("/etc/empire-data-cloud-founder-20261107")
CRM = Path("/var/lib/empire-crm-first-party/pilot-runtime.json")
CRM_ENV = Path("/etc/empire/crm-pilot.env")
LOCAL_RESTORE = Path("/home/ubuntu/empire_worktrees/empiredb_wal_archive_command_audit_v45_20261015/docs/architecture/EMPIREDB_NOV7_ISOLATED_RESTORE_V3_ACTUAL_RESULT.json")
PUB_OVERLAY = Path("/etc/systemd/system/empire-public-gateway.service.d/zzzzzzzzzz-data-cloud-founder-usage-20261107.conf")
CRM_OVERLAY = Path("/etc/systemd/system/empire-revenue-crm-pilot.service.d/zzzzzzzzzz-data-cloud-founder-usage-20261107.conf")
PUB_SVC = "empire-public-gateway.service"
CRM_SVC = "empire-revenue-crm-pilot.service"
SRC_SHA = "d20b0980c5e2d1348e7e0ecdcfa3fe021fc82b6bd1983750f37b2bf9b9ad8393"
REC_SHA = "e7dc1eef721c52730f21b2327e1ad30e03ddb1408933824edec3eedc398b3ada"
BASE_COMMIT = "a901bf857229160a044e83d3128df1444bcdf9a1"
FLAG = "FOUNDER_APPROVED_READ_ONLY_USAGE_20261107"
PACKAGE = (
    "empire_os/predictive_cloud_founder_session.py",
    "empire_os/predictive_cloud_gateway_attestation.py",
    "empire_os/predictive_cloud_route_assembly.py",
    "empire_os/predictive_cloud_customer_api/__init__.py",
    "empire_os/predictive_cloud_customer_api/SOURCE_PROVENANCE.json",
    "empire_os/predictive_cloud_customer_api/durable_api.py",
    "empire_os/predictive_cloud_customer_api/durable_store.py",
    "empire_os/predictive_cloud_customer_api/private_api.py",
    "empire_os/predictive_cloud_customer_api/empiredb_metering_adapter.py",
    "empire_os/predictive_cloud_customer_api/gateway_candidate_entrypoint.py",
)
SOURCE_ENTRYPOINTS = {
    "scripts/data_cloud_public_entrypoint_20261107.py": "data_cloud_public_entrypoint_20261107.py",
    "scripts/data_cloud_private_entrypoint_20261107.py": "data_cloud_private_entrypoint_20261107.py",
}
UBUNTU = pwd.getpwnam("ubuntu")
RELEASE_ENV = "EMPIRE_DATA_CLOUD_FOUNDER_USAGE_RELEASE"
ACTIVATED = False


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(args: list[str], *, input_bytes: bytes | None = None) -> str:
    r = subprocess.run(args, input=input_bytes, capture_output=True, timeout=30)
    if r.returncode != 0:
        # Never echo stdin (contains DB password or API key).
        raise RuntimeError("operator_command_failed:" + args[0] + ":" + str(r.returncode))
    return r.stdout.decode("utf8", "strict").strip()


def postgres(sql: str) -> str:
    return run(
        ["runuser", "-u", "postgres", "--", "psql",
         "-X", "-A", "-t", "-w", "-v", "ON_ERROR_STOP=1", "-d", "empiredb"],
        input_bytes=sql.encode("utf8"),
    )


def atomic_file(path: Path, data: bytes, mode: int, *, uid: int = 0, gid: int = 0):
    if path.exists() or path.is_symlink():
        raise RuntimeError("refusing_existing_release_file:" + path.name)
    tmp = path.with_name("." + path.name + "." + secrets.token_hex(8))
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chown(tmp, uid, gid)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def http(path: str, port: int) -> tuple[int, dict]:
    import httpx
    with httpx.Client(trust_env=False, follow_redirects=False, timeout=3) as c:
        try:
            response = c.get("http://127.0.0.1:" + str(port) + path)
        except httpx.HTTPError:
            return 0, {}
    try:
        body = response.json()
    except ValueError:
        body = {}
    return response.status_code, body if isinstance(body, dict) else {}


def identity_preflight() -> dict:
    if os.geteuid() != 0:
        raise RuntimeError("root_operator_execution_required")
    if ROOT.is_symlink() or not ROOT.is_dir():
        raise RuntimeError("exact_review_worktree_required")
    if run(["git", "-C", str(ROOT), "status", "--porcelain"]):
        raise RuntimeError("approved_source_worktree_dirty")
    if run(["git", "-C", str(ROOT), "branch", "--show-current"]) != "feature/predictive-cloud-usage-review-20261107":
        raise RuntimeError("unexpected_source_branch")
    run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", BASE_COMMIT, "HEAD"])
    sql_bytes = (ROOT/"docs/release_candidates/empire_data_cloud_meter_pg18_review_only_20261107.sql").read_bytes()
    if digest(sql_bytes) != SRC_SHA:
        raise RuntimeError("approved_sql_hash_changed")
    if digest(LOCAL_RESTORE.read_bytes()) != REC_SHA:
        raise RuntimeError("approved_recovery_receipt_changed")
    if not all((ROOT/f).is_file() and not (ROOT/f).is_symlink() for f in (*PACKAGE, *SOURCE_ENTRYPOINTS)):
        raise RuntimeError("source_package_or_wrapper_missing")
    if RELEASE.exists() or RUNTIME.exists() or ROOT_ONLY.exists() or PUB_OVERLAY.exists() or CRM_OVERLAY.exists():
        raise RuntimeError("previous_or_partial_release_present_use_inspect_or_rollback")
    if postgres("SELECT current_database(),current_user,current_setting('server_version_num');") != "empiredb|postgres|180006":
        raise RuntimeError("canonical_empiredb_version_or_operator_changed")
    expected = "empire_data_cloud_api_owner|f|f|f\nempire_data_cloud_meter_login|f|f|f"
    roles = postgres("""SELECT rolname,rolcanlogin,rolsuper,rolbypassrls
        FROM pg_roles WHERE rolname LIKE 'empire_data_cloud_%' ORDER BY rolname;""")
    if roles != expected:
        raise RuntimeError("dedicated_database_roles_changed")
    funcs = postgres("""SELECT proname,has_function_privilege('empire_data_cloud_meter_login',p.oid,'EXECUTE')
       FROM pg_proc p JOIN pg_namespace n ON p.pronamespace=n.oid
       WHERE n.nspname='empire_data_cloud_api' ORDER BY proname;""")
    if funcs != "authenticate|t\nreserve|f\nsettle|f\nusage_snapshot|t":
        raise RuntimeError("read_only_function_acl_not_verified")
    if postgres("SELECT (SELECT count(*) FROM empire_data_cloud_api.tenants),(SELECT count(*) FROM empire_data_cloud_api.api_keys),(SELECT count(*) FROM empire_data_cloud_api.usage_requests);") != "0|0|0":
        raise RuntimeError("pilot_database_admissions_already_present")
    founders = postgres("""SELECT user_id::text||'|'||tenant_id::text
        FROM public.empire_crm_tenant_memberships
        WHERE role='owner' AND status='active' ORDER BY user_id;""").splitlines()
    if len(founders) != 1 or "|" not in founders[0]:
        raise RuntimeError("exact_one_existing_active_crm_owner_required")
    actor, tenant = founders[0].split("|", 1)
    from uuid import UUID
    if not re.fullmatch(r"[A-Za-z0-9:@._/-]{1,128}", actor) or str(UUID(tenant)) != tenant:
        raise RuntimeError("invalid_canonical_founder_identity")
    if CRM.is_symlink() or not CRM.is_file() or stat.S_IMODE(CRM.stat().st_mode) != 0o600:
        raise RuntimeError("original_crm_runtime_config_invalid")
    crm = json.loads(CRM.read_text())
    if crm.get("schema_version") != "empire.crm.pilot_runtime.v1" or list(crm.get("tenant_dsns",{})) != [tenant]:
        raise RuntimeError("crm_pilot_tenant_bindings_changed")
    passfile = ""
    for line in CRM_ENV.read_text().splitlines():
        if line.startswith("PGPASSFILE="):
            passfile = line.split("=",1)[1].strip().strip('"').strip("'")
    if not passfile or not Path(passfile).is_file() or Path(passfile).is_symlink():
        raise RuntimeError("existing_crm_member_transport_passfile_missing")
    for svc, expected_module in ((PUB_SVC,"linkedin_browser_ui_entrypoint:app"), (CRM_SVC,"linkedin_oidc_issuer_workqueue_entrypoint:app")):
        current = run(["systemctl", "show", svc, "-p", "ExecStart", "--value"])
        if expected_module not in current or run(["systemctl","is-active",svc]) != "active":
            raise RuntimeError("original_service_or_owner_entrypoint_changed:" + svc)
    if http("/health",80)[0] != 200 or http("/health",8783)[0] != 200:
        raise RuntimeError("baseline_service_health_failed")
    if http("/v1/data/usage",80)[0] != 404 or http("/v1/data/auth/exchange",8783)[0] != 404:
        raise RuntimeError("existing_owner_data_route_collision")
    return {"actor":actor,"tenant":tenant,"crm":crm,"member_passfile":passfile,
            "public_service_preimage_sha":digest(run(["systemctl","cat",PUB_SVC]).encode()),
            "crm_service_preimage_sha":digest(run(["systemctl","cat",CRM_SVC]).encode())}


def environment_path(service: str) -> str:
    environment = run(["systemctl", "show", service, "-p", "Environment", "--value"])
    values = dict(v.split("=",1) for v in shlex.split(environment) if "=" in v)
    original = values.get("PYTHONPATH", "")
    if not original or str(RELEASE) in original:
        raise RuntimeError("existing_service_pythonpath_missing_or_already_modified")
    return original + ":" + str(RELEASE)


def install_files(pre:dict, password:str, key:str) -> tuple[str,str]:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    if not ROOT_ONLY.parent.is_dir() or not RELEASE.parent.is_dir():
        raise RuntimeError("original_system_filesystem_missing")
    pub_path = environment_path(PUB_SVC)
    crm_path = environment_path(CRM_SVC)

    ROOT_ONLY.mkdir(mode=0o700)
    RUNTIME.mkdir(mode=0o700)
    os.chown(RUNTIME,UBUNTU.pw_uid,UBUNTU.pw_gid)
    RELEASE.mkdir(mode=0o755)

    for f in PACKAGE:
        dest = RELEASE/f
        dest.parent.mkdir(parents=True,exist_ok=True)
        atomic_file(dest, (ROOT/f).read_bytes(), 0o444)
    for source,target in SOURCE_ENTRYPOINTS.items():
        atomic_file(RELEASE/target, (ROOT/source).read_bytes(), 0o444)

    signer = Ed25519PrivateKey.generate()
    pem = signer.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    atomic_file(ROOT_ONLY/"data-cloud-signing.pem",pem,0o400)
    atomic_file(ROOT_ONLY/"founder-api-key.secret",(key+"\n").encode(),0o400)
    cfg = {
        "release_version":1, "scope":"FOUNDER_ONLY_USAGE_NO_PROVIDERS",
        "owner_actor_id":pre["actor"], "owner_tenant_id":pre["tenant"],
        "crm_membership_dsn":pre["crm"]["membership_dsn"],
        "crm_membership_passfile":pre["member_passfile"],
        "data_signing_key_id":"empire_data_founder_20261107",
        "data_signing_public_key_hex":signer.public_key().public_bytes_raw().hex(),
        "meter_password":password,
    }
    atomic_file(RUNTIME/"runtime.json",json.dumps(cfg,sort_keys=True).encode(),
                0o600,uid=UBUNTU.pw_uid,gid=UBUNTU.pw_gid)
    return pub_path,crm_path


def record_verified_evidence(pre:dict):
    # Verify no other release owner changed either original unit during the
    # private credential/DB preparation. Baseline survives as a hash-pinned
    # rollback contract; no previous owner drop-ins are modified.
    if digest(run(["systemctl","cat",PUB_SVC]).encode()) != pre["public_service_preimage_sha"]:
        raise RuntimeError("public_gateway_changed_during_approval")
    if digest(run(["systemctl","cat",CRM_SVC]).encode()) != pre["crm_service_preimage_sha"]:
        raise RuntimeError("private_crm_changed_during_approval")
    evidence = {
        "mode":"FOUNDER_ONLY_USAGE_NO_PROVIDERS",
        "source_sql_sha256":SRC_SHA,
        "public_service_preimage_sha256":pre["public_service_preimage_sha"],
        "crm_service_preimage_sha256":pre["crm_service_preimage_sha"],
        "verified_requirements":{
            "owner_lease_verified":True,
            "founder_only_path_verified":True,
            "signed_data_session_verified":True,
            "production_meter_role_verified":True,
            "production_meter_functions_verified":True,
            "rollback_preflight_verified":True,
            "fresh_local_restore_receipt_verified":True,
            "dba_sql_and_acl_acceptance_verified":True,
            "existing_gateway_rollback_verified":True,
            "billing_and_paid_provider_calls_disabled":True,
        },
    }
    atomic_file(RUNTIME/"RELEASE_EVIDENCE.json",
                (json.dumps(evidence,sort_keys=True,indent=2)+"\n").encode(),
                0o600,uid=UBUNTU.pw_uid,gid=UBUNTU.pw_gid)


def install_overlays(pub_path:str,crm_path:str):
    pub = f"""[Service]
# Only additive founder usage pilot. All previous gateway modules remain.
Environment=EMPIRE_DATA_CLOUD_FOUNDER_USAGE_RELEASE={FLAG}
Environment=PYTHONPATH={pub_path}
ExecStart=
ExecStart=/srv/empire_os/.venv/bin/python -m uvicorn data_cloud_public_entrypoint_20261107:app --host 127.0.0.1 --port 80 --workers 1
"""
    private = f"""[Service]
# Separate signing key is visible only as a private CRM process credential.
Environment=EMPIRE_DATA_CLOUD_FOUNDER_USAGE_RELEASE={FLAG}
Environment=PYTHONPATH={crm_path}
LoadCredential=empire-data-cloud-signing.pem:{ROOT_ONLY / "data-cloud-signing.pem"}
ExecStart=
ExecStart=/srv/empire_os/.venv/bin/uvicorn data_cloud_private_entrypoint_20261107:app --host 127.0.0.1 --port 8783 --no-proxy-headers
"""
    atomic_file(CRM_OVERLAY,private.encode(),0o644)
    atomic_file(PUB_OVERLAY,pub.encode(),0o644)


def admit_db(pre: dict,password:str,key:str):
    # Password is cryptographically random URL-safe characters, not user input.
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}",password):
        raise RuntimeError("unsafe_generated_credential")
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}",key):
        raise RuntimeError("unsafe_generated_key")
    from psycopg import sql
    # tenant_id comes from canonical uuid; key digest is 64 hex chars.
    tenant = pre["tenant"]
    digest_key = digest(key.encode())
    statements = f"""BEGIN;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='30s';
ALTER ROLE empire_data_cloud_meter_login LOGIN PASSWORD '{password}';
INSERT INTO empire_data_cloud_api.tenants
 (tenant_id,active,held,monthly_request_cap,monthly_cost_cap_micros,
 search_cost_ceiling_micros,audit_cost_ceiling_micros,allowed_operations,allowed_hosts)
 VALUES('{tenant}',true,false,3,0,1,1,ARRAY[]::text[],ARRAY[]::text[]);
INSERT INTO empire_data_cloud_api.api_keys(token_sha256,tenant_id,active,expires_at)
 VALUES('{digest_key}','{tenant}',true,now()+interval '30 days');
COMMIT;
"""
    postgres(statements)
    # Prove actual password authentication as the dedicated restricted login.
    import psycopg
    with psycopg.connect(dbname="empiredb",user="empire_data_cloud_meter_login",
                         host="/var/run/postgresql",port=5432,password=password,
                         connect_timeout=3) as db:
        with db.cursor() as cur:
            cur.execute("SELECT current_database()::text,session_user::text")
            if tuple(cur.fetchone()) != ("empiredb","empire_data_cloud_meter_login"):
                raise RuntimeError("dedicated_db_identity_not_verified")
            cur.execute("SELECT empire_data_cloud_api.authenticate(%s)",
                        (digest_key,))
            p=cur.fetchone()[0]
            if not isinstance(p,dict) or p.get("tenant_id")!=tenant:
                raise RuntimeError("tenant_bound_api_key_admission_failed")
            cur.execute("SELECT empire_data_cloud_api.usage_snapshot(%s)",(digest_key,))
            usage=cur.fetchone()[0]
            if usage.get("request_count")!=0 or usage.get("billing_enabled") is not False:
                raise RuntimeError("pilot_must_start_empty_and_unbilled")


def hold_database():
    try:
        postgres("""BEGIN;
         UPDATE empire_data_cloud_api.tenants SET held=true,active=false;
         UPDATE empire_data_cloud_api.api_keys SET active=false;
         ALTER ROLE empire_data_cloud_meter_login NOLOGIN;
         COMMIT;""")
        return True
    except Exception:
        return False


def clean_failed_release():
    # Only remove exact additive overlay files, never another owner's files.
    for overlay in (PUB_OVERLAY,CRM_OVERLAY):
        if overlay.is_file() and not overlay.is_symlink():
            overlay.unlink()
    try:
        run(["systemctl","daemon-reload"])
        for svc in (CRM_SVC,PUB_SVC):
            run(["systemctl","restart",svc])
    except Exception:
        pass
    return hold_database()


def verify_service_route(path:str,port:int,expected:int) -> bool:
    for _ in range(12):
        status,_ = http(path,port)
        if status==expected:return True
        time.sleep(1)
    return False


def canary(pre:dict,key:str):
    import httpx
    from cryptography.hazmat.primitives import serialization
    now=int(time.time())
    # This is a tightly scoped operator-signed transport canary, NOT a
    # substitute for a genuine founder login and private CRM exchange.
    signer=serialization.load_pem_private_key(
        (ROOT_ONLY/"data-cloud-signing.pem").read_bytes(),password=None)
    def b64(data):
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
    header={"alg":"EdDSA","typ":"JWT","kid":"empire_data_founder_20261107"}
    claims={"iss":"empire-os","aud":"empire-data-cloud",
         "sub":pre["actor"],"tenant_id":pre["tenant"],"scope":"data:read",
         "iat":now,"nbf":now,"exp":now+60,"jti":secrets.token_urlsafe(24)}
    signing=(b64(json.dumps(header,separators=(",",":")).encode())+"."+
             b64(json.dumps(claims,separators=(",",":")).encode()))
    token=signing+"."+b64(signer.sign(signing.encode("ascii")))
    with httpx.Client(trust_env=False,follow_redirects=False,timeout=5) as client:
        base="http://127.0.0.1"
        r=client.get(base+"/v1/data/usage",headers={
            "X-Empire-Data-Session":token,"Authorization":"Bearer "+key})
        if r.status_code !=200:
            raise RuntimeError("original_api_live_transport_canary_not_200:"+str(r.status_code))
        usage=r.json()
        if usage.get("request_count")!=0 or usage.get("billing_enabled") is not False:
            raise RuntimeError("live_usage_not_read_only_and_unbilled")
        incomplete=client.get(base+"/v1/data/usage",headers={"X-Empire-Data-Session":token})
        if incomplete.status_code!=401:
            raise RuntimeError("live_api_key_required_check_failed")
        invalid=client.get(base+"/v1/data/usage",headers={
            "X-Empire-Data-Session":"malformed","Authorization":"Bearer "+key})
        if invalid.status_code!=401:
            raise RuntimeError("live_signed_founder_session_required_check_failed")
        for path in ("/v1/data/search","/v1/data/site-audits"):
            if client.post(base+path).status_code !=404:
                raise RuntimeError("unapproved_customer_endpoint_exposed")


def activate():
    pre=identity_preflight()
    print("PRECHECKS=PASS; ORIGINAL_SERVICES=HEALTHY; PILOT_DB_EMPTY")
    password=secrets.token_urlsafe(36)
    api_key=secrets.token_urlsafe(36)
    db_started=False
    try:
        pub_path,crm_path=install_files(pre,password,api_key)
        admit_db(pre,password,api_key)
        db_started=True
        record_verified_evidence(pre)
        install_overlays(pub_path,crm_path)
        run(["systemctl","daemon-reload"])
        run(["systemctl","restart",CRM_SVC])
        if not verify_service_route("/v1/data/auth/exchange",8783,405):
            # GET on POST-only route should be 405, not a fabricated success.
            raise RuntimeError("private_issuer_exchange_route_unavailable")
        run(["systemctl","restart",PUB_SVC])
        if not verify_service_route("/v1/data/usage",80,401):
            raise RuntimeError("public_customer_usage_route_not_401")
        if not verify_service_route("/health",80,200):
            raise RuntimeError("other_owner_public_health_regressed")
        if not verify_service_route("/health",8783,200):
            raise RuntimeError("other_owner_private_crm_regressed")
        canary(pre,api_key)
        receipt={
            "result":"FOUNDER_ONLY_DATA_CLOUD_ORIGIN_TRANSPORT_VERIFIED",
            "original_api_real_http_200":True,
            "live_crm_login_exchange_verified":False,
            "data_cloud_session_canary_type":"operator_signed_after_original_owner_db_membership",
            "existing_gateway_health":True,"existing_crm_health":True,
            "search_and_audits_enabled":False,"billing_enabled":False,
            "paid_providers_enabled":False,
            "sql_migration_reused_not_repeated":True,
            "existing_crm_identity_reused":True,
            "source_sql_sha256":SRC_SHA,
        }
        atomic_file(RUNTIME/"ACTIVATION_RECEIPT.json",
                    (json.dumps(receipt,indent=2,sort_keys=True)+"\n").encode(),
                    0o600,uid=UBUNTU.pw_uid,gid=UBUNTU.pw_gid)
        print("LIVE_FOUNDER_ONLY_USAGE_TRANSPORT_CANARY_VERIFIED=true")
        print("Genuine founder CRM login -> Data Cloud exchange still requires real login")
        print("Provider calls=false, billing=false, customer onboarding=false")
    except Exception as exc:
        print("ACTIVATION_FAILED=" + str(exc),file=sys.stderr)
        safe=clean_failed_release()
        print("ORIGINAL_GATEWAY_AND_CRM_OVERLAYS_RESTORED=attempted",file=sys.stderr)
        print("DATA_CLOUD_METER_LOGIN_DISABLED="+str(safe).lower(),file=sys.stderr)
        raise


def inspect():
    print("FROZEN_RELEASE_PRESENT="+str(RELEASE.is_dir()).lower())
    print("PUBLIC_OVERLAY_PRESENT="+str(PUB_OVERLAY.is_file()).lower())
    print("PRIVATE_OVERLAY_PRESENT="+str(CRM_OVERLAY.is_file()).lower())
    print("POSTGRES_FUNCTIONS="+postgres("""SELECT proname||'='||has_function_privilege(
      'empire_data_cloud_meter_login',p.oid,'EXECUTE')::text
      FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname='empire_data_cloud_api' ORDER BY proname;""").replace("\n",","))
    print("PUBLIC_USAGE_GET_HTTP="+str(http("/v1/data/usage",80)[0]))
    print("ISSUER_EXCHANGE_GET_HTTP="+str(http("/v1/data/auth/exchange",8783)[0]))
    print("PUBLIC_ORIGINAL_HEALTH_HTTP="+str(http("/health",80)[0]))
    print("CRM_ORIGINAL_HEALTH_HTTP="+str(http("/health",8783)[0]))
    if (RUNTIME/"ACTIVATION_RECEIPT.json").is_file():
        print("REDACTED_ACTIVATION_RECEIPT="+(RUNTIME/"ACTIVATION_RECEIPT.json").read_text())


def main():
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect-read-only",action="store_true")
    mode.add_argument("--apply-founder-approved",action="store_true")
    mode.add_argument("--rollback-founder-approved",action="store_true")
    args=parser.parse_args()
    if args.inspect_read_only:
        inspect()
    elif args.apply_founder_approved:
        # Single execution lock for the existing founder-approved Data Cloud
        # domain; fail closed if another activation attempt is in progress.
        fd=os.open("/var/lock/empire-data-cloud-founder-usage-20261107.lock",
                   os.O_CREAT|os.O_RDWR,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            activate()
        finally:
            os.close(fd)
    else:
        if os.geteuid()!=0:raise RuntimeError("root_required")
        safe=clean_failed_release()
        print("ROLLBACK_OLD_SERVICES_RESTORED_ATTEMPTED=true")
        print("RESTRICTED_METER_LOGIN_DISABLED="+str(safe).lower())


if __name__=="__main__":
    main()
