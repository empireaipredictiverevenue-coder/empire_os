"""Actual NVIDIA authenticated NLP->executed SQL six-case acceptance.

Runs only after backend activation; preserves an immutable private receipt,
checks six synthetic SQL counts and cancels unfinished conversations. Correct
generated prose, SQL without executed result, and timeouts never count.
"""
from __future__ import annotations
import ast,json,os,re,sqlite3,time,uuid
from pathlib import Path
import httpx
from empire_os.nvidia_ontology_shadow import TABLE_DESCRIPTIONS

ROOT=Path("/srv/empire_os/runtime/nvidia_ontology_eval")
SOURCE=ROOT/"empire_graph.sqlite"
OUT=ROOT/"nvidia_hosted_nlp_six_case_receipt_20261117_v2.json"
BASE="http://localhost:33000"
CASES={
 "buyer_demand_edge_count":(
  "Using the synthetic empire_graph database, count ontology_edges where relation is BUYER_DEMANDS_LANE. Execute SQL and report the database count, not a guess.",
  "SELECT COUNT(*) FROM ontology_edges WHERE relation='BUYER_DEMANDS_LANE'",
  ["ontology_edges","BUYER_DEMANDS_LANE"]),
 "capacity_edge_count":(
  "Count ontology_edges relationships where relation is BUYER_HAS_CAPACITY_FOR_LANE in the synthetic database. Run SQL and give the actual count.",
  "SELECT COUNT(*) FROM ontology_edges WHERE relation='BUYER_HAS_CAPACITY_FOR_LANE'",
  ["ontology_edges","BUYER_HAS_CAPACITY_FOR_LANE"]),
 "unknown_demand_null":(
  "Among ontology_edges with relation BUYER_DEMANDS_LANE, how many rows have demand_units NULL? Run SQL. Unknown is not zero.",
  "SELECT COUNT(*) FROM ontology_edges WHERE relation='BUYER_DEMANDS_LANE' AND demand_units IS NULL",
  ["ontology_edges","BUYER_DEMANDS_LANE","demand_units","NULL"]),
 "known_demand_zero":(
  "Count synthetic ontology_edges with relation BUYER_DEMANDS_LANE and demand_units exactly zero, excluding NULL. Execute SQL.",
  "SELECT COUNT(*) FROM ontology_edges WHERE relation='BUYER_DEMANDS_LANE' AND demand_units = 0",
  ["ontology_edges","BUYER_DEMANDS_LANE","demand_units"]),
 "product_market_join":(
  "Using synthetic ontology_edges, how many BUYER_DEMANDS_LANE relationships share target_node_id with a PRODUCT_DEFINES_LANE edge and a MARKET_DEFINES_LANE edge? Execute joins and count matching demand edges.",
  "SELECT COUNT(*) FROM ontology_edges d JOIN ontology_edges p ON p.target_node_id=d.target_node_id AND p.relation='PRODUCT_DEFINES_LANE' JOIN ontology_edges m ON m.target_node_id=d.target_node_id AND m.relation='MARKET_DEFINES_LANE' WHERE d.relation='BUYER_DEMANDS_LANE'",
  ["ontology_edges","BUYER_DEMANDS_LANE","PRODUCT_DEFINES_LANE","MARKET_DEFINES_LANE"]),
 "positive_matching_capacity":(
  "For synthetic ontology_edges buyer demand relationships BUYER_DEMANDS_LANE, count those with matching source_node_id and target_node_id in BUYER_HAS_CAPACITY_FOR_LANE edges where capacity_remaining > 0. Execute the SQL join.",
  "SELECT COUNT(*) FROM ontology_edges d JOIN ontology_edges c ON d.source_node_id=c.source_node_id AND d.target_node_id=c.target_node_id AND c.relation='BUYER_HAS_CAPACITY_FOR_LANE' WHERE d.relation='BUYER_DEMANDS_LANE' AND c.capacity_remaining>0",
  ["ontology_edges","BUYER_DEMANDS_LANE","BUYER_HAS_CAPACITY_FOR_LANE","capacity_remaining"]),
}

def parse_count(payload):
    if isinstance(payload,int) and not isinstance(payload,bool):
        return payload
    if isinstance(payload,(list,tuple)):
        # A COUNT query must return one aggregate row, not a series whose
        # first number happens to match the expected answer.
        return parse_count(payload[0]) if len(payload)==1 else None
    if isinstance(payload,dict):
        if len(payload)!=1:
            return None
        for k,v in payload.items():
            if str(k).lower() in {"value","count","n","total","count(*)","count(1)","row_count"}:
                if isinstance(v,(int,float)) and not isinstance(v,bool) and int(v)==v:return int(v)
                if isinstance(v,str) and v.isdigit():return int(v)
        # NVIDIA's executed COUNT(*) query may alias its sole result column,
        # e.g. buyer_demands_lane_count rather than "count". Accept exactly one
        # integer-like scalar in exactly one column; never guess from prose.
        if len(payload)==1:
            only=next(iter(payload.values()))
            if isinstance(only,int) and not isinstance(only,bool):
                return only
            if isinstance(only,str) and only.isdigit():
                return int(only)
        for v in payload.values():
            if isinstance(v,(list,dict)):
                n=parse_count(v)
                if n is not None:return n
    if isinstance(payload,str):
        for parser in (json.loads,ast.literal_eval):
            try:
                decoded=parser(payload)
            except (ValueError,SyntaxError,TypeError,RecursionError):
                continue
            # A textual model answer or bare JSON scalar is not a table row.
            if isinstance(decoded,(list,dict)) and decoded!=payload:
                return parse_count(decoded)
    return None

