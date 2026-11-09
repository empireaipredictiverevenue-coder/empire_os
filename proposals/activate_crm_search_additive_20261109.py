"""Add search evidence after original startup; restore own override on failure."""
import argparse, hashlib, json, os, pwd, subprocess, time
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

SERVICE="empire-revenue-crm-pilot.service"
ORIGINAL="private_crm_original_v411_source_entrypoint_20261108:app"
MODULE="crm_search_additive_20261109.entrypoint:app"
CRM=Path("/opt/empire-ai/crm-pilot-releases/smart-crm-work-queue-20261104v1")
SOURCE=Path(__file__).resolve().parent
DEST=Path("/opt/empire-ai/crm-search-additive-20261109")
DROP=Path("/etc/systemd/system/empire-revenue-crm-pilot.service.d/zzzzzzzzzzzzz-crm-search-additive-20261109.conf")
EXPECTED={"__init__.py":"d927ea4e5a2b00150db31e82d69e9e85dce4a3aa5251f533ae61d1b3a92901c2","entrypoint.py":"26e536dc1c00f3402e92849b4e908271ee89096b14df446866dc7dfaf7a711c4","mount.py":"b57f2dd9ba35bb0994401cf8f795d83c42cdaeeca42afaf56dfb3720d70129c7","revenue_crm_search_evidence_api.py":"bb0070b32a5e0a26828181f458e35eeab0efdf2c64b63ed1e0cbb7be505f6b3a","revenue_crm_search_growth.py":"d6beff1ea4c483bf9ef4349c9c0412867d0a2f5ad51e745ab74874aef9426721"}
SEARCH="/v1/revenue-crm/prospects/00000000-0000-0000-0000-000000000000/search-growth?site_id=00000000-0000-0000-0000-000000000000&query=release-check&engine=release-check"

def require(value,message):
    if not value: raise RuntimeError(message)
def command(*args):
    return subprocess.check_output(args,text=True,timeout=45).strip()
def prop(name):
    return command("systemctl","show",SERVICE,"-p",name,"--value")
def digest(path):
    require(path.is_file() and not path.is_symlink(),"regular file required")
    return hashlib.sha256(path.read_bytes()).hexdigest()
def pins():
    for name,sha in {
        "revenue_crm_api.py":"d5ce55e7306f27c56d2ff053e3bafbd73779860a7a53789aac32d0f949c16a05",
        "revenue_crm_search_growth.py":"e2bcb699a4ee9e21fceaf94bf9417f3851b04c8e29ab18c19185789a13be9d55",
        "revenue_crm_transport.py":"ec24791ed8a8d91914085f70a2f610c21415d77582a38734257eff62be4bf3c3",
    }.items():
        require(digest(CRM/"empire_os"/name)==sha,"original CRM changed: "+name)

def database():
    sql="""BEGIN READ ONLY; SET LOCAL statement_timeout='4s';
SELECT (SELECT md5(prosrc)='06b1cd54d49364214c954fe6a91418d8'
 AND prosecdef AND provolatile='s' AND proowner='empiredb_migrator'::regrole
 AND proconfig @> ARRAY['search_path=""','row_security=on']
 FROM pg_proc WHERE oid='public.empire_crm_search_evidence(uuid,uuid,text,text,integer)'::regprocedure)
 AND (SELECT count(*)=0 FROM public.crm_search_site_bindings)
 AND has_function_privilege('empire_revenue_crm_reader',
 'public.empire_crm_search_evidence(uuid,uuid,text,text,integer)','EXECUTE')
 AND NOT EXISTS (SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) a
 WHERE c.oid='public.crm_search_site_bindings'::regclass AND a.grantee<>c.relowner)
 AND NOT EXISTS (SELECT 1 FROM pg_proc p,LATERAL aclexplode(p.proacl) a
 WHERE p.oid='public.empire_crm_search_evidence(uuid,uuid,text,text,integer)'::regprocedure
 AND a.grantee NOT IN (p.proowner,'empire_revenue_crm_reader'::regrole));
ROLLBACK;"""
    result=command("/usr/sbin/runuser","-u","postgres","--","/usr/bin/psql",
                   "-X","-Atq","-d","empiredb","-v","ON_ERROR_STOP=1","-c",sql)
    require(result=="t","database readback failed")

