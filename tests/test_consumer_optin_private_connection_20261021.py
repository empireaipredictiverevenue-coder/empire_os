"""Synthetic-only private-login and suppression-read integration tests."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace

import pytest

from empire_os.consumer_optin_connection_custody import (
    PrivateConsumerConnectionFactory, validate_private_dsn,
    LOGIN, WRITER, TABLES,
)
from empire_os.consumer_optin_suppression_reader import ConsumerPrivateSuppressionReader
from empire_os.consumer_optin_token_security import email_lookup_hmac

DSN = ("host=127.0.0.1 port=5432 dbname=empiredb "
       "user=empire_consumer_optin_login "
       "password=synthetic_FAKE_64_chars_never_valid_on_live_service")

class Cursor:
    def __init__(self, val=None):
        self.val=val
    def fetchone(self):
        return self.val

class FakeConnection:
    def __init__(self, *, wrong_user=False, unsafe_role=False,
                 broad_reader=False, schema_count=5, extra_memberships=0):
        self.commands=[]
        self.closed=False
        self.wrong_user=wrong_user
        self.unsafe_role=unsafe_role
        self.broad_reader=broad_reader
        self.schema_count=schema_count
        self.extra_memberships=extra_memberships
    def execute(self, sql, params=()):
        self.commands.append((sql,params))
        if sql.startswith("SELECT session_user"):
            return Cursor(("empiredb_app" if self.wrong_user else LOGIN,
                           WRITER, "empiredb", "off"))
        if "FROM pg_roles login CROSS JOIN pg_roles writer" in sql:
            arr=(True,False,False,False,False,False,False,
                 False,False,False,False,True,False,False)
            if self.unsafe_role:
                arr=arr[:2]+(True,)+arr[3:]
            return Cursor(arr)
        if "FROM pg_auth_members m" in sql:
            return Cursor((self.extra_memberships,))
        if "FROM pg_class c" in sql:
            return Cursor((self.schema_count,))
        if "FROM pg_policies" in sql:
            return Cursor((5,))
        if "has_table_privilege(current_user,%s,'SELECT')" in sql:
            return Cursor((True,not self.broad_reader))
        if sql.startswith("SELECT EXISTS("):
            return Cursor((not self.broad_reader,))
        return Cursor()
    def close(self):
        self.closed=True
    def __enter__(self):
        return self
    def __exit__(self, typ, exception, tb):
        self.closed=True


def test_no_default_credentials_and_strict_production_identity():
    with pytest.raises(TypeError):
        PrivateConsumerConnectionFactory()
    assert validate_private_dsn(DSN)["user"] == LOGIN
    for invalid in (
        DSN.replace(LOGIN,"empiredb_app"),
        DSN.replace("dbname=empiredb","dbname=postgres"),
        DSN.replace("host=127.0.0.1","host=external.example"),
        DSN.replace("port=5432","port=5433"),
        DSN+" options='-c search_path=evil'",
        DSN.replace("password=synthetic_FAKE_64_chars_never_valid_on_live_service",
                    "password=weak"),
        DSN.replace("host=127.0.0.1","host=/var/run/postgresql"),
    ):
        with pytest.raises(ValueError):
            validate_private_dsn(invalid)


def test_connection_does_not_open_without_separate_custody_approval():
    seen=[]
    factory=PrivateConsumerConnectionFactory(
        dsn=DSN,connect=lambda *a,**kw:seen.append((a,kw))
    )
    assert "synthetic_FAKE" not in repr(factory)
    with pytest.raises(RuntimeError,match="NOT_APPROVED"):
        factory()
    assert seen==[]


def test_private_login_enters_scoped_role_and_verifies_original_schema():
    fake=FakeConnection()
    seen=[]
    def connect(*a,**kw):
        seen.append((a,kw))
        return fake
    factory=PrivateConsumerConnectionFactory(dsn=DSN,owner_authorized=True,connect=connect)
    output=factory()
    assert output is fake and not fake.closed
    assert seen and seen[0][1]["connect_timeout"]==5
    assert any(sql=="SET LOCAL ROLE "+WRITER for sql,_ in fake.commands)
    assert any("FORCE" not in sql and "pg_policies" in sql for sql,_ in fake.commands)
    assert len([1 for sql,_ in fake.commands if "has_table_privilege(current_user,%s,'SELECT')" in sql])==5
    assert all("has_table_privilege('empiredb_app'" not in sql for sql,_ in fake.commands)
    assert all("pg_catalog.aclexplode" in sql for sql,_ in fake.commands if "has_table_privilege(current_user" in sql)
    assert all("INSERT INTO" not in sql for sql,_ in fake.commands)
    assert all("ALTER ROLE" not in sql for sql,_ in fake.commands)


@pytest.mark.parametrize("case",[
    dict(wrong_user=True),
    dict(unsafe_role=True),
    dict(broad_reader=True),
    dict(schema_count=4),
    dict(extra_memberships=1),
])
def test_wrong_login_or_broad_grants_close_connection(case):
    fake=FakeConnection(**case)
    factory=PrivateConsumerConnectionFactory(
        dsn=DSN,owner_authorized=True,connect=lambda *a,**kw:fake
    )
    with pytest.raises(RuntimeError):
        factory()
    assert fake.closed


def test_suppression_reader_only_answers_boolean_and_uses_hmac():
    fake=FakeConnection()
    reader=ConsumerPrivateSuppressionReader(
        connect=lambda:fake,lookup_key=b"K"*32,
        approved_private_custody=True
    )
    assert reader("synthetic@example.test") is True
    sql,params=next((sql,params) for sql,params in fake.commands
                    if "SELECT EXISTS(" in sql)
    assert "empire_consumer_email_suppressions" in sql
    assert "send_claimed_at IS NOT NULL" in sql
    assert "pending_verification" in sql
    assert params==(email_lookup_hmac("synthetic@example.test",key=b"K"*32),)
    assert "synthetic@example.test" not in str(fake.commands)
    assert fake.closed


def test_suppression_not_connected_or_closed_on_error():
    opened=[]
    reader=ConsumerPrivateSuppressionReader(
        connect=lambda:opened.append(True),lookup_key=b"K"*32
    )
    assert reader("synthetic@example.test") is False
    assert not opened
    failed=ConsumerPrivateSuppressionReader(
        connect=lambda:(_ for _ in ()).throw(RuntimeError("DB_DOWN")),
        lookup_key=b"K"*32,approved_private_custody=True
    )
    assert failed("synthetic@example.test") is False


def test_suppressed_or_non_pending_record_rejected():
    fake=FakeConnection(broad_reader=True)
    reader=ConsumerPrivateSuppressionReader(
        connect=lambda:fake,lookup_key=b"K"*32,
        approved_private_custody=True,
    )
    assert reader("synthetic@example.test") is False


def test_cannot_construct_lookup_with_weak_key():
    with pytest.raises(ValueError):
        ConsumerPrivateSuppressionReader(connect=lambda:None,lookup_key=b"short")
