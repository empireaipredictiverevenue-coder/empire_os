"""Isolated PG18 hardened meter acceptance, NO production DB access."""
from __future__ import annotations
import hashlib, secrets, os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import psycopg

ROOT=Path(os.environ.get("EMPIRE_CLOUD_ISOLATED_PG_ROOT", "/home/ubuntu/empire_releases/data_cloud_pg18_isolated_acceptance_20261107"))
def connect():
    return psycopg.connect(dbname="empiredb",user="postgres",host=str(ROOT),port=int(os.environ.get("EMPIRE_CLOUD_ISOLATED_PG_PORT", "55439")))
def h(value):
    return hashlib.sha256(value.encode()).hexdigest()
def value(name, token, cap=4):
    with connect() as db:
        db.execute("""INSERT INTO empire_data_cloud_api.tenants
        (tenant_id,active,held,monthly_request_cap,monthly_cost_cap_micros,
        search_cost_ceiling_micros,audit_cost_ceiling_micros,allowed_operations,allowed_hosts)
        VALUES (%s,true,false,%s,2000,500,500,ARRAY['site_audit'],ARRAY['empire-ai.co.uk'])""",(name,cap))
        db.execute("""INSERT INTO empire_data_cloud_api.api_keys(token_sha256,tenant_id,active,expires_at)
        VALUES (%s,%s,true,now()+interval '1 hour')""",(h(token),name))
def request(sql,params=(),*,as_runtime=True):
    with connect() as db:
        if as_runtime:
            db.execute("SET ROLE empire_data_cloud_meter_login")
            assert db.execute("SELECT current_user::text").fetchone()[0] in (b"empire_data_cloud_meter_login","empire_data_cloud_meter_login")
        return db.execute(sql,params).fetchone()[0]
def rejected(sql,params,code,*,as_runtime=True):
    try:request(sql,params,as_runtime=as_runtime)
    except psycopg.Error as ex:
        assert ex.sqlstate==code,(ex.sqlstate,code)
        return
    raise AssertionError("expected SQL error "+code)
def reserve(token,k,host="empire-ai.co.uk"):
    return request("select empire_data_cloud_api.reserve(%s,%s,%s,%s,%s)",(h(token),"site_audit",k,h("audit-owned-site"),host),as_runtime=False)
def settle(token,id,actual=None,ref=None):
    return request("select empire_data_cloud_api.settle(%s,%s,%s,%s,%s)",(h(token),id,"completed",actual,ref),as_runtime=False)
def inspect():
    with connect() as db:
        db.execute("SELECT current_setting('data_directory')::text,inet_server_addr(),current_database()::text")
        datadir,addr,name=db.fetchone() if False else db.execute("SELECT current_setting('data_directory')::text,inet_server_addr(),current_database()::text").fetchone()
        if isinstance(datadir,bytes):datadir=datadir.decode()
        if isinstance(name,bytes):name=name.decode()
        assert Path(datadir).resolve()==ROOT.resolve() and addr is None and name=="empiredb"
        rows=db.execute("""SELECT p.proname,p.prosecdef, pg_get_userbyid(p.proowner),p.proconfig
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='empire_data_cloud_api' ORDER BY p.proname""").fetchall()
        assert len(rows)==4
        for nm,sdef,owner,conf in rows:
            if isinstance(owner,bytes):owner=owner.decode()
            assert sdef and owner=="empire_data_cloud_api_owner",rows
            assert any(b"search_path" in x if isinstance(x,bytes) else "search_path" in x for x in conf)
        for role,login,superuser,bypass in db.execute("""SELECT rolname,rolcanlogin,rolsuper,rolbypassrls
          FROM pg_roles WHERE rolname IN('empire_data_cloud_api_owner','empire_data_cloud_meter_login')"""):
            assert login is False and superuser is False and bypass is False,(role,login,superuser,bypass)
        # The usage-only runtime role must not execute write-capable functions.
        for function,granted in (
            ('authenticate(text)',True),('usage_snapshot(text)',True),
            ('reserve(text,text,text,text,text)',False),
            ('settle(text,bigint,text,bigint,text)',False),
        ):
            actual=db.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')",
                ("empire_data_cloud_meter_login","empire_data_cloud_api."+function)).fetchone()[0]
            assert actual is granted,(function,actual,granted)
