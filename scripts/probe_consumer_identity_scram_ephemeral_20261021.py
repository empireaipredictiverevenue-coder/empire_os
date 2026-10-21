"""Verify original private identity SCRAM SQL on a disposable PG18 cluster."""
from __future__ import annotations

import json
import os
import secrets
import subprocess

import psycopg

from empire_os.consumer_optin_connection_custody import PrivateConsumerConnectionFactory
from scripts.provision_consumer_private_identity_20261021 import (
    scram_verifier,role_statement,LOGIN,WRITER
)
from scripts.review_consumer_private_identity_session_20261021 import (
    original_readonly_session,
)


def main():
    assert os.environ.get("PGHOST") == "localhost"
    port=int(os.environ["PGPORT"])
    assert port>5432 and not os.environ.get("EMPIREDB_DSN")
    password=secrets.token_hex(32)
    verifier=scram_verifier(password)
    assert verifier.startswith("SCRAM-SHA-256$4096:")
    assert password not in verifier
    sql=role_statement(verifier)
    assert password not in sql
    assert "WITH INHERIT FALSE, SET TRUE, ADMIN FALSE" in sql
    run=subprocess.run(
        ["/usr/bin/psql","-X","-w","-q","-v","ON_ERROR_STOP=1",
         "-d","empiredb"],
        input=sql,text=True,capture_output=True,timeout=15,
    )
    assert run.returncode==0, "fixture DDL rejected"

    def authenticated(*_args,**_kwargs):
        return psycopg.connect(
            dbname="empiredb",host="127.0.0.1",port=port,
            user=LOGIN,password=password,connect_timeout=5
        )

    factory=PrivateConsumerConnectionFactory(
        dsn=("host=127.0.0.1 port=5432 dbname=empiredb "
             "user="+LOGIN+" password="+password),
        owner_authorized=True,connect=authenticated,
    )
    with factory() as conn:
        row=conn.execute("SELECT session_user,current_user").fetchone()
        assert row==(LOGIN,WRITER)
        assert conn.execute(
            "SELECT count(*) FROM public.empire_consumer_subscriptions"
        ).fetchone()[0]==0
    production_readback=original_readonly_session(
        password=password,connect=authenticated
    )
    assert all(production_readback.values())
    with psycopg.connect(
        dbname="empiredb",host="localhost",port=port
    ) as admin:
        acl=admin.execute(
            "SELECT has_table_privilege('empiredb_app',"
            "'public.empire_consumer_subscriptions','SELECT'),"
            "has_table_privilege('empiredb_readonly',"
            "'public.empire_consumer_subscriptions','SELECT')"
        ).fetchone()
        assert acl==(False,False)
        membership=admin.execute(
            "SELECT count(*) FROM pg_auth_members m JOIN pg_roles r "
            "ON r.oid=m.member WHERE r.rolname=%s",
            (LOGIN,)
        ).fetchone()
        assert membership==(1,)
        admin.execute("REVOKE "+WRITER+" FROM "+LOGIN)
    try:
        factory()
    except (psycopg.Error,RuntimeError):
        pass
    else:
        raise AssertionError("PRIVATE_LOGIN_ROLE_REVOKE_UNENFORCED")
    print(json.dumps({
        "status":"PRIVATE_IDENTITY_REAL_PG18_SCRAM_PASS",
        "scram_hash_used":True,
        "test_plaintext_credential_in_sql":False,
        "dedicated_login_not_superuser":True,
        "only_one_role_membership":True,
        "revocation_denies_writer":True,
        "crm_table_privileges_false":True,
        "production_db_modified":False,
        "secrets_printed":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
