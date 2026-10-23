"""Independent site owner + connector security signatures; no production issuer."""
from __future__ import annotations
import base64
import json
import os
from pathlib import Path
import secrets
import time
from uuid import UUID
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from empire_os.agency_signed_site_grants import (
    SignedAgencySiteSnapshotReader, SignedAgencyConnectorSnapshotReader,
    SITE_SCHEMA, CONNECTOR_SCHEMA, SITE_DOMAIN, CONNECTOR_DOMAIN,
)
from empire_os.agency_connector_authority import OPERATIONS
from empire_os.agency_connector_preflight import (
    prepare_agency_read_session, revalidate_agency_read_operation,
)
from empire_os.agency_connector_authority import SCHEMA, AUDIENCE, ISSUER, DOMAIN
from empire_os.saas_scale import TenantMembership

TENANT = "510152ee-21b1-4d88-af83-3937718b4236"
SUBJECT = "synthetic:agency-owner"
SITE = "car-yard-synthetic"
CONNECTOR = "wp-synthetic-inventory-read-v1"
REF = "test-wp-site-credential"
ORIGIN = "http://127.0.0.1:25439"
NOW = 1_800_000_000

def pub(key):
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

def signed(private, claims, domain, key_id):
    payload=domain+json.dumps(claims,sort_keys=True,separators=(",",":"),
                              ensure_ascii=True,allow_nan=False).encode("ascii")
    return {"key_id":key_id,"claims":claims,
            "signature":base64.urlsafe_b64encode(private.sign(payload)).rstrip(b"=").decode()}

@pytest.fixture
def stage(tmp_path):
    directory=tmp_path/"approved-snapshots"
    directory.mkdir(mode=0o700)
    owner=Ed25519PrivateKey.generate()
    security=Ed25519PrivateKey.generate()
    owner_path=directory/"site-owner.json"
    security_path=directory/"connector-security.json"
    base={"tenant_id":TENANT,"site_id":SITE,"connector_id":CONNECTOR,
          "credential_ref":REF,"wp_origin":ORIGIN,"operations":list(OPERATIONS),
          "status":"active","issued_at":NOW-4,"not_before":NOW-4,
          "expires_at":NOW+180}
    site={"schema":SITE_SCHEMA,"issuer":"empire-agency-site-owner",
          "subject":SUBJECT,**base}
    connector={"schema":CONNECTOR_SCHEMA,"issuer":"empire-agency-connector-security",
               "read_only":True,**base}
    def save(path,data):
        path.write_text(json.dumps(data,separators=(",",":")))
        path.chmod(0o600)
    def sign_site(claims=None):
        save(owner_path,signed(owner, claims or site, SITE_DOMAIN,"site-owner-1"))
    def sign_security(claims=None):
        save(security_path,signed(security, claims or connector,CONNECTOR_DOMAIN,"security-1"))
    sign_site()
    sign_security()
    source=SignedAgencySiteSnapshotReader(owner_path,os.getuid(),
                {"site-owner-1":pub(owner)}, now=lambda:NOW)
    registry=SignedAgencyConnectorSnapshotReader(security_path,os.getuid(),
                {"security-1":pub(security)}, now=lambda:NOW)
    return {
        "source":source,"registry":registry, "site":site,"connector":connector,
        "sign_site":sign_site,"sign_security":sign_security,
        "owner_path":owner_path,"security_path":security_path,
        "private":directory,"owner":owner,"security":security,
    }

def good(stage):
    return stage["source"](SUBJECT,TENANT,SITE,CONNECTOR),stage["registry"](TENANT,SITE,CONNECTOR)

def test_separate_owner_and_security_signatures_authorise_read_only_same_site(stage):
    owner,security=good(stage)
    assert owner.user_id==SUBJECT and owner.tenant_id==security.tenant_id==TENANT
    assert owner.credential_ref==security.credential_ref==REF
    assert owner.wp_origin==security.wp_origin==ORIGIN
    assert owner.operations==security.allowed_operations==OPERATIONS
    assert security.read_only is True

@pytest.mark.parametrize("which,changed",[
    ("site",{"status":"revoked"}),
    ("site",{"tenant_id":"510152ee-21b1-4d88-af83-3937718b4237"}),
    ("site",{"subject":"synthetic:another-owner"}),
    ("site",{"operations":["vehicles:write"]}),
    ("site",{"expires_at":NOW-1}),
    ("site",{"wp_origin":"https://customer.invalid"}),
    ("connector",{"status":"revoked"}),
    ("connector",{"read_only":False}),
    ("connector",{"operations":["capabilities:read","vehicles:read","booking:write"]}),
    ("connector",{"expires_at":NOW-1}),
])
def test_signed_but_revoked_wrong_tenant_or_permission_deny(stage,which,changed):
    original=stage["site" if which=="site" else "connector"]
    stage["sign_site" if which=="site" else "sign_security"]({**original,**changed})
    owner,security=good(stage)
    assert (owner is None) if which=="site" else (security is None)

