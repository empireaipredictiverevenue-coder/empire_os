"""One bounded, authenticated NVIDIA natural-language-to-SQL acceptance probe.

Synthetic fixture ONLY. Compares executed SQL result against an independent
read-only SQLite count. Preserves a private audit record and cancels a timed-out
conversation; does not claim success from generated prose.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path

import httpx

from empire_os.nvidia_ontology_shadow import TABLE_DESCRIPTIONS

ROOT = Path("/srv/empire_os/runtime/nvidia_ontology_eval")
BASE = "http://localhost:33000"
RESULT = ROOT / "nvidia_first_nlp_sql_result_20261116.json"
SOURCE = ROOT / "empire_graph.sqlite"
QUESTION = (
    "In the synthetic empire_graph database, count ontology_edges rows "
    "where relation equals BUYER_DEMANDS_LANE. Execute SQL and report only "
    "the actual database count. Do not infer sales or buyer verification."
)

def _db_ground_truth():
    conn = sqlite3.connect(f"file:{SOURCE}?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only = ON")
        return conn.execute(
            "SELECT COUNT(*) FROM ontology_edges WHERE relation = ?",
            ("BUYER_DEMANDS_LANE",),
        ).fetchone()[0]
    finally:
        conn.close()

def _actual_count(payload):
    if isinstance(payload, list):
        for item in payload:
            count = _actual_count(item)
            if count is not None:
                return count
    if isinstance(payload, dict):
        for k,v in payload.items():
            if k.lower() in ("value","count","total","count(*)","n") and isinstance(v,(int,str)):
                try:
                    return int(v)
                except ValueError:
                    continue
    if isinstance(payload, str):
        try:
            return _actual_count(json.loads(payload))
        except (ValueError,TypeError):
            return None
    return None

def main():
    if RESULT.exists():
        raise RuntimeError("NVIDIA NLP acceptance already attempted; preserve prior audit")
    cfg = dict(s.split("=",1) for s in (ROOT/".env").read_text().splitlines() if "=" in s)
    assert cfg["CONNECTION_STRINGS"] == "sqlite:////reference/empire_graph.sqlite"
    assert cfg["REASONING_ENDPOINT"] == "http://172.18.0.1:19999/v1"
    expected = _db_ground_truth()
    assert expected == 2
    started=time.monotonic()
    conversation_id = str(uuid.uuid4())
    reply=None
    sql=None
    sql_result=None
    error=None
    events=[]
    timed_out=False
    http_status=None

    with httpx.Client(base_url=BASE,trust_env=False,follow_redirects=False,
                      timeout=httpx.Timeout(connect=10,read=35,write=10,pool=10),
                      headers={"Origin":BASE}) as client:
        login=client.post("/api/auth/sign-in/email",json={
            "email":cfg["AUTO_ONTOLOGY_ADMIN_EMAIL"],
            "password":cfg["AUTO_ONTOLOGY_ADMIN_PASSWORD"],
        })
        if login.status_code != 200 or not client.cookies:
            raise RuntimeError("NVIDIA local admin sign-in failed")
        status=client.get("/api/semantic-compilation/status")
        status.raise_for_status()
        if status.json().get("running") is not False:
            raise RuntimeError("semantic compiler still running")
        terms_resp=client.get("/api/terms?limit=50")
        terms_resp.raise_for_status()
        terms=terms_resp.json().get("terms",[])
        if len(terms)!=4:
            raise RuntimeError("semantic terms incomplete")
        terms_by_name={item["name"]:item["description"] for item in terms}
        if any(
            terms_by_name.get(table.replace("_"," ").title())!=description
            for table,description in TABLE_DESCRIPTIONS.items()
        ):
            raise RuntimeError("canonical term descriptions not verified")
        try:
            with client.stream(
                "POST","/api/chat/completions",
                json={
                    "question":QUESTION,"conversation_id":conversation_id,
                    "target_db":"empire_graph","prediction":False,
                },
                headers={
                    "Content-Type":"application/json",
                    "Accept":"text/event-stream",
                    "x-auto-ontology-source":"synthetic_acceptance",
                },
            ) as response:
                http_status=response.status_code
                if http_status != 200:
                    error=f"HTTP {http_status}"
                else:
                    for line in response.iter_lines():
                        if time.monotonic()-started > 95:
                            timed_out=True
                            break
                        if not line.startswith("data:"):
                            continue
                        raw=line[5:].strip()
                        if raw=="[DONE]":
                            break
                        try:
                            event=json.loads(raw)
                        except ValueError:
                            continue
                        kind=event.get("type")
                        if kind not in ("step","sql","result","error","charts"):
                            continue
                        events.append(kind)
                        if kind=="sql":
                            sql=event.get("sql")
                        elif kind=="result":
                            answer=event.get("answer") or {}
                            reply=answer.get("response")
                            sql=answer.get("sql_code") or sql
                            sql_result=answer.get("sql_response_from_db")
                            break
                        elif kind=="error":
                            error=str(event.get("message"))[:180]
                            break
        except (httpx.HTTPError,TimeoutError) as exc:
            error=type(exc).__name__
            timed_out=True
        if reply is None:
            try:
                cancel=client.post(f"/api/chat/cancel?conversation_id={conversation_id}",
                                   timeout=8)
                cancel_status=cancel.status_code
            except httpx.HTTPError:
                cancel_status=None
        else:
            cancel_status=None

    actual=_actual_count(sql_result)
    sql_valid=isinstance(sql,str) and bool(
        re.search(r"ontology_edges",sql,re.IGNORECASE)
    ) and "BUYER_DEMANDS_LANE" in sql.upper()
    verified=actual==expected and sql_valid and error is None
    output={
        "status":"VERIFIED" if verified else "NOT_VERIFIED",
        "source":"ACTUAL_NVIDIA_AUTHENTICATED_NLP_SSE",
        "synthetic_only":True,
        "http":http_status,
        "expected_count":expected,
        "database_count":actual,
        "sql_matches_expected_table_and_relation":bool(sql_valid),
        "result_event_seen":reply is not None,
        "events":events[-20:],
        "error_kind":error,
        "timed_out":timed_out,
        "cancel_status_if_incomplete":cancel_status,
        "elapsed_s":round(time.monotonic()-started,1),
        "model_response_excerpt":str(reply)[:200] if reply else None,
        "model_sql_excerpt":str(sql)[:300] if sql else None,
        "secrets_disclosed":False,
    }
    fd=os.open(RESULT,os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600)
    with os.fdopen(fd,"w") as f:
        json.dump(output,f,indent=2)
    print(json.dumps(output,indent=2,sort_keys=True))
if __name__=="__main__":
    main()