REHEARSAL=r"""
import os,sys,json
from pathlib import Path
root=Path(sys.argv[1])
sys.path.insert(0,str(root))
def audit(event,args):
    if event=='open':
        mode,flags=args[1],args[2]
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            raise RuntimeError('rehearsal_write_blocked')
    if event in ('socket.connect','socket.bind','subprocess.Popen','os.system','os.mkdir','os.remove','os.rename','os.rmdir','os.chmod','os.chown'):
        raise RuntimeError('rehearsal_side_effect_blocked')
sys.addaudithook(audit)
try:
    from private_crm_original_v411_source_entrypoint_20261108 import app as original_app
    from fastapi.testclient import TestClient
    original_client=TestClient(original_app)
    assert original_client.get('/health').status_code==200
    assert original_client.get('/v1/revenue-crm/prospects?limit=1').status_code==401
    assert original_client.get(sys.argv[2]).status_code==404
    import crm_search_additive_20261109.entrypoint as entry
    assert Path(entry.__file__).resolve()==root/'crm_search_additive_20261109/entrypoint.py'
    from fastapi.testclient import TestClient
    client=TestClient(entry.app)
    assert client.get('/health').status_code==200
    assert client.get('/v1/revenue-crm/prospects?limit=1').status_code==401
    assert client.get(sys.argv[2]).status_code==401
    print('FULL_CHAIN_PASS')
except Exception as exc:
    print('FULL_CHAIN_FAILED:'+type(exc).__name__)
    sys.exit(1)
"""
def rehearse(root):
    pid=prop("MainPID")
    require(pid.isdigit() and int(pid)>0,"CRM PID missing")
    # Reuse service configuration in memory; never print or save its values.
    env=dict(item.split("=",1) for item in
             (Path("/proc")/pid/"environ").read_bytes().decode().split("\0") if "=" in item)
    env["PYTHONDONTWRITEBYTECODE"]="1"
    identity=pwd.getpwnam(prop("User"))
    kwargs={}
    if os.geteuid()==0:
        kwargs={"user":identity.pw_uid,"group":identity.pw_gid,
                "extra_groups":os.getgrouplist(identity.pw_name,identity.pw_gid)}
    result=subprocess.run(["/srv/empire_os/.venv/bin/python","-B","-c",REHEARSAL,str(root),SEARCH],
          env=env,cwd=CRM,text=True,capture_output=True,timeout=40,**kwargs)
    require(result.returncode==0 and result.stdout.strip()=="FULL_CHAIN_PASS",
            "full startup rehearsal failed; live untouched")
def status(path):
    try:
        with urlopen("http://127.0.0.1:8783"+path,timeout=2) as response: return response.status
    except HTTPError as error: return error.code
    except (URLError,TimeoutError): return 0
def smoke(search_code):
    for _ in range(15):
        if prop("ActiveState")=="active" and status("/health")==200 and status("/v1/revenue-crm/prospects?limit=1")==401 and status(SEARCH)==search_code:
            return True
        time.sleep(1)
    return False
def preflight():
    require(os.geteuid()==0,"run with sudo")
    require(prop("WorkingDirectory")==str(CRM) and ORIGINAL in prop("ExecStart"),"service identity changed")
    require(prop("ActiveState")=="active","original CRM not active")
    require(not DROP.exists() and not DROP.is_symlink(),"override already exists")
    pins()
    for name,sha in EXPECTED.items():
        require(digest(SOURCE/"crm_search_additive_20261109"/name)==sha,"candidate changed")
    database()
    rehearse(SOURCE)
def restore_override():
    # The only live configuration mutation is this newly-created drop-in.
    DROP.unlink()
    command("systemctl","daemon-reload")
    require(ORIGINAL in prop("ExecStart"),"original entrypoint not restored")
    command("systemctl","reset-failed",SERVICE)
    command("systemctl","restart",SERVICE)
    require(smoke(404),"ROLLBACK_NOT_VERIFIED; inspect service")
    pins()
def apply():
    preflight()
    require(not DEST.exists() and not DEST.is_symlink(),"candidate destination already exists; inspect before retry")
    package=DEST/"crm_search_additive_20261109"
    package.mkdir(parents=True,mode=0o755)
    for name,sha in EXPECTED.items():
        target=package/name
        with target.open("xb") as stream: stream.write((SOURCE/package.name/name).read_bytes())
        os.chmod(target,0o644)
        require(digest(target)==sha,"frozen candidate mismatch")
    rehearse(DEST)
    preflight()
    text=("[Service]\nExecStart=\nExecStart=/srv/empire_os/.venv/bin/uvicorn "
          +MODULE+" --app-dir "+str(DEST)+" --host 127.0.0.1 --port 8783 --no-proxy-headers\n")
    with DROP.open("x") as stream: stream.write(text)
    os.chmod(DROP,0o644)
    try:
        command("systemctl","daemon-reload")
        require(MODULE in prop("ExecStart"),"new override not effective")
        command("systemctl","restart",SERVICE)
        require(smoke(401),"new route runtime smoke failed")
        pins()
    except Exception:
        restore_override()
        print(json.dumps({"status":"RELEASE_FAILED_ORIGINAL_RESTORED","health":200,"unsigned_crm":401,"search_route":404}))
        raise RuntimeError("release failed; original restored; do not retry") from None
    receipt={"status":"ADDITIVE_SEARCH_ROUTE_LIVE","health":200,"unsigned_crm":401,
             "unsigned_search":401,"original_files_unchanged":True,
             "database_writes":False,"signed_founder_session_verified":False}
    (DEST/"receipt.json").write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--preflight-readonly",action="store_true")
    parser.add_argument("--apply-founder-approved-with-rollback",action="store_true")
    args=parser.parse_args()
    require(args.preflight_readonly != args.apply_founder_approved_with_rollback,"choose one mode")
    if args.preflight_readonly:
        preflight()
        print('FULL_CHAIN_AND_DATABASE_PREFLIGHT_PASS')
    else: apply()