def test_signature_tampering_wrong_issuer_key_and_missing_file_deny(stage):
    raw=json.loads(stage["owner_path"].read_text())
    raw["claims"]["site_id"]="tampered-site"
    stage["owner_path"].write_text(json.dumps(raw))
    assert good(stage)[0] is None
    stage["sign_site"]()
    bad=SignedAgencySiteSnapshotReader(stage["owner_path"],os.getuid(),
           {"site-owner-1":pub(Ed25519PrivateKey.generate())},now=lambda:NOW)
    assert bad(SUBJECT,TENANT,SITE,CONNECTOR) is None
    stage["security_path"].unlink()
    assert good(stage)[1] is None

def test_untrusted_permissions_and_symlink_are_denied(stage,tmp_path):
    path=stage["owner_path"]
    path.chmod(0o644)
    assert good(stage)[0] is None
    path.chmod(0o600)
    outside=tmp_path/"outside"
    outside.write_text(path.read_text())
    path.unlink()
    path.symlink_to(outside)
    assert good(stage)[0] is None

def test_rechecking_snapshots_after_valid_session_blocks_site_and_registry_revocation(stage,tmp_path):
    cred_dir=tmp_path/"credentials"
    cred_dir.mkdir(mode=0o700)
    file=cred_dir/REF
    file.write_text("synthetic WordPress application password 987")
    file.chmod(0o600)
    issuer=Ed25519PrivateKey.generate()
    claims={
        "schema":SCHEMA,"iss":ISSUER,"aud":AUDIENCE,"sub":SUBJECT,"tenant_id":TENANT,
        "site_id":SITE,"connector_id":CONNECTOR,"credential_ref":REF,"wp_origin":ORIGIN,
        "operations":list(OPERATIONS),"iat":NOW-5,"nbf":NOW-5,
        "exp":NOW+100,"jti":secrets.token_urlsafe(24),
    }
    data=DOMAIN+json.dumps(claims,sort_keys=True,separators=(",",":"),
                           ensure_ascii=True).encode("ascii")
    envelope={"kid":"test-issuer","payload":claims,
              "signature":base64.urlsafe_b64encode(issuer.sign(data)).rstrip(b"=").decode()}
    def membership(u,t):
        return TenantMembership(tenant_id=TENANT,user_id=SUBJECT,role="owner") if (u,t)==(SUBJECT,TENANT) else None
    seen=set()
    def nonce(value):
        if value in seen:return False
        seen.add(value)
        return True
    session=prepare_agency_read_session(
        envelope,pinned_authority_keys={"test-issuer":pub(issuer)},
        membership_reader=membership,site_grant_reader=stage["source"],
        trusted_registry_reader=stage["registry"],consume_nonce=nonce,
        trusted_credential_directory=cred_dir,trusted_uid=os.getuid(),now=lambda:NOW)
    def check():
        return revalidate_agency_read_operation(session,"vehicles:read",
             membership_reader=membership,site_grant_reader=stage["source"],
             trusted_registry_reader=stage["registry"],
             trusted_credential_directory=cred_dir,trusted_uid=os.getuid(),
             now=lambda:NOW)
    assert check() is True
    stage["sign_site"]({**stage["site"],"status":"revoked"})
    with pytest.raises(ValueError):check()
    stage["sign_site"]()
    stage["sign_security"]({**stage["connector"],"status":"revoked"})
    with pytest.raises(ValueError):check()
    stage["sign_security"]()
    assert check() is True
    # A validly signed security-side credential change must NOT override the
    # independent site owner's previous grant or session binding.
    stage["sign_security"]({**stage["connector"],"credential_ref":"other-credential"})
    with pytest.raises(ValueError):check()
    stage["sign_security"]()
    assert check() is True
    file.unlink()
    with pytest.raises(ValueError):check()

def test_reader_fails_without_owner_provisioned_public_keys(stage):
    bad=SignedAgencySiteSnapshotReader(stage["owner_path"],os.getuid(),{},now=lambda:NOW)
    assert bad(SUBJECT,TENANT,SITE,CONNECTOR) is None