def check_one(client,name,question,expected,tokens):
    started=time.monotonic()
    cid=str(uuid.uuid4())
    events=[]
    sql=None;db=None;reply=None;error=None;http=None;cancel=None
    try:
        with client.stream(
            "POST","/api/chat/completions",
            json={"question":question,"conversation_id":cid,"target_db":"empire_graph","prediction":False},
            headers={"Content-Type":"application/json","Accept":"text/event-stream","x-auto-ontology-source":"synthetic_nlp_sql_acceptance"}
        ) as res:
            http=res.status_code
            if res.status_code!=200:
                error="HTTP_"+str(res.status_code)
            else:
                for line in res.iter_lines():
                    if time.monotonic()-started>135:
                        error="WALL_CLOCK_LIMIT";break
                    if not line.startswith("data:"):continue
                    part=line[5:].strip()
                    if part=="[DONE]":break
                    try: event=json.loads(part)
                    except ValueError:continue
                    kind=event.get("type")
                    if kind not in ("step","sql","result","error","charts"):continue
                    events.append(kind)
                    if kind=="sql":sql=event.get("sql")
                    if kind=="error":
                        error="NVIDIA_STREAM_ERROR";break
                    if kind=="result":
                        answer=event.get("answer") or {}
                        sql=answer.get("sql_code") or sql
                        db=answer.get("sql_response_from_db")
                        reply=answer.get("response")
                        break
    except (httpx.HTTPError,TimeoutError) as exc:
        error=type(exc).__name__
    if reply is None:
        try:cancel=client.post(f"/api/chat/cancel?conversation_id={cid}",timeout=7).status_code
        except httpx.HTTPError:pass
    actual=parse_count(db)
    sql_ok=(
        isinstance(sql,str) and bool(re.search(r"\bCOUNT\s*\(",sql,re.IGNORECASE))
        and all(t.lower() in sql.lower() for t in tokens)
    )
    passed=(
        http==200 and reply is not None and isinstance(sql,str)
        and db is not None and sql_ok and actual==expected
        and error is None
    )
    return {
        "name":name,"http":http,"expected":expected,"actual":actual,
        "has_executed_sql_response":db is not None,
        "sql_source_and_filter_matches":bool(sql_ok),
        "sse_result_received":reply is not None,
        "events":events[-15:],"error_kind":error,"cancel_http":cancel,
        "passed":passed,"duration_s":round(time.monotonic()-started,2),
    }

def run():
    if OUT.exists():raise RuntimeError("immutable acceptance receipt already exists")
    cfg=dict(s.split("=",1) for s in (ROOT/".env").read_text().splitlines() if "=" in s)
    if cfg.get("CONNECTION_STRINGS")!="sqlite:////reference/empire_graph.sqlite" or cfg.get("REASONING_MODEL")!="openai/nvidia/nemotron-3.5-super-vl:free":
        raise RuntimeError("isolated free-model configuration not staged")
    with sqlite3.connect(f"file:{SOURCE}?mode=ro",uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        expected={name:int(db.execute(sql).fetchone()[0]) for name,(_,sql,_) in CASES.items()}
    assert expected=={
        "buyer_demand_edge_count":2,"capacity_edge_count":1,
        "unknown_demand_null":1,"known_demand_zero":1,
        "product_market_join":2,"positive_matching_capacity":1,
    }
    output={"status":"NOT_VERIFIED","model":"openai/nvidia/nemotron-3.5-super-vl:free",
            "real_nvidia_nlp":True,"real_executed_sql_required":True,
            "synthetic_only":True,"paid_fallback":False,
            "customer_data_sent":False,"case_count":len(CASES),"results":[]}
    with httpx.Client(
        base_url=BASE,follow_redirects=False,trust_env=False,
        timeout=httpx.Timeout(connect=12,read=155,write=15,pool=12),
        headers={"Origin":BASE},
    ) as client:
        auth=client.post("/api/auth/sign-in/email",json={
            "email":cfg["AUTO_ONTOLOGY_ADMIN_EMAIL"],"password":cfg["AUTO_ONTOLOGY_ADMIN_PASSWORD"],
        })
        if auth.status_code!=200 or not client.cookies:raise RuntimeError("authenticated login failed")
        sem=client.get("/api/semantic-compilation/status")
        sem.raise_for_status()
        if sem.json().get("running") is not False:
            raise RuntimeError("semantic compiler must be inactive")
        catalog=client.get("/api/terms?limit=100")
        catalog.raise_for_status()
        observed={t["name"]:t["description"] for t in catalog.json().get("terms",[])}
        if len(observed)!=4 or any(observed.get(k.replace("_"," ").title())!=v for k,v in TABLE_DESCRIPTIONS.items()):
            raise RuntimeError("canonical source definitions not verified")
        for name,(question,_sql,tokens) in CASES.items():
            outcome=check_one(client,name,question,expected[name],tokens)
            output["results"].append(outcome)
            print(json.dumps({"case":name,"passed":outcome["passed"],"duration_s":outcome["duration_s"],"error":outcome["error_kind"]}),flush=True)
            if not outcome["passed"]:
                break
    output["passed_count"]=sum(row["passed"] for row in output["results"])
    output["status"]="VERIFIED" if output["passed_count"]==len(CASES) else "NOT_VERIFIED"
    fd=os.open(OUT,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"w") as f:json.dump(output,f,indent=2)
    print(json.dumps({"status":output["status"],"passed":output["passed_count"],"total":len(CASES),"receipt":str(OUT)}))

if __name__=="__main__":
    run()
