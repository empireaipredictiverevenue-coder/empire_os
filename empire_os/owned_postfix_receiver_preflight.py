"""Read-only, strict receiver-release prerequisite check for staged Postfix.

This is NOT a way to activate a receiving MTA. No root actions, DNS, SMTP,
systemd changes, credentials, subprocesses or inbound original messages.
The probe cannot infer Postfix production readiness from package presence.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "empire.mail.postfix_receiver_prerequisites.v1"
_ALLOWED = frozenset({"postconf", "postmap", "postfix"})
_ITEMS = (
    "LIVE_SMTP_ACCEPTANCE_UNTESTED",
    "MAIL_TRANSPORT_AUTHENTICATION_UNAUDITED",
    "FIRST_PARTY_INGRESS_CUSTODY_UNVERIFIED",
    "EXISTING_MX_CUTOVER_UNAPPROVED",
)


def assess_postfix_receiver_prerequisites(
    *, binaries: Mapping[str, bool], mail_owner: Mapping[str, int] | None,
    postdrop: Mapping[str, int] | None, default_privs: Mapping[str, int] | None,
    isolated_runtime_available: bool | None,
) -> dict[str, Any]:
    if (not isinstance(binaries, Mapping) or set(binaries) != _ALLOWED
            or any(type(v) is not bool for v in binaries.values())):
        raise ValueError("explicit known Postfix binary inventory required")
    for role in (mail_owner, postdrop, default_privs):
        if role is not None and (
            not isinstance(role, Mapping)
            or set(role) != {"uid", "gid"}
            or any(type(v) is not int or v < 0 for v in role.values())
        ):
            raise ValueError("bounded numeric owner/group inventory required")
    if type(isolated_runtime_available) not in (bool, type(None)):
        raise ValueError("explicit isolation evidence required")
    blockers = list(_ITEMS)
    if not all(binaries.values()):
        blockers.append("POSTFIX_BINARIES_NOT_INSTALLED")
    if mail_owner is None or mail_owner["uid"] == 0:
        blockers.append("UNPRIVILEGED_POSTFIX_MAIL_OWNER_MISSING")
    if postdrop is None or postdrop["gid"] == 0:
        blockers.append("POSTDROP_SETGID_GROUP_MISSING")
    if default_privs is None or default_privs["uid"] == 0:
        blockers.append("NONROOT_DEFAULT_PRIVS_MISSING")
    if (mail_owner is not None and postdrop is not None
            and mail_owner["gid"] == postdrop["gid"]):
        blockers.append("MAIL_OWNER_AND_POSTDROP_GROUP_CONFLICT")
    if (default_privs is not None and postdrop is not None
            and default_privs["gid"] == postdrop["gid"]):
        blockers.append("DEFAULT_PRIVS_AND_POSTDROP_GROUP_CONFLICT")
    if isolated_runtime_available is not True:
        blockers.append("ISOLATED_SMTP_RUNTIME_NOT_PROVEN")
    return {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY",
        "status": "HOLD_POSTFIX_RECEIVER_ACTIVATION",
        "binaries_present": {name: binaries[name] for name in sorted(_ALLOWED)},
        "mail_owner_present": mail_owner is not None,
        "postdrop_group_present": postdrop is not None,
        "default_privs_present": default_privs is not None,
        "isolated_runtime_verified": isolated_runtime_available,
        "blocked_reasons": sorted(set(blockers)),
        "config_parsing_alone_is_not_acceptance": True,
        "postmap_compiled_with_real_service_identities": False,
        "smtp_rcpt_acceptance_verified": False,
        "external_relay_denial_verified": False,
        "original_message_authentication_verified": False,
        "production_signer_audited": False,
        "real_buyer_replies_verified": None,
        "mail_sent": False,
        "mail_received": False,
        "dns_changed": False,
        "system_packages_changed": False,
        "services_changed": False,
        "execution_authority": "none",
    }
