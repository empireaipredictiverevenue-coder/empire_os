"""Six genuine Viewer-authenticated NVIDIA MCP natural-language-to-SQL runs.

Use the existing OpenCode OAuth Viewer grant, existing verified free Nemotron
relay, and synthetic SQLite graph. All six are independent of admin access.
Accept only generated SQL + executed database rows matching independent SQL.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import os
import sqlite3
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from scripts.accept_nvidia_free_nlp_six_20261117 import CASES,parse_count
from scripts.verify_nvidia_viewer_real_mcp_tools_20261117 import load_existing_grant

ROOT=Path("/srv/empire_os/runtime/nvidia_ontology_eval")
OUT=ROOT/"nvidia_viewer_six_real_mcp_sql_20261118.json"
SOURCE=ROOT/"empire_graph.sqlite"
URL="http://127.0.0.1:33013/mcp"
MAX_SECONDS=160

def independently_expected(query:str)->int:
    if SOURCE.stat().st_mode & 0o022:
        raise RuntimeError("synthetic SQLite fixture writable by group/others")
    with sqlite3.connect("file:"+str(SOURCE)+"?mode=ro",uri=True) as db:
        val=db.execute(query).fetchone()
    assert isinstance(val,tuple) and len(val)==1 and isinstance(val[0],int)
    return val[0]

def normalized_answer(result):
    data=result.structuredContent or {}
    if isinstance(data,dict) and isinstance(data.get("result"),dict):
        return data["result"]
    return data if isinstance(data,dict) else {}

async def main():
    if OUT.exists():
        raise RuntimeError("immutable six-case evidence already exists")
    env=dict(l.split("=",1) for l in (ROOT/".env").read_text().splitlines()
             if "=" in l and not l.startswith("#"))
    assert env["CONNECTION_STRINGS"]=="sqlite:////reference/empire_graph.sqlite"
    assert env["REASONING_MODEL"]=="openai/nvidia/nemotron-3.5-super-vl:free"
    token=load_existing_grant()
    receipt={"scope":"EXISTING_AUTHORIZED_NVIDIA_VIEWER_NATIVE_MCP_SIX_CASE_ACCEPTANCE",
             "tool":"ask_question","sample":"synthetic_empire_graph_only",
             "data_source":"preexisting SQLite fixture, no extra ingest",
             "target_db_override_used":False,
             "oauth_grant_reused":True,"token_disclosed":False,
             "admin_not_used":True,"model_alias":"openai/nvidia/nemotron-3.5-super-vl:free",
             "total_cases":len(CASES),"passed_count":0,
             "cases":[],"all_verified":False}
    async with streamablehttp_client(
        URL,headers={"Authorization":"Bearer "+token},
        timeout=25,sse_read_timeout=MAX_SECONDS
    ) as (reader,writer,_):
        async with ClientSession(
            reader,writer,read_timeout_seconds=datetime.timedelta(seconds=MAX_SECONDS)
        ) as session:
            await session.initialize()
            for name,(question,sql_expected,tokens) in CASES.items():
                started=time.monotonic()
                expected=independently_expected(sql_expected)
                r={"name":name,"expected":expected,"actual":None,
                   "generated_sql":False,"executed_rows":False,
                   "valid_table_and_predicate":False,
                   "tool_is_error":None,"passed":False,"failure":None}
                try:
                    result=await session.call_tool("ask_question",{"question":question},
                        read_timeout_seconds=datetime.timedelta(seconds=MAX_SECONDS))
                    r["tool_is_error"]=bool(result.isError)
                    ans=normalized_answer(result)
                    sql=str(ans.get("sql") or "")
                    rows=ans.get("rows")
                    r["generated_sql"]=bool(sql.strip())
                    r["executed_rows"]=isinstance(rows,list) and len(rows)>0
                    r["valid_table_and_predicate"]=all(
                        t.lower() in sql.lower() for t in tokens)
                    r["actual"]=parse_count(rows)
                    r["row_count"]=ans.get("row_count")
                    r["passed"]=all((
                        result.isError is False,
                        r["generated_sql"],
                        r["executed_rows"],
                        r["valid_table_and_predicate"],
                        r["actual"]==expected,
                    ))
                except Exception as exc:
                    r["failure"]=type(exc).__name__
                r["elapsed_seconds"]=round(time.monotonic()-started,1)
                receipt["cases"].append(r)
                if r["passed"]:receipt["passed_count"]+=1
                print("CASE",name,
                      "PASS" if r["passed"] else "FAIL",
                      "expected",expected,"actual",r["actual"],
                      "seconds",r["elapsed_seconds"],flush=True)
    receipt["all_verified"]=receipt["passed_count"]==receipt["total_cases"]
    fd=os.open(OUT,os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as f:json.dump(receipt,f,indent=2,sort_keys=True)
    print(json.dumps({"status":"VERIFIED" if receipt["all_verified"] else "PARTIAL",
                      "passed":receipt["passed_count"],"cases":receipt["total_cases"],
                      "receipt_private":True,"token_disclosed":False,
                      "synthetic_only":True},indent=2))
    if not receipt["all_verified"]:
        raise SystemExit(2)

if __name__=="__main__":
    asyncio.run(main())
