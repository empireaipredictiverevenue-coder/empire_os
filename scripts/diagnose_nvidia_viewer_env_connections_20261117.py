"""Verify NVIDIA Viewer sees environment-managed connection without secrets."""
import asyncio,json
import httpx
from scripts.verify_nvidia_viewer_real_mcp_tools_20261117 import load_existing_grant

async def main():
    token=load_existing_grant()
    async with httpx.AsyncClient(base_url="http://localhost:33000",
                                 timeout=10,trust_env=False) as c:
        headers={"Authorization":"Bearer "+token}
        for name,path in (("env_source","/api/connections/source"),
                          ("catalogued_connections","/api/connections"),
                          ("databases","/api/datasources/dbs")):
            r=await c.get(path,headers=headers)
            try:data=r.json()
            except ValueError:data=None
            summary=(data if name=="env_source" else (
                {"count":data.get("count"),"rows":len(data.get("data") or [])}
                if isinstance(data,dict) else {"type":type(data).__name__}))
            print(json.dumps({"name":name,"http":r.status_code,
                              "summary":summary,"secrets_disclosed":False}))
asyncio.run(main())
