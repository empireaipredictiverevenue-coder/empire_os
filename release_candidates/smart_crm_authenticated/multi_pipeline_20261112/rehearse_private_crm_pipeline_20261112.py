"""Read-only rehearsal of the COMPLETE existing private CRM startup chain.

Obtain the running unit's environment without logging values or writing them
to disk. Execute as the original ubuntu service user, audit-block any side
effects, and verify old and new FastAPI routes with the internal test client.
"""
import json,os,pwd,subprocess,sys
from pathlib import Path

ROOT=Path("/srv/empire_os/release_candidates/smart_crm_authenticated/multi_pipeline_20261112")
OLDER=Path("/opt/empire-ai/crm-search-additive-20261109")
CODE=r"""
import os,sys,json
sys.path.insert(0,sys.argv[1])
sys.path.insert(0,sys.argv[2])
def audit(event,args):
    if event=='open':
        mode=args[1] if len(args)>1 else None
        flags=args[2] if len(args)>2 else None
        if (isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            raise RuntimeError('rehearsal_write_blocked')
    if event in ('socket.connect','socket.bind','subprocess.Popen','os.system','os.mkdir','os.remove','os.rename','os.rmdir','os.chmod','os.chown'):
        raise RuntimeError('rehearsal_side_effect_blocked')
sys.addaudithook(audit)
try:
    from crm_search_additive_20261109.entrypoint import app as existing
    from fastapi.testclient import TestClient
    before=TestClient(existing)
    assert before.get('/v1/revenue-crm/pipelines/board').status_code==404
    assert before.get('/v1/revenue-crm/pipelines/view').status_code==404
    route_count_before=len(existing.router.routes)
    import empire_crm_multi_pipeline_20261112.entrypoint as patched
    assert existing is patched.app
    assert len(patched.app.router.routes)==route_count_before+1
    client=TestClient(patched.app)
    assert client.get('/health').status_code==200
    assert client.get('/v1/revenue-crm/prospects?limit=1').status_code==401
    assert client.get('/v1/revenue-crm/pipelines/board?limit=1').status_code==401
    assert client.get('/v1/revenue-crm/pipelines/board',headers={'X-Tenant-ID':'708efd4b-53b2-43d7-961d-1cecab67f17a'}).status_code==401
    view=client.get('/v1/revenue-crm/pipelines/view')
    assert view.status_code==200 and 'Commercial Pipeline Control' in view.text
    assert 'default-src \'none\'' in view.headers['content-security-policy']
    assert view.headers['cache-control']=='no-store'
    assert 'Demo Roofing' not in view.text
    script=client.get('/v1/revenue-crm/pipelines/board.js')
    assert script.status_code==200 and 'sessionBearer' in script.text
    assert script.headers['cache-control']=='no-store'
    assert client.get('/v1/revenue-crm/journeys/designer').status_code==401
    search='/v1/revenue-crm/prospects/00000000-0000-0000-0000-000000000000/search-growth?site_id=00000000-0000-0000-0000-000000000000&query=release-check&engine=release-check'
    assert client.get(search).status_code==401
    print(json.dumps({'status':'FULL_CHAIN_PRIVATE_CRM_REHEARSAL_PASS',
       'prior_router_wrappers':route_count_before,'new_router_wrappers':1,'new_get_routes':3,
       'login_data_routes_unsigned':401,'static_login_shell':200,
       'private_db_used':False,'production_writes':False},sort_keys=True))
except Exception as e:
    print('PRIVATE_CRM_REHEARSAL_FAILED:'+type(e).__name__,flush=True)
    raise
"""

def prop(name):
    return subprocess.check_output(["systemctl","show","empire-revenue-crm-pilot.service",
                         "-p",name,"--value"],text=True,timeout=12).strip()

def rehearse(path=ROOT):
    if os.geteuid()!=0:raise RuntimeError("root_required_to_scope_credential_env")
    pid=prop("MainPID")
    if not pid.isdigit() or int(pid)<1:raise RuntimeError("CRM_not_running")
    original=(Path("/proc")/pid/"environ").read_bytes()
    env=dict(part.split("=",1) for part in original.decode().split("\0") if "=" in part)
    env["PYTHONDONTWRITEBYTECODE"]="1"
    env["PYTHONPATH"]=str(path)+":"+str(OLDER)+":"+env.get("PYTHONPATH","")
    identity=pwd.getpwnam(prop("User"))
    kwargs={"user":identity.pw_uid,"group":identity.pw_gid,
            "extra_groups":os.getgrouplist(identity.pw_name,identity.pw_gid)}
    command=["/srv/empire_os/.venv/bin/python","-B","-c",CODE,str(path),str(OLDER)]
    result=subprocess.run(command,env=env,cwd=prop("WorkingDirectory"),
        text=True,capture_output=True,timeout=45,**kwargs)
    if result.returncode!=0:
        print("REHEARSAL_FAILURE_CATEGORY",result.stderr.splitlines()[-1][:180] if result.stderr else "unknown")
        raise RuntimeError("full_chain_rehearsal_failed")
    assert "FULL_CHAIN_PRIVATE_CRM_REHEARSAL_PASS" in result.stdout
    print(result.stdout.strip())

if __name__=="__main__":
    rehearse(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT)
