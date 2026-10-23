"""Disposable PostgreSQL 041 canonical MEMBERSHIP revocation proof, not live EmpireDB.

The dedicated existing CRM membership function is an identity *reader* only.
Agency audience, real client site authority and secret delivery remain separate.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import time
from uuid import UUID
import psycopg
from psycopg import errors
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from empire_os.agency_canonical_membership import AgencyCanonicalMembershipReader
from empire_os.revenue_crm_signed_auth import EmpireDbCrmMembershipReader
from empire_os.agency_connector_authority import (
    AgencySiteGrant, SCHEMA, AUDIENCE, ISSUER, OPERATIONS, DOMAIN,
)
from empire_os.agency_connector_preflight import (
    CanonicalConnectorBinding, prepare_agency_read_session,
    revalidate_agency_read_operation,
)

TENANT = "510152ee-21b1-4d88-af83-3937718b4236"
DIFFERENT_TENANT = "51f9aa7e-a9e0-427b-86ee-a94a2af87e25"
USER = "synthetic:agency-owner"
SITE = "test-dealership"
CONNECTOR = "test-car-yard-connector"
SECRET_REF = "test-agency-wordpress-secret"
ORIGIN = "http://127.0.0.1:25439"

checks: dict[str, bool] = {}
def require(name: str, condition: bool) -> None:
    if not condition:
        raise RuntimeError("CANONICAL_POSTGRES_FIXTURE_CHECK_FAILED:" + name)
    checks[name] = True

socket = Path(os.environ.get("PGHOST", ""))
port = os.environ.get("PGPORT", "")
if (not str(socket).startswith("/tmp/empire_agency_041_sql_")
        or not socket.is_dir() or not port.isdecimal() or os.getuid() != os.stat(socket).st_uid):
    raise RuntimeError("Refusing non-disposable PostgreSQL target")
read_dsn = psycopg.conninfo.make_conninfo(
    dbname="crm_membership_fixture", user="empire_crm_membership_login",
    host=str(socket), port=port, connect_timeout=3,
)
owner_dsn = psycopg.conninfo.make_conninfo(
    dbname="crm_membership_fixture", user="ubuntu",
    host=str(socket), port=port, connect_timeout=3,
)
with psycopg.connect(owner_dsn) as conn:
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO public.empire_crm_tenant_memberships (
                tenant_id, subject, role, status, evidence_ref,
                verified_at, valid_until, revoked_at
            ) VALUES (%s::uuid, %s, 'owner', 'active', 'synthetic-fixture-041',
                CURRENT_TIMESTAMP - INTERVAL '2 days',
                CURRENT_TIMESTAMP + INTERVAL '2 days', NULL)
            """, (TENANT, USER))
require("synthetic_owner_inserted_only_in_temp_database", True)

with psycopg.connect(read_dsn, autocommit=True) as conn:
    with conn.cursor() as cursor:
        try:
            cursor.execute("SELECT count(*) FROM public.empire_crm_tenant_memberships")
        except errors.InsufficientPrivilege as exc:
            require("dedicated_reader_denied_direct_member_table", exc.sqlstate == "42501")
        else:
            raise RuntimeError("Dedicated reader acquired forbidden table read")

reader = EmpireDbCrmMembershipReader(read_dsn)
member = AgencyCanonicalMembershipReader(authoritative_reader=reader, approved_tenant=TENANT)
first = member(USER, TENANT)
require("canonical_041_reader_active_owner", first is not None and first.role == "owner")
require("cross_tenant_denied_by_approved_scope", member(USER, DIFFERENT_TENANT) is None)
require("unknown_member_denied", member("synthetic:unknown", TENANT) is None)

private = Ed25519PrivateKey.generate()
public = private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
now = int(time.time())
claims = {
    "schema": SCHEMA, "iss": ISSUER, "aud": AUDIENCE, "sub": USER,
    "tenant_id": TENANT, "site_id": SITE, "connector_id": CONNECTOR,
    "credential_ref": SECRET_REF, "wp_origin": ORIGIN,
    "operations": list(OPERATIONS), "iat": now-5, "nbf": now-5,
    "exp": now+95, "jti": secrets.token_urlsafe(24),
}
body = DOMAIN + json.dumps(claims,sort_keys=True,separators=(",",":"),
                         ensure_ascii=True).encode("ascii")
signature = base64.urlsafe_b64encode(private.sign(body)).rstrip(b"=").decode("ascii")
envelope={"kid":"ephemeral-test-issuer", "payload":claims, "signature":signature}
state={"site":True, "registry":True}
def grant(user,tenant,site,connector):
    if not state["site"] or (user,tenant,site,connector)!=(USER,TENANT,SITE,CONNECTOR):
        return None
    return AgencySiteGrant(user_id=USER,tenant_id=TENANT,site_id=SITE,
                           connector_id=CONNECTOR,credential_ref=SECRET_REF,
                           wp_origin=ORIGIN,status="active",operations=OPERATIONS)
