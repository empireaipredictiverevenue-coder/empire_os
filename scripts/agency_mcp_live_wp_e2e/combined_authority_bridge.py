"""Disposable-only Python authority bridge for real PostgreSQL 041 + WP/MCP E2E.

Trusted by the *test launcher* via private process stdio, not HTTP or MCP.
Creates a test-only signed agency grant, consults the existing canonical SQL
reader for each tool invocation and rechecks the current scoped secret file.

This is NOT a general purpose issuer, production service, signed-site authority,
or a valid replacement for managed credential delivery.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import sys
import time
from pathlib import Path
from uuid import UUID

import psycopg
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from empire_os.agency_canonical_membership import AgencyCanonicalMembershipReader
from empire_os.agency_connector_authority import AgencySiteGrant, AUDIENCE, DOMAIN, ISSUER, OPERATIONS, SCHEMA
from empire_os.agency_connector_preflight import (
    CanonicalConnectorBinding, prepare_agency_read_session,
    revalidate_agency_read_operation,
)
from empire_os.revenue_crm_signed_auth import EmpireDbCrmMembershipReader

TENANT = "510152ee-21b1-4d88-af83-3937718b4236"
USER = "synthetic:agency-owner"
SITE = "car-yard-synthetic"
CONNECTOR = "wp-synthetic-inventory-read-v1"
SECRET_REF = "agency-wp-test-credential"

temp = Path(os.environ.get("YARD_COMBINED_ROOT", ""))
pg_host = Path(os.environ.get("PGHOST", ""))
port = os.environ.get("PGPORT", "")
origin = os.environ.get("YARD_BASE_URL", "")
secret_dir = temp / "connector-secrets"
if (not temp.is_dir() or not str(temp).startswith("/tmp/empire_agency_combined_")
        or pg_host != temp or not port.isdecimal()
        or os.getuid() != temp.stat().st_uid
        or not origin.startswith("http://127.0.0.1:")
        or not origin.rsplit(":", 1)[-1].isdecimal()
        or not secret_dir.is_dir()):
    raise RuntimeError("Expected private disposable WordPress + PostgreSQL fixture")

dsn = psycopg.conninfo.make_conninfo(
    dbname="crm_membership_fixture", user="empire_crm_membership_login",
    host=str(pg_host), port=port, connect_timeout=3,
)
reader = AgencyCanonicalMembershipReader(
    authoritative_reader=EmpireDbCrmMembershipReader(dsn),
    approved_tenant=TENANT,
)

# Synthetic site/registry fixtures are *not* canonical EmpireDB resources.
def grant(subject: str, tenant: str, site: str, connector: str):
    if (subject, tenant, site, connector) != (USER, TENANT, SITE, CONNECTOR):
        return None
    return AgencySiteGrant(
        user_id=USER,tenant_id=TENANT,site_id=SITE,connector_id=CONNECTOR,
        credential_ref=SECRET_REF,wp_origin=origin,status="active",
        operations=OPERATIONS,
    )

def registry(tenant: str, site: str, connector: str):
    if (tenant, site, connector) != (TENANT, SITE, CONNECTOR):
        return None
    return CanonicalConnectorBinding(
        tenant_id=TENANT,site_id=SITE,connector_id=CONNECTOR,
        credential_ref=SECRET_REF,wp_origin=origin,allowed_operations=OPERATIONS,
        active=True,read_only=True,
    )

private = Ed25519PrivateKey.generate()
public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
now = int(time.time())
claims = {
    "schema":SCHEMA,"iss":ISSUER,"aud":AUDIENCE,"sub":USER,
    "tenant_id":TENANT,"site_id":SITE,"connector_id":CONNECTOR,
    "credential_ref":SECRET_REF,"wp_origin":origin,
    "operations":list(OPERATIONS),"iat":now-2,"nbf":now-2,
    "exp":now+120,"jti":secrets.token_urlsafe(24),
}
payload = DOMAIN + json.dumps(claims,sort_keys=True,separators=(",",":"),
                               ensure_ascii=True).encode("ascii")
envelope = {
    "kid":"test-only-agency-issuer",
    "payload":claims,
    "signature":base64.urlsafe_b64encode(private.sign(payload)).rstrip(b"=").decode("ascii"),
}
used = set()
def nonce(value):
    if value in used:
        return False
    used.add(value)
    return True

session = prepare_agency_read_session(
    envelope,pinned_authority_keys={"test-only-agency-issuer":public},
    membership_reader=reader,site_grant_reader=grant,
    trusted_registry_reader=registry,consume_nonce=nonce,
    trusted_credential_directory=secret_dir,trusted_uid=os.getuid(),
    now=lambda:int(time.time()),
)

def send(value: dict):
    sys.stdout.write(json.dumps(value,sort_keys=True,separators=(",",":")) + "\n")
    sys.stdout.flush()

send({"type":"ready", "tenant":TENANT, "site":SITE,
      "canonical_sql_reader":True, "production_authority":False})

for line in sys.stdin:
    try:
        request = json.loads(line)
        if (not isinstance(request,dict) or set(request)!={"operation","id"}
                or type(request["id"]) is not int or request["id"] < 1
                or not isinstance(request["operation"],str)):
            raise ValueError("Invalid bridge request")
        allowed = revalidate_agency_read_operation(
            session,request["operation"],
            membership_reader=reader,site_grant_reader=grant,
            trusted_registry_reader=registry,
            trusted_credential_directory=secret_dir,trusted_uid=os.getuid(),
            now=lambda:int(time.time()),
        )
        send({"id":request["id"],"allowed":allowed is True})
    except Exception:
        # Never leak SQL errors, auth details or secret file names to MCP client.
        request_id=request.get("id") if isinstance(request,dict) else None
        send({"id":request_id if type(request_id) is int else None,"allowed":False})
