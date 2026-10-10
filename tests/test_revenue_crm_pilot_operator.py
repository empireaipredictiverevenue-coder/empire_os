"""Real disposable PG18 proof: founder-reviewed CRM invites have no public writer.

Tests import existing 041 disposable fixture. No production DB or mail.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from empire_os.revenue_crm_first_party_login import prepare_crm_invitation
from empire_os.revenue_crm_pilot_operator import PostgresCrmInviteOperator
from test_crm_membership_authority_ephemeral import A, B, membership_pg

FOUNDER_PROOF = "founder:reviewed-crm-pilot-customer-20261010"
MAILBOX_PROOF = "verified-email:independent-operator-check-20261010"


def test_controlled_operator_provisions_only_verified_pending_invite(membership_pg):
    run, sock, port = membership_pg
    from pathlib import Path
    sql = (Path(__file__).resolve().parents[1]
           / "migrations/empiredb/042_crm_first_party_login.sql")
    run(file=sql)
    # Deliberately fixture-only DBA identity. Never create this in production.
    run("CREATE ROLE postgres SUPERUSER LOGIN")
    dsns = (
        f"host={sock} port={port} dbname=crm_membership_fixture user=postgres",
        f"host={sock} port={port} dbname=crm_membership_fixture user=ubuntu",
    )
    operator = PostgresCrmInviteOperator(
        dsns[0], expected_database="crm_membership_fixture",
    )
    # PostgreSQL must observe an untrusted session_user even if the
    # connection wrapper gave us a postgres-labelled DSN.
    class ForceUntrustedConnection:
        def __init__(self, wrong_dsn):
            import psycopg
            self._wrong_dsn = wrong_dsn
            self._connect = psycopg.connect

        def __call__(self, _dsn):
            return self._connect(self._wrong_dsn)

    untrusted = PostgresCrmInviteOperator(
        dsns[0], expected_database="crm_membership_fixture",
        connect_factory=ForceUntrustedConnection(dsns[1]),
    )
    subject = "pilot:verified-test"
    invitation = prepare_crm_invitation(
        subject=subject, email="PILOT@example.invalid", tenant_id=A,
        evidence_ref="person:pilot-independent-identity-reviewed",
    )
    # Diagnostic repr must not disclose the raw one-time token or hashed data.
    assert invitation.token not in repr(invitation)
    assert invitation.password_salt.hex() not in repr(invitation)
    evidence = dict(
        founder_approval_ref=FOUNDER_PROOF,
        verified_recipient_ref=MAILBOX_PROOF,
    )
    # Current membership is a hard requirement, despite operator privileges.
    assert not operator.provision(invitation, **evidence)
    assert not operator.provision(
        invitation, founder_approval_ref="not-approved",
        verified_recipient_ref=MAILBOX_PROOF,
    )
    assert not operator.provision(
        invitation, founder_approval_ref=FOUNDER_PROOF,
        verified_recipient_ref="not-verified-email",
    )
    assert not untrusted.provision(invitation, **evidence)
    assert run("SELECT count(*) FROM public.empire_crm_login_credentials") == "0"

    run(f"""
        INSERT INTO public.empire_crm_tenant_memberships
          (tenant_id,subject,role,status,evidence_ref,verified_at)
        VALUES ('{A}'::uuid,'{subject}','viewer','disabled',
                'fixture:identity-evidence',now());
    """)
    assert not operator.provision(invitation, **evidence)
    run(f"""UPDATE public.empire_crm_tenant_memberships SET status='active'
        WHERE tenant_id='{A}'::uuid AND subject='{subject}';""")
    wrong_tenant = prepare_crm_invitation(
        subject=subject, email="pilot@example.invalid", tenant_id=B,
        evidence_ref="person:pilot-independent-identity-reviewed",
    )
    assert not operator.provision(wrong_tenant, **evidence)
    assert run("SELECT count(*) FROM public.empire_crm_login_credentials") == "0"

    # Exact prior approval, recipient verification and tenant are persisted.
    assert operator.provision(invitation, **evidence)
    row = run(f"""
        SELECT status||'|'||invitation_tenant_id::text||'|'||evidence_ref
        FROM public.empire_crm_login_credentials
        WHERE subject='{subject}';
    """)
    assert row.startswith(f"pending|{A}|")
    assert FOUNDER_PROOF in row and MAILBOX_PROOF in row
    assert invitation.token not in row
    assert run("SELECT count(*) FROM public.empire_crm_login_credentials") == "1"
    # Cannot implicitly resend, replace password materials or rotate invite.
    assert not operator.provision(invitation, **evidence)
    assert run("SELECT count(*) FROM public.empire_crm_login_credentials") == "1"

    # Crucial business outcome: operator-created invite can really be
    # redeemed through EXISTING CRM login code, not just inserted.
    run("""
        CREATE ROLE empire_crm_auth_login LOGIN NOINHERIT;
        GRANT SELECT ON public.empire_crm_login_credentials
          TO empire_crm_auth_login;
        GRANT UPDATE(
          failed_attempts,locked_until,last_login_at,updated_at,
          password_salt,password_digest,status,password_change_required,
          invitation_token_hash,invitation_redeemed_at)
          ON public.empire_crm_login_credentials TO empire_crm_auth_login;
        GRANT EXECUTE ON FUNCTION public.empire_crm_read_member(text,uuid)
          TO empire_crm_membership_login;
    """)
    from empire_os.revenue_crm_first_party_login import PostgresCrmPasswordLogin
    from empire_os.revenue_crm_signed_auth import EmpireDbCrmMembershipReader
    auth = PostgresCrmPasswordLogin(
        f"host={sock} port={port} dbname=crm_membership_fixture "
        "user=empire_crm_auth_login",
    )
    membership = EmpireDbCrmMembershipReader(
        f"host={sock} port={port} dbname=crm_membership_fixture "
        "user=empire_crm_membership_login",
    )
    invited_password = "real-test-only-invite-password-2030!"
    assert auth.authenticate(invitation.login_email, invited_password) is None
    assert auth.accept_invitation(
        invitation.token, invited_password, A, load_membership=membership
    ) is True
    assert auth.accept_invitation(
        invitation.token, invited_password, A, load_membership=membership
    ) is False
    assert auth.authenticate(invitation.login_email, invited_password) == subject


def test_invalid_packet_and_target_fail_closed():
    from datetime import datetime, timezone
    base = prepare_crm_invitation(
        subject="person:verified", email="user@example.invalid", tenant_id=A,
        evidence_ref="identity:checked", now=datetime.now(timezone.utc),
    )
    operator = PostgresCrmInviteOperator(
        "host=/tmp/fake-crm-fixture port=5533 dbname=crm_membership_fixture user=postgres",
        expected_database="crm_membership_fixture",
        connect_factory=lambda _: (_ for _ in ()).throw(
            AssertionError("Invalid invite must not connect to DB")
        )
    )
    checks = [
        replace(base, invitation_token_hash=b"\x00" * 32),
        replace(base, invitation_tenant_id=B),
        replace(base, expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)),
        replace(base, expires_at=datetime.now(timezone.utc) + timedelta(days=9)),
        replace(base, password_salt=b"short"),
        replace(base, password_digest=b"bad"),
        replace(base, token="bad"),
        replace(base, evidence_ref=""),
    ]
    for packet in checks:
        assert operator.provision(
            packet, founder_approval_ref=FOUNDER_PROOF,
            verified_recipient_ref=MAILBOX_PROOF,
        ) is False
    assert operator.provision(
        base, founder_approval_ref="no", verified_recipient_ref=MAILBOX_PROOF,
    ) is False


def test_operator_refuses_noncanonical_production_connection():
    import pytest
    for dsn in (
        "dbname=empiredb user=postgres host=remote.example port=5432",
        "dbname=empiredb user=empiredb_app host=/var/run/postgresql port=5432",
        "dbname=otherdb user=postgres host=/var/run/postgresql port=5432",
        "dbname=empiredb user=postgres host=/tmp/custom port=5432",
        "dbname=empiredb user=postgres host=/var/run/postgresql port=2222",
    ):
        with pytest.raises(ValueError, match="operator"):
            PostgresCrmInviteOperator(dsn)
    assert PostgresCrmInviteOperator(
        "dbname=empiredb user=postgres host=/var/run/postgresql port=5432"
    )._database == "empiredb"
