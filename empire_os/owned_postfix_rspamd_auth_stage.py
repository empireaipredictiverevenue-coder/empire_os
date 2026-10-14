"""Owner-gated Postfix inbound authentication Milter profile, test-only.

Receives a BASELINE profile that has already been audited as exact
loopback-only/one-synthetic-alias. This overlays an independently running
Rspamd Milter on 127.0.0.1:11332 and REFUSES SMTP DATA if Milter is down.

IMPORTANT: connectivity to a Milter, a generic Authentication-Results header,
or a message queue ID does NOT by itself authenticate a sender or establish
DMARC alignment, a real buyer, contact consent, canonical EmpireDB binding,
or a cryptographically signed original message receipt.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

from empire_os.owned_postfix_staging_profile import (
    StageIdentity,
    generate_candidate_postfix_profile,
    validate_candidate_postfix_profile,
)

MILTER_PROFILE = {
    "smtpd_milters": "inet:127.0.0.1:11332",
    "non_smtpd_milters": "",
    "milter_default_action": "tempfail",
    "milter_protocol": "6",
    "milter_connect_timeout": "5s",
    "milter_command_timeout": "5s",
    "milter_content_timeout": "10s",
}


def generate_postfix_rspamd_auth_stage(
    identity: StageIdentity, *, root: Path,
) -> dict[str, str]:
    """Generate only, never write OS files or activate Postfix/Rspamd."""
    source = generate_candidate_postfix_profile(identity, root=root)
    fields = "".join(
        f"{key} = {value}\n" for key, value in MILTER_PROFILE.items()
    )
    source["main.cf"] += fields
    validate_postfix_rspamd_auth_stage(source, identity=identity, root=root)
    return source


def validate_postfix_rspamd_auth_stage(
    material: Mapping[str, str], *, identity: StageIdentity, root: Path
) -> dict[str, object]:
    """Fail closed on any relaxation, changed destination, or new Milter."""
    if not isinstance(material, Mapping) or set(material) != {
        "main.cf", "master.cf", "recipients", "header_checks"
    }:
        raise ValueError("complete offline staging and Milter profile required")
    main = material["main.cf"]
    if not isinstance(main, str) or len(main) > 9000:
        raise ValueError("bounded Milter profile required")
    expected = "".join(
        f"{key} = {value}\n" for key, value in MILTER_PROFILE.items()
    )
    if not main.endswith(expected) or sum(line.startswith("smtpd_milters = ") for line in main.splitlines()) != 1:
        raise ValueError("strict authenticated Milter settings required")
    original = dict(material)
    original["main.cf"] = main[:-len(expected)]
    base = validate_candidate_postfix_profile(
        original, identity=identity, root=root
    )
    return {
        **base,
        "schema_version": "empire.mail.postfix_rspamd_milter_stage.v1",
        "milter_fail_closed": True,
        "milter_loopback_only": True,
        "milter_wire_protocol": 6,
        "milter_deployed": False,
        "real_dkim_spf_dmarc_verified": False,
        "trusted_mta_auth_event_verified": False,
        "signed_ingress_receipt_verified": False,
        "actual_buyer_identity_verified": False,
        "production_mx_changed": False,
        "execution_authority": "none",
    }