def run():
    inspect()
    rejected("SELECT count(*) FROM empire_data_cloud_api.tenants",(),"42501")
    rejected("SELECT count(*) FROM empire_data_cloud_api.api_keys",(),"42501")
    # role cannot create arbitrary schema or gain table visibility via set role.
    key=secrets.token_urlsafe(32)
    name="founder_isolated_"+secrets.token_hex(4)
    value(name,key,4)
    assert request("SELECT empire_data_cloud_api.authenticate(%s)",(h(key),))["tenant_id"]==name
    rejected("SELECT empire_data_cloud_api.reserve(%s,%s,%s,%s,%s)",
             (h(key),"site_audit","role-denied-0001",h("audit-owned-site"),"empire-ai.co.uk"),"42501")
    rejected("SELECT empire_data_cloud_api.settle(%s,%s,%s,%s,%s)",
             (h(key),1,"completed",0,"test-role-denied"),"42501")
    # Full write-capable function semantics are covered under isolated DBA
    # control, never granted to the founder-only production runtime role.
    # The site domain must be explicit and allowlisted.
    rejected("SELECT empire_data_cloud_api.reserve(%s,%s,%s,%s,%s)",
             (h(key),"site_audit","missing-host-1",h("audit-owned-site"),None),"42501",as_runtime=False)
    rejected("SELECT empire_data_cloud_api.reserve(%s,%s,%s,%s,%s)",
             (h(key),"site_audit","wrong-host-1",h("audit-owned-site"),"internal.local"),"42501",as_runtime=False)
    first=reserve(key,"with-evidence-0001")
    out=settle(key,first,0,"synthetic-zero-cost-verification")
    assert out in (b"completed","completed"),out
    rejected("SELECT empire_data_cloud_api.reserve(%s,%s,%s,%s,%s)",
             (h(key),"site_audit","with-evidence-0001",h("audit-owned-site"),"empire-ai.co.uk"),"23505",as_runtime=False)
    def try_res(i):
        try:return ("admitted",reserve(key,f"concurrent-hard-{i:04d}"))
        except psycopg.Error as ex:return ("held",ex.sqlstate)
    with ThreadPoolExecutor(max_workers=16) as pool:
        outcomes=list(pool.map(try_res,range(20)))
    admissions=[x for k,x in outcomes if k=="admitted"]
    rejects=[x for k,x in outcomes if k=="held"]
    assert len(admissions)==3 and len(rejects)==17 and set(rejects)=={"P0001"},outcomes
    # Absent evidence forces irreversible cost hold (not a fake completed record).
    for reservation in admissions[:-1]:
        assert settle(key,reservation,0,"synthetic-zero-cost-verification") in (b"completed","completed")
    last=admissions[-1]
    assert settle(key,last) in (b"cost_integrity_hold","cost_integrity_hold")
    rejected("select empire_data_cloud_api.authenticate(%s)",(h(key),),"28000")
    snapshot=request("SELECT empire_data_cloud_api.usage_snapshot(%s)",(h(key),))
    assert snapshot["request_count"]==4 and snapshot["tenant_cost_hold"] is True
    assert snapshot["billing_enabled"] is False and snapshot["verified_actual_cost_usd_micros"] is None
    print("ISOLATED_PG18_HARDENED_LEDGER_PASS=true")
    print("SECURITY_DEFINER_NONLOGIN_OWNER=true,NOLOGIN_METER_ROLE=true,NO_BASE_TABLE_SELECT=true")
    print("USAGE_ROLE_READ_FUNCTIONS_ONLY=true,WRITER_FUNCTION_EXECUTE_DENIED=true")
    print("OWNED_HOST_ALLOWLIST=true,DEDUPLICATION=true,CONCURRENT_LIMIT_ADMITTED=3,REJECTED=17")
    print("COST_WITHOUT_EVIDENCE_HELD=true,ACTUAL_COST_INDEPENDENTLY_VERIFIED=false")
    print("PRODUCTION_CONNECTIONS=0,PRODUCTION_WRITES=0")
if __name__=="__main__":run()
