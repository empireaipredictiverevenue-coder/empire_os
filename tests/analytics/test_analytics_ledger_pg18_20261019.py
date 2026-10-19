"""Real PostgreSQL 18 test in an isolated disposable /tmp instance.

NEVER connects to production EmpireDB, remote servers, existing sockets
or an existing configured PG* environment. Temporary trust auth is safe
only because listen_addresses is EMPTY and socket is private to tmp.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime,timezone,timedelta
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
import uuid

import psycopg
import pytest

MIGRATION = (Path(__file__).resolve().parents[2]
             /"migrations/empiredb/054_first_party_analytics_ledger_held.sql")
PG = Path("/usr/lib/postgresql/18/bin")
FIXTURE_DB = "empire_analytics_fixture"
ADMIN = "analytics_fixture_admin"
TENANT_A = "11111111-1111-4111-8111-111111111111"
TENANT_B = "22222222-2222-4222-8222-222222222222"
PROP = "empire-ai.co.uk"
POLICY = "draft-analytics-20261019"
SQL_SESSION = """
 INSERT INTO public.empire_analytics_sessions
 (tenant_id,property_key,session_digest,acquisition_channel,
  source_evidence_kind,policy_revision,opened_at,expires_at)
 VALUES (%s,%s,%s,%s,%s,%s,
         clock_timestamp()-interval '2 minutes',
         clock_timestamp()+interval '20 minutes')
"""
SQL_DECISION = """
 INSERT INTO public.empire_analytics_consent_decisions
 (tenant_id,property_key,session_digest,revision,decision,
  policy_revision,evidence_sha256,evidence_class)
 VALUES (%s,%s,%s,%s,%s,%s,%s,'SERVER_VERIFIED_CMP_DECISION')
"""
SQL_EVENT = """
 INSERT INTO public.empire_analytics_event_receipts
 (tenant_id,property_key,event_digest,session_digest,event_kind,
  page_key,occurred_at)
 VALUES (%s,%s,%s,%s,%s,%s,clock_timestamp())