from empire_os.agency_owner_gated_connector import OwnerGatedAgencyConnector
from empire_os.agency_canonical_membership import AgencyCanonicalMembershipReader
from empire_os.agency_private_nonce_store import PrivateAgencyNonceStore
from empire_os.revenue_crm_signed_auth import EmpireDbCrmMembershipReader


def owner_context(stage,tmp_path,monkeypatch):
    current={"active":True}
    canonical_sql_reader=EmpireDbCrmMembershipReader(
        "synthetic-not-production",connect_factory=lambda *_:None,
    )
    def existing_read(self, subject, tenant):
        if current["active"] and (subject,tenant)==(SUBJECT,TENANT):
            return TenantMembership(tenant_id=TENANT,user_id=SUBJECT,role="owner")
        return None
    monkeypatch.setattr(EmpireDbCrmMembershipReader,"__call__",existing_read)
    member=AgencyCanonicalMembershipReader(
        authoritative_reader=canonical_sql_reader,approved_tenant=TENANT)
    creds=tmp_path/"owner-private-credentials"
    creds.mkdir(mode=0o700)
    (creds/REF).write_text("synthetic application password do not send")
    (creds/REF).chmod(0o600)
    replay=tmp_path/"replay-store"
    replay.mkdir(mode=0o700)
    nonce=PrivateAgencyNonceStore(replay,os.getuid())
    issuer=Ed25519PrivateKey.generate()
    public_key=pub(issuer)
    ctx=OwnerGatedAgencyConnector(
        canonical_member=member,site_owner=stage["source"],
        connector_security=stage["registry"],replay_receipts=nonce,
        issuer_public_keys={"agency-issuer-1":public_key},
        credential_directory=creds,trusted_uid=os.getuid(),
    )
    current_time=int(time.time())
    claims={
        "schema":SCHEMA,"iss":ISSUER,"aud":AUDIENCE,"sub":SUBJECT,
        "tenant_id":TENANT,"site_id":SITE,"connector_id":CONNECTOR,
        "credential_ref":REF,"wp_origin":ORIGIN,
        "operations":list(OPERATIONS),"iat":current_time-10,
        "nbf":current_time-10,"exp":current_time+110,
        "jti":secrets.token_urlsafe(24),
    }
    signature=base64.urlsafe_b64encode(issuer.sign(
        DOMAIN+json.dumps(claims,sort_keys=True,separators=(",",":"),
                          ensure_ascii=True).encode("ascii")
    )).rstrip(b"=").decode()
    envelope={"kid":"agency-issuer-1","payload":claims,"signature":signature}
    return ctx,envelope,current,issuer


def test_owner_gated_adapter_pins_three_independent_signers_and_revalidates_each_call(
        stage,tmp_path,monkeypatch):
    ctx,envelope,current,_=owner_context(stage,tmp_path,monkeypatch)
    session=ctx.open_session(envelope)
    assert session.nonsecret_receipt()["read_only"] is True
    assert ctx.authorize_tool(session,"vehicles:read") is True
    assert ctx.authorize_tool(session,"capabilities:read") is True
    with pytest.raises(ValueError):ctx.authorize_tool(session,"booking:write")
    with pytest.raises(ValueError):ctx.open_session(envelope)  # persistent nonce
    current["active"]=False
    with pytest.raises(ValueError):ctx.authorize_tool(session,"vehicles:read")


def test_signed_site_and_registry_revocation_deny_existing_owner_gated_session(
        stage,tmp_path,monkeypatch):
    ctx,envelope,current,_=owner_context(stage,tmp_path,monkeypatch)
    session=ctx.open_session(envelope)
    assert ctx.authorize_tool(session,"vehicles:read")
    stage["sign_site"]({**stage["site"],"status":"revoked"})
    with pytest.raises(ValueError):ctx.authorize_tool(session,"vehicles:read")
    stage["sign_site"]()
    stage["sign_security"]({**stage["connector"],"status":"revoked"})
    with pytest.raises(ValueError):ctx.authorize_tool(session,"vehicles:read")


def test_owner_security_and_issuer_signing_keys_cannot_be_reused(
        stage,tmp_path,monkeypatch):
    ctx,envelope,current,_=owner_context(stage,tmp_path,monkeypatch)
    from dataclasses import replace
    with pytest.raises(ValueError,match="independent"):
        replace(ctx,issuer_public_keys=stage["source"].site_owner_public_keys)
    with pytest.raises(ValueError,match="Independent owner"):
        replace(ctx,canonical_member=lambda *_:TenantMembership(TENANT,SUBJECT,"owner"))
