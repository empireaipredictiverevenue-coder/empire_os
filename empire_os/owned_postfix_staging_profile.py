"""Postfix loopback-only candidate receiver profile for offline review.

Never activates a service, changes DNS, provisions a mailbox or receives
SMTP. An explicit test UUID is admitted; reply@mail.empire-ai.co.uk and
unlisted or catch-all addresses are NOT admitted.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Mapping
from uuid import UUID

DOMAIN = "mail.empire-ai.co.uk"
HOST = "mx-stage.mail.empire-ai.co.uk"
MAX_BYTES = 512 * 1024
# Fixture hygiene ONLY. The sender can freely supply Authentication-Results
# and Received-SPF headers. Stripping them does not establish trusted DKIM,
# SPF, ARC or DMARC verification; the future mail-owned Milter must do that.
HEADER_CHECKS = (
    "/^Authentication-Results:[[:space:]]*/ IGNORE\n"
    "/^ARC-Authentication-Results:[[:space:]]*/ IGNORE\n"
    "/^Received-SPF:[[:space:]]*/ IGNORE\n"
)
SAFE = re.compile(r"^/tmp/empire-postfix-stage-[a-zA-Z0-9_-]{4,48}$")
REQUIRED = {
    "compatibility_level": "3.6",
    "myhostname": HOST,
    "mydomain": "empire-ai.co.uk",
    "mydestination": "localhost",
    "mynetworks": "127.0.0.0/8",
    "inet_interfaces": "loopback-only",
    "inet_protocols": "ipv4",
    "relay_domains": "",
    "relayhost": "",
    "smtpd_sasl_auth_enable": "no",
    "smtpd_relay_restrictions": "reject_unauth_destination",
    "smtpd_recipient_restrictions": "reject_non_fqdn_recipient, reject_unlisted_recipient, reject_unauth_destination",
    "disable_vrfy_command": "yes",
    "smtpd_helo_required": "yes",
    "smtpd_tls_security_level": "none",
    "virtual_alias_domains": "",
    "virtual_mailbox_domains": DOMAIN,
    "virtual_minimum_uid": "1000",
    "message_size_limit": str(MAX_BYTES),
    "virtual_mailbox_limit": str(MAX_BYTES),
    "recipient_delimiter": "+",
}
# No default SMTP/25 process, outbound smtp transport, submission, smtps,
# UNIX smtpd, IPv6, or external binding. This is *not* production mail.
MASTER = """# EMPIRE OFFLINE LOOPBACK STAGING - NOT PRODUCTION
127.0.0.1:2525 inet n - n - - smtpd
pickup unix n - n 60 1 pickup
cleanup unix n - n - 0 cleanup
qmgr unix n - n 300 1 qmgr
rewrite unix - - n - - trivial-rewrite
bounce unix - - n - 0 bounce
defer unix - - n - 0 bounce
trace unix - - n - 0 bounce
verify unix - - n - 1 verify
flush unix n - n 1000? 0 flush
showq unix n - n - - showq
error unix - - n - - error
retry unix - - n - - error
discard unix - - n - - discard
local unix - n n - - local
virtual unix - n n - - virtual
# Standard internal Unix daemons needed by smtpd; NOT public listeners.
proxymap unix - - n - - proxymap
anvil unix - - n - 1 anvil
scache unix - - n - 1 scache
tlsmgr unix - - n 1000? 1 tlsmgr
"""


@dataclass(frozen=True)
class StageIdentity:
    intent_id: str
    uid: int
    gid: int

    def validate(self) -> str:
        try:
            canonical = str(UUID(self.intent_id))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("canonical reply intent UUID required") from None
        if canonical != self.intent_id:
            raise ValueError("exact lowercase UUID required")
        for number in (self.uid, self.gid):
            if type(number) is not int or not 1000 <= number <= 65534:
                raise ValueError("verified, unprivileged staging UID/GID required")
        return canonical


def _root(path: Path) -> str:
    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError("explicit offline absolute path required")
    text = str(path)
    if not SAFE.fullmatch(text):
        raise ValueError("only isolated staging roots permitted")
    return text


def generate_candidate_postfix_profile(
    identity: StageIdentity, *, root: Path
) -> dict[str, str]:
    intent = identity.validate()
    base = _root(root)
    fields = {
        **REQUIRED,
        "header_checks": f"regexp:{base}/header_checks",
        "virtual_mailbox_maps": f"hash:{base}/recipients",
        "virtual_mailbox_base": f"{base}/maildir",
        "virtual_uid_maps": f"static:{identity.uid}",
        "virtual_gid_maps": f"static:{identity.gid}",
    }
    map_row = f"reply+{intent}@{DOMAIN} jev-{intent}/\n"
    material = {
        "main.cf": "".join(f"{k} = {v}\n" for k, v in fields.items()),
        "master.cf": MASTER,
        "recipients": map_row,
        "header_checks": HEADER_CHECKS,
    }
    validate_candidate_postfix_profile(material, identity=identity, root=root)
    return material


def validate_candidate_postfix_profile(
    material: Mapping[str, str], *, identity: StageIdentity, root: Path
) -> dict[str, object]:
    intent = identity.validate()
    base = _root(root)
    if not isinstance(material, Mapping) or set(material) != {
        "main.cf", "master.cf", "recipients", "header_checks"
    } or any(not isinstance(v, str) or len(v) > 8000 for v in material.values()):
        raise ValueError("bounded candidate profile required")
    settings: dict[str, str] = {}
    for line in material["main.cf"].splitlines():
        if line.count("=") != 1 or line.startswith((" ", "#")):
            raise ValueError("invalid Postfix staged config line")
        k, v = (part.strip() for part in line.split("=", 1))
        if not re.fullmatch(r"[a-z][a-z0-9_]*", k) or k in settings:
            raise ValueError("unknown or duplicate Postfix parameter")
        settings[k] = v
    expected = {
        **REQUIRED,
        "header_checks": f"regexp:{base}/header_checks",
        "virtual_mailbox_maps": f"hash:{base}/recipients",
        "virtual_mailbox_base": f"{base}/maildir",
        "virtual_uid_maps": f"static:{identity.uid}",
        "virtual_gid_maps": f"static:{identity.gid}",
    }
    if settings != expected:
        raise ValueError("staging configuration differs from deny-by-default policy")
    if material["header_checks"] != HEADER_CHECKS:
        raise ValueError("staging authentication header policy changed")
    if material["master.cf"] != MASTER:
        raise ValueError("staging listener or delivery graph was modified")
    recipient = f"reply+{intent}@{DOMAIN} jev-{intent}/\n"
    if material["recipients"] != recipient:
        raise ValueError("only one exact, provisioned reply alias is admitted")
    digest = sha256(json.dumps(
        dict(material), sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return {
        "schema_version": "empire.mail.postfix_staging_profile.v1",
        "mode": "OFFLINE",
        "config_sha256": digest,
        "allowed_recipients": 1,
        "listen_address": "127.0.0.1:2525",
        "bare_reply_mailbox_admitted": False,
        "wildcard_or_catchall_admitted": False,
        "external_relay_enabled": False,
        "smtp_submission_enabled": False,
        "runtime_postfix_parser_verified": False,
        "postmap_compiled": False,
        "untrusted_authentication_headers_policy_present": True,
        "trusted_authentication_filter_installed": False,
        "virtual_maildir_provisioned": False,
        "actual_mail_received": False,
        "receiver_deployed": False,
        "mx_changed": False,
        "mail_sent": False,
        "execution_authority": "none",
    }
