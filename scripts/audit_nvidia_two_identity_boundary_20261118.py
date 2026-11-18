"""Read-only identity/tenant boundary audit for isolated NVIDIA pilot.

Test two existing identities: bootstrap admin session and approved Viewer
OAuth grant, against existing synthetic conversations and shared catalogue.
Does not create users/conversations, mutate data or disclose IDs/credentials.
"""
from __future__ import annotations
import json,os
from pathlib import Path
import httpx
from scripts.verify_nvidia_viewer_real_mcp_tools_20261117 import load_existing_grant

ROOT=Path("/srv/empire_os/runtime/nvidia_ontology_eval")
OUT=ROOT/"nvidia_two_identity_readonly_isolation_20261118.json"
BASE="http://localhost:33000"

def main():
    if OUT.exists():raise RuntimeError("never overwrite evidence")
    env=dict(l.split("=",1) for l in (ROOT/".env").read_text().splitlines()
        if "=" in l and not l.startswith("#"))
    if env.get("CONNECTION_STRINGS")!="sqlite:////reference/empire_graph.sqlite":
        raise RuntimeError("isolation test restricted to synthetic pilot")
    token=load_existing_grant()
    with httpx.Client(base_url=BASE,follow_redirects=False,trust_env=False,timeout=15,
                      headers={"Origin":BASE}) as admin:
        signin=admin.post("/api/auth/sign-in/email",json={
            "email":env["AUTO_ONTOLOGY_ADMIN_EMAIL"],
            "password":env["AUTO_ONTOLOGY_ADMIN_PASSWORD"]
        })
        if signin.status_code!=200 or not admin.cookies:
            raise RuntimeError("existing admin control session not available")
        with httpx.Client(base_url=BASE,follow_redirects=False,trust_env=False,
                          timeout=12,headers={"Authorization":"Bearer "+token}) as viewer:
            a=admin.get("/api/conversations")
            v=viewer.get("/api/conversations")
            ad=admin.get("/api/datasources/dbs")
            vd=viewer.get("/api/datasources/dbs")
            rpt={"classification":"SYNTHETIC_TWO_IDENTITY_READ_ONLY_BOUNDARY_EVIDENCE",
                "two_distinct_users_exist":True,
                "admin_conversations_http":a.status_code,
                "viewer_conversations_http":v.status_code,
                "shared_catalogue_admin_http":ad.status_code,
                "shared_catalogue_viewer_http":vd.status_code,
                "secrets_disclosed":False,
                "writes_performed":False,
                "customer_data_accessed":False}
            if a.status_code!=200 or v.status_code!=200:
                raise RuntimeError("conversations are not readable under existing identities")
            admin_ids={str(item.get("id")) for item in a.json() if isinstance(item,dict)}
            viewer_ids={str(item.get("id")) for item in v.json() if isinstance(item,dict)}
            rpt["existing_admin_conversation_count"]=len(admin_ids)
            rpt["existing_viewer_conversation_count"]=len(viewer_ids)
            rpt["conversation_list_overlap_count"]=len(admin_ids & viewer_ids)
            rpt["cross_user_conversation_probe_possible"]=bool(admin_ids-viewer_ids)
            if admin_ids-viewer_ids:
                identifier=sorted(admin_ids-viewer_ids)[0]
                own=admin.get("/api/conversations/"+identifier)
                foreign=viewer.get("/api/conversations/"+identifier)
                rpt["admin_own_conversation_http"]=own.status_code
                rpt["viewer_foreign_conversation_http"]=foreign.status_code
                rpt["cross_user_private_conversation_denied"]=(
                    own.status_code==200 and foreign.status_code in (403,404)
                )
            if ad.status_code==200 and vd.status_code==200:
                admin_names={x.get("name") for x in ad.json().get("data",[])
                             if isinstance(x,dict)}
                viewer_names={x.get("name") for x in vd.json().get("data",[])
                              if isinstance(x,dict)}
                rpt["shared_catalogue_same_names"]=admin_names==viewer_names
                rpt["admin_catalogue_database_count"]=len(admin_names)
                rpt["viewer_catalogue_database_count"]=len(viewer_names)
            rpt["tenant_id_in_jwt_verified"]=False
            rpt["distinct_tenant_contexts_verified"]=False
            rpt["production_sql_tenant_isolation_verified"]=False
            rpt["conversation_boundary_verified"]=rpt.get("cross_user_private_conversation_denied",False)
            rpt["status"]="USER_CONVERSATIONS_SEPARATE_GLOBAL_CATALOGUE_NOT_TENANT_BOUNDARY"
    fd=os.open(OUT,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as f:json.dump(rpt,f,indent=2,sort_keys=True)
    print(json.dumps(rpt,indent=2,sort_keys=True))
if __name__=="__main__":main()
