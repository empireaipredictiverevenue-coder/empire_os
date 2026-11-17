"""Read-only diagnosis of NVIDIA viewer chat readiness after empty MCP answer."""
import asyncio,json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from scripts.verify_nvidia_viewer_real_mcp_tools_20261117 import load_existing_grant

async def main():
    token=load_existing_grant()
    async with streamablehttp_client(
        "http://127.0.0.1:33013/mcp",
        headers={"Authorization":"Bearer "+token},
        timeout=20,sse_read_timeout=45,
    ) as (reader,writer,_):
        async with ClientSession(reader,writer) as session:
            await session.initialize()
            r=await session.call_tool("check_readiness",{})
            d=r.structuredContent or {}
            if isinstance(d,dict) and isinstance(d.get('result'),dict):
                d=d['result']
            safe={k:d.get(k) for k in ('ready','semantic_layer_built','can_execute_sql',
                'catalog_present','databases','blockers','unverified')}
            print(json.dumps({"mcp_tool":"check_readiness","is_error":r.isError,
                "readiness":safe,"token_disclosed":False},indent=2))
asyncio.run(main())
