from empire_os.data_cloud_role_model import (
    ObjectGrant,
    RoleSpec,
    compare_grants,
    compare_roles,
    role_safety_findings,
)


def test_capability_role_and_login_pair_are_safe():
    roles = (
        RoleSpec("empire_outbound_sender", can_login=False),
        RoleSpec(
            "empire_outbound_sender_login",
            can_login=True,
            member_of=("empire_outbound_sender",),
        ),
    )
    assert role_safety_findings(roles) == ()


def test_capability_role_cannot_login_or_bypass_rls():
    findings = role_safety_findings(
        (
            RoleSpec(
                "empire_revenue_recognizer",
                can_login=True,
                bypass_rls=True,
            ),
        )
    )
    assert "capability_role_must_be_nologin:empire_revenue_recognizer" in findings
    assert "bypassrls_forbidden:empire_revenue_recognizer" in findings


def test_login_role_must_inherit_exact_matching_capability_without_admin():
    findings = role_safety_findings(
        (
            RoleSpec(
                "empire_bsc_verifier_login",
                can_login=True,
                member_of=("empire_outbound_sender",),
                admin_memberships=("empire_outbound_sender",),
            ),
        )
    )
    assert "login_membership_mismatch:empire_bsc_verifier_login" in findings
    assert "admin_membership_forbidden:empire_bsc_verifier_login" in findings


def test_role_parity_detects_missing_or_changed_roles():
    source = (
        RoleSpec("empire_reader", can_login=False),
        RoleSpec(
            "empire_reader_login",
            can_login=True,
            member_of=("empire_reader",),
        ),
    )
    target = (RoleSpec("empire_reader", can_login=False),)
    result = compare_roles(source, target)
    assert result["compatible"] is False
    assert "missing_role:empire_reader_login" in result["findings"]


def test_unexpected_target_grants_are_security_drift():
    source = (
        ObjectGrant("empire_reader", "table", "prospects", ("SELECT",)),
    )
    target = (
        ObjectGrant("empire_reader", "table", "prospects", ("SELECT",)),
        ObjectGrant("empire_reader", "table", "prospects", ("DELETE",)),
    )
    result = compare_grants(source, target)
    assert result["compatible"] is False
    assert result["unexpected_count"] == 1
    assert any(
        finding.startswith("unexpected_grant:empire_reader:table:prospects")
        for finding in result["findings"]
    )