def registry(tenant,site,connector):
    if not state["registry"] or (tenant,site,connector)!=(TENANT,SITE,CONNECTOR):
        return None
    return CanonicalConnectorBinding(
        tenant_id=TENANT,site_id=SITE,connector_id=CONNECTOR,
        credential_ref=SECRET_REF,wp_origin=ORIGIN,
        allowed_operations=OPERATIONS,active=True,read_only=True)
cred_dir=socket/"credentials"
cred_dir.mkdir(mode=0o700)
cred_file=cred_dir/SECRET_REF
cred_file.write_text("test temporary WordPress password 987654")
cred_file.chmod(0o600)
seen:set[str]=set()
def nonce(n):
    if n in seen: return False
    seen.add(n)
    return True
session=prepare_agency_read_session(
    envelope, pinned_authority_keys={"ephemeral-test-issuer":public},
    membership_reader=member,site_grant_reader=grant,
    trusted_registry_reader=registry,consume_nonce=nonce,
    trusted_credential_directory=cred_dir,trusted_uid=os.getuid(),
    now=lambda:now)
def recheck(operation="vehicles:read"):
    return revalidate_agency_read_operation(
        session,operation,membership_reader=member,
        site_grant_reader=grant,trusted_registry_reader=registry,
        trusted_credential_directory=cred_dir,trusted_uid=os.getuid(),
        now=lambda:now)
require("agency_signed_session_and_real_pg_membership",recheck() is True)
require("agency_secret_not_in_receipt",
    "test temporary WordPress password" not in json.dumps(session.nonsecret_receipt()))

# DISPOSABLE DB change only, not a real user's production membership.
with psycopg.connect(owner_dsn) as conn:
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE public.empire_crm_tenant_memberships
               SET status='disabled', revoked_at=CURRENT_TIMESTAMP
             WHERE tenant_id=%s::uuid AND subject=%s
        """,(TENANT,USER))
require("canonical_041_reader_revoked_return_none", member(USER,TENANT) is None)
try:
    recheck()
except ValueError:
    require("agency_existing_session_revoked_after_pg_update",True)
else:
    raise RuntimeError("Agency session survived canonical PostgreSQL membership revocation")

with psycopg.connect(owner_dsn) as conn:
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE public.empire_crm_tenant_memberships
            SET status='active', revoked_at=NULL, role='operator'
            WHERE tenant_id=%s::uuid AND subject=%s
        """,(TENANT,USER))
require("agency_operator_cannot_inherit_owner_site_scope",member(USER,TENANT) is None)

with psycopg.connect(owner_dsn) as conn:
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE public.empire_crm_tenant_memberships
            SET status='active', revoked_at=NULL, role='owner',
                valid_until=CURRENT_TIMESTAMP-INTERVAL '1 day'
            WHERE tenant_id=%s::uuid AND subject=%s
        """,(TENANT,USER))
require("canonical_041_reader_denies_expired_membership",member(USER,TENANT) is None)

with psycopg.connect(owner_dsn) as conn:
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE public.empire_crm_tenant_memberships
            SET status='active', revoked_at=NULL, role='owner',
                valid_until=CURRENT_TIMESTAMP+INTERVAL '2 days'
            WHERE tenant_id=%s::uuid AND subject=%s
        """,(TENANT,USER))
require("owner_reactivated_for_independent_site_guard",member(USER,TENANT) is not None)
state["site"]=False
try:
    recheck()
except ValueError:
    require("separate_site_grant_still_required",True)
else:
    raise RuntimeError("Missing synthetic site grant allowed session")
state["site"]=True
state["registry"]=False
try:
    recheck()
except ValueError:
    require("separate_registry_approval_still_required",True)
else:
    raise RuntimeError("Missing synthetic connector registry allowed session")

print(json.dumps({
    "status":"REAL_POSTGRES_CANONICAL_041_MEMBERSHIP_REVOCATION_FIXTURE_PASS",
    "checks":checks,"checks_passed":len(checks),
    "canonical_source":"migrations/empiredb/041_crm_membership_authority.sql",
    "real_postgresql_auth_and_membership_reader":True,
    "dedicated_membership_login":"empire_crm_membership_login",
    "fixture_db":"crm_membership_fixture",
    "live_empiredb_queried":False,"live_user_revoked":False,
    "synthetic_site_and_registry_fixture":True,
    "production_changes":False,"real_client_credentials":False,
},sort_keys=True))