"""


def run(args:list[str],*,env:dict,timeout=20,expected=True):
    result = subprocess.run(args,env=env,capture_output=True,text=True,
                            timeout=timeout)
    if expected and result.returncode:
        raise AssertionError("isolated PostgreSQL fixture command failed: "
                             + " ".join(args[:3]) + " : " + result.stderr[-900:])
    return result


@pytest.fixture(scope="module")
def db_socket():
    required = ("initdb","pg_ctl","createdb","psql")
    if not all((PG/name).is_file() for name in required):
        pytest.skip("PostgreSQL 18 server toolchain not available")
    with tempfile.TemporaryDirectory(prefix="ea54_") as temp:
        base=Path(temp)
        data=base/"data"
        sock=base/"sock"
        sock.mkdir(mode=0o700)
        log=base/"postgres.log"
        env=dict(os.environ)
        for key in list(env):
            if key.startswith("PG") or key.startswith("PSQL"):
                env.pop(key)
        env["PGSSLMODE"]="disable"
        env["PGPASSWORD"]=""
        env["PGHOST"]=str(sock)
        env["PGPORT"]="56652"
        env["PGUSER"]=ADMIN
        # This is an isolated fixture created as ubuntu in /tmp.
        run([str(PG/"initdb"),"-D",str(data),"-A","trust",
             "-U",ADMIN,"--no-instructions","--no-sync"],env=env,timeout=30)
        try:
            run([str(PG/"pg_ctl"),"-D",str(data),"-l",str(log),
                 "-o",f"-c listen_addresses='' -c unix_socket_directories={sock} -c port=56652",
                 "-w","start"],env=env,timeout=30)
            run([str(PG/"createdb"),"-h",str(sock),"-p","56652",
                 "-U",ADMIN,FIXTURE_DB],env=env)
            def script(sql,dbname=FIXTURE_DB,expected=True):
                return run([str(PG/"psql"),"-X","-q","-v","ON_ERROR_STOP=1",
                            "-d",dbname,"-c",sql],env=env,expected=expected)
            script("CREATE ROLE empiredb_migrator NOLOGIN NOSUPERUSER NOBYPASSRLS;")
            script("GRANT CREATE ON SCHEMA public TO empiredb_migrator;")
            # Must apply successfully to the explicitly allowed fixture,
            # never to default postgres or a production remote address.
            result=run([str(PG/"psql"),"-X","-q","-v","ON_ERROR_STOP=1",
                        "-d",FIXTURE_DB,"-f",str(MIGRATION)],env=env)
            assert result.returncode==0
            yield f"host={sock} port=56652 dbname={FIXTURE_DB} user={ADMIN} sslmode=disable",script
        finally:
            run([str(PG/"pg_ctl"),"-D",str(data),"-m","immediate",
                 "-w","stop"],env=env,timeout=30,expected=False)


@pytest.fixture
def conn(db_socket):
    connection=psycopg.connect(db_socket[0],autocommit=True)
    try:
        # Each test uses unique tenant/session hashes so shared DB fixture
        # does not affect expectations and no teardown writes are needed.
        yield connection
    finally:
        connection.close()


def new_session(conn,*,tenant=TENANT_A,digest=None,channel="direct",
                evidence="server_observed_direct",policy=POLICY):
    digest=digest or uuid.uuid4().hex*2
    conn.execute(SQL_SESSION,(tenant,PROP,digest,channel,evidence,policy))
    return digest


def decide(conn,digest,revision,decision,*,tenant=TENANT_A,
           evidence=None,policy=POLICY):
    conn.execute(SQL_DECISION,(tenant,PROP,digest,revision,decision,
                              policy,evidence or uuid.uuid4().hex*2))


def record(conn,digest,*,tenant=TENANT_A,event_id=None,event="page_view",
           page="home"):
    conn.execute(SQL_EVENT,(tenant,PROP,event_id or uuid.uuid4().hex*2,
                            digest,event,page))


def rejected(fn,needle=""):
    with pytest.raises(psycopg.Error) as exc:
        fn()
    if needle:
        assert needle in str(exc.value)


def test_exact_three_tables_forced_rls_no_policies_no_app_grants(conn):
    result=conn.execute("""
      SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity
      FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n
      ON n.oid=c.relnamespace WHERE n.nspname='public'
      AND c.relname LIKE 'empire_analytics_%'
      AND c.relkind='r' ORDER BY c.relname
    """).fetchall()
    assert len(result)==3
    assert all(row[1:] == (True,True) for row in result)
    policies=conn.execute("""
      SELECT count(*) FROM pg_catalog.pg_policy p
      JOIN pg_catalog.pg_class c ON p.polrelid=c.oid
      WHERE c.relname LIKE 'empire_analytics_%'
    """).fetchone()[0]
    assert policies==0
    # The new tables are not exposed to regular application logins.
    conn.execute("CREATE ROLE analytics_untrusted_fixture LOGIN NOSUPERUSER NOBYPASSRLS")
    for table in ("sessions","consent_decisions","event_receipts"):
        with psycopg.connect(conn.info.dsn.replace(
                f"user={ADMIN}","user=analytics_untrusted_fixture"),
                autocommit=True) as untrusted:
            rejected(lambda:untrusted.execute(
                "SELECT count(*) FROM public.empire_analytics_"+table),
                "permission denied")


def test_consent_must_precede_each_event(conn):
    s=new_session(conn)
    rejected(lambda:record(conn,s),"ANALYTICS054_WEBSITE_CONSENT_NOT_PROVEN")
    decide(conn,s,1,"granted")
    record(conn,s)
    decide(conn,s,2,"revoked")
    rejected(lambda:record(conn,s),"ANALYTICS054_WEBSITE_CONSENT_NOT_PROVEN")
    rejected(lambda:decide(conn,s,3,"granted"),
             "ANALYTICS054_INVALID_CONSENT_TRANSITION")


def test_denied_decision_can_precede_genuine_new_grant(conn):
    s=new_session(conn)
    decide(conn,s,1,"denied")
    rejected(lambda:record(conn,s),"ANALYTICS054_WEBSITE_CONSENT_NOT_PROVEN")
    decide(conn,s,2,"granted")
    record(conn,s)


def test_consent_revisions_sequential_and_policy_bound(conn):
    s=new_session(conn)
    rejected(lambda:decide(conn,s,2,"granted"),
             "ANALYTICS054_INVALID_CONSENT_TRANSITION")
    rejected(lambda:decide(conn,s,1,"granted",policy="other-draft"),
             "ANALYTICS054_SESSION_OR_POLICY_UNVERIFIED")
    decide(conn,s,1,"granted")
    rejected(lambda:decide(conn,s,1,"denied"),
             "ANALYTICS054_INVALID_CONSENT_TRANSITION")
    rejected(lambda:decide(conn,s,2,"granted"),
             "ANALYTICS054_INVALID_CONSENT_TRANSITION")


def test_cross_tenant_session_fk_prevents_receipt_spoof(conn):
    s=new_session(conn)
    decide(conn,s,1,"granted")
    rejected(lambda:record(conn,s,tenant=TENANT_B))


def test_event_replay_unique_across_requests_and_other_sessions(conn):
    s1=new_session(conn)
    s2=new_session(conn)
    decide(conn,s1,1,"granted")
    decide(conn,s2,1,"granted")
    nonce=uuid.uuid4().hex*2
    record(conn,s1,event_id=nonce)
    rejected(lambda:record(conn,s1,event_id=nonce),"duplicate key")
    rejected(lambda:record(conn,s2,event_id=nonce),"duplicate key")


@pytest.mark.parametrize("kind",["purchase","revenue_verified","lead","form_submit_confirmed"])
def test_browser_event_cannot_create_buyer_or_revenue_proof(conn,kind):
    s=new_session(conn)
    decide(conn,s,1,"granted")
    rejected(lambda:record(conn,s,event=kind))


@pytest.mark.parametrize("path",[
    "https://empire-ai.co.uk/?secret=foo","home/foo","/api/private",
    "john@example.com","user-123","HOME",
])
def test_pages_are_registered_keys_not_raw_urls_or_pii(conn,path):
    s=new_session(conn)
    decide(conn,s,1,"granted")
    rejected(lambda:record(conn,s,page=path))


def test_unverified_source_provenance_cannot_create_session(conn):
    rejected(lambda:new_session(conn,channel="direct",
                 evidence="signed_campaign_binding"))
    rejected(lambda:new_session(conn,channel="email",
                 evidence="server_observed_direct"))
    rejected(lambda:new_session(conn,channel="paid_search",
                 evidence="signed_campaign_binding"))


def test_cross_table_updates_and_deletes_immutable(conn):
    s=new_session(conn)
    decide(conn,s,1,"granted")
    record(conn,s)
    for table in ("sessions","consent_decisions","event_receipts"):
        rejected(lambda:conn.execute(
            "DELETE FROM public.empire_analytics_"+table+
            " WHERE session_digest=%s",(s,)),
                 "ANALYTICS054_APPEND_ONLY_MUTATION_DENIED")


def test_migration_reapply_requires_manual_owner_reconciliation(db_socket):
    _,script=db_socket
    r=script("SELECT 1 FROM public.empire_analytics_sessions LIMIT 1")
    assert r.returncode==0
    # Re-running is never silently idempotent or destructive.
    result=subprocess.run(
        [str(PG/"psql"),"-X","-q","-v","ON_ERROR_STOP=1",
         "-d",FIXTURE_DB,"-f",str(MIGRATION)],
        capture_output=True,text=True,
        env={**os.environ,"PGHOST":str(db_socket[0].split("host=")[1].split(" ")[0]),
             "PGPORT":"56652","PGUSER":ADMIN},timeout=20)
    assert result.returncode !=0
    assert "ANALYTICS054_EXISTING_OBJECT_OWNER_REVIEW_REQUIRED" in result.stderr


def test_migration_wrong_database_refused(db_socket):
    _,script=db_socket
    result=script("SELECT current_database();",dbname="postgres")
    assert result.returncode==0
    env={**os.environ,"PGHOST":str(db_socket[0].split("host=")[1].split(" ")[0]),
         "PGPORT":"56652","PGUSER":ADMIN}
    result=run([str(PG/"psql"),"-X","-q","-v","ON_ERROR_STOP=1",
                "-d","postgres","-f",str(MIGRATION)],env=env,expected=False)
    assert result.returncode !=0
    assert "ANALYTICS054_WRONG_DATABASE" in result.stderr
    assert script("SELECT to_regclass('public.empire_analytics_sessions') IS NULL;",
                  dbname="postgres").returncode==0


def test_pre_consent_event_does_not_become_valid_after_grant(conn):
    s=new_session(conn)
    # Event time is from before the actual consent was recorded.
    before=conn.execute("SELECT clock_timestamp()-interval '2 seconds'").fetchone()[0]
    decide(conn,s,1,"granted")
    with pytest.raises(psycopg.Error,match="ANALYTICS054_PRE_CONSENT_EVENT_DENIED"):
        conn.execute("""
         INSERT INTO public.empire_analytics_event_receipts
         (tenant_id,property_key,event_digest,session_digest,event_kind,page_key,occurred_at)
         VALUES (%s,%s,%s,%s,'page_view','home',%s)
        """,(TENANT_A,PROP,uuid.uuid4().hex*2,s,before))


def test_consent_recorded_at_cannot_be_forged_by_writer(conn):
    s=new_session(conn)
    earlier=conn.execute("SELECT clock_timestamp()-interval '60 seconds'").fetchone()[0]
    conn.execute("""
        INSERT INTO public.empire_analytics_consent_decisions
        (tenant_id,property_key,session_digest,revision,decision,
         policy_revision,evidence_sha256,evidence_class,recorded_at)
        VALUES (%s,%s,%s,1,'granted',%s,%s,'SERVER_VERIFIED_CMP_DECISION',%s)
    """,(TENANT_A,PROP,s,POLICY,uuid.uuid4().hex*2,earlier))
    actual=conn.execute("""
      SELECT recorded_at FROM public.empire_analytics_consent_decisions
      WHERE tenant_id=%s AND property_key=%s AND session_digest=%s AND revision=1
    """,(TENANT_A,PROP,s)).fetchone()[0]
    assert actual > earlier+timedelta(seconds=30)


def test_receipt_received_at_cannot_be_retroactively_forged(conn):
    s=new_session(conn)
    decide(conn,s,1,"granted")
    earlier=conn.execute("SELECT clock_timestamp()-interval '5 days'").fetchone()[0]
    digest=uuid.uuid4().hex*2
    conn.execute("""
      INSERT INTO public.empire_analytics_event_receipts
      (tenant_id,property_key,event_digest,session_digest,
       event_kind,page_key,occurred_at,received_at)
      VALUES (%s,%s,%s,%s,'page_view','home',clock_timestamp(),%s)
    """,(TENANT_A,PROP,digest,s,earlier))
    actual=conn.execute("""
      SELECT received_at FROM public.empire_analytics_event_receipts
      WHERE tenant_id=%s AND property_key=%s AND event_digest=%s
    """,(TENANT_A,PROP,digest)).fetchone()[0]
    assert actual > earlier+timedelta(days=4)


def test_simultaneous_consent_revision_cannot_fork_transaction_order(db_socket):
    dsn=db_socket[0]
    with psycopg.connect(dsn,autocommit=True) as init:
        s=new_session(init)
        decide(init,s,1,"granted")
    def write(rev):
        with psycopg.connect(dsn,autocommit=True) as conn:
            try:
                decide(conn,s,2,rev)
                return True
            except psycopg.Error:
                return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        result=list(pool.map(write,("denied","revoked")))
    assert sorted(result)==[False,True]
    with psycopg.connect(dsn,autocommit=True) as conn:
        rows=conn.execute("""
          SELECT decision FROM public.empire_analytics_consent_decisions
          WHERE tenant_id=%s AND session_digest=%s AND revision=2
        """,(TENANT_A,s)).fetchall()
        assert len(rows)==1
