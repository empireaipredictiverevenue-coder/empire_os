"""Rollback rehearsal for hardened candidate, disposable PG18 only.

Explicitly denies canonical PostgreSQL (socket, port and datadir).
Delete only this synthetic customer ledger schema and its two isolated roles.
"""
from __future__ import annotations
from pathlib import Path
import psycopg
ROOT=Path("/home/ubuntu/empire_releases/data_cloud_pg18_isolated_acceptance_20261107")

def main():
    with psycopg.connect(dbname="empiredb",user="postgres",host=str(ROOT),port=55439) as db:
        datadir,addr,database,user = db.execute(
            "SELECT current_setting('data_directory')::text,inet_server_addr(),current_database()::text,current_user::text").fetchone()
        def decode(x):return x.decode("ascii") if isinstance(x,bytes) else x
        if (Path(decode(datadir)).resolve()!=ROOT.resolve() or addr is not None
            or decode(database)!="empiredb" or decode(user)!="postgres"):
            raise RuntimeError("unsafe rollback target refused")
        assert db.execute("SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='empire_data_cloud_api')").fetchone()[0]
        for role in ("empire_data_cloud_meter_login","empire_data_cloud_api_owner"):
            assert db.execute("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=%s)",(role,)).fetchone()[0]
        db.execute("DROP SCHEMA empire_data_cloud_api CASCADE")
        db.execute("DROP ROLE empire_data_cloud_meter_login")
        db.execute("DROP ROLE empire_data_cloud_api_owner")
    with psycopg.connect(dbname="empiredb",user="postgres",host=str(ROOT),port=55439) as db:
        schema,roles=db.execute("""SELECT EXISTS(SELECT FROM pg_namespace WHERE nspname='empire_data_cloud_api'),
        (SELECT count(*) FROM pg_roles WHERE rolname IN('empire_data_cloud_meter_login','empire_data_cloud_api_owner'))""").fetchone()
        assert schema is False and roles==0,(schema,roles)
        print("HARDENED_PG18_ISOLATED_ROLLBACK_PASS=true")
        print("CUSTOMER_SCHEMA_REMOVED=true; METER_AND_OWNER_ROLES_REMOVED=true")
        print("CANONICAL_EMPIREDB_ACCESSED=false")
if __name__=="__main__":main()
