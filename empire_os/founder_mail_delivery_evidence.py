"""Read a bounded founder-observed historical mail transport attestation.

This is evidence from the owner's connected Gmail test messages, not a Gmail
server API transaction, today's independent delivery test, canonical business
reply, permission to send prospects, or consent/suppression proof.
"""
from __future__ import annotations

import json
import re
import stat
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(
    "/srv/empire_os/runtime/conversations_replies_control/"
    "founder_owned_mail_delivery_test_evidence_20261014.json"
)


def load_historical_mail_evidence(path: Path = DEFAULT_PATH) -> dict[str, Any]:
    """Fail closed on malformed or unprotected evidence; never print addresses."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("HISTORICAL_MAIL_EVIDENCE_MISSING_OR_SYMLINK")
    meta = path.stat()
    if stat.S_IMODE(meta.st_mode) != 0o600 or not 0 < meta.st_size <= 8192:
        raise ValueError("HISTORICAL_MAIL_EVIDENCE_INSECURE")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict)
        or data.get("schema_version") != "empire.founder_mail.delivery_observation.v1"
        or data.get("source") != "FOUNDER_CONNECTED_GMAIL_READ_ONLY"
        or data.get("historical_test_date") != "2026-10-13"
        or data.get("observed_on") != "2026-10-14"
        or data.get("prospect_send_authorized") is not False
        or data.get("new_email_sent_by_this_check") is not False
        or data.get("direct_workspace_inbox_auth_verified") is not False
        or data.get("canonical_business_reply_verified") is not False
        or data.get("credentials_included") is not False):
        raise ValueError("UNTRUSTED_HISTORICAL_MAIL_EVIDENCE")
    sender = data.get("sender_test")
    base = data.get("reply_base_test")
    alias = data.get("reply_alias_test")
    if not all(isinstance(x, dict) for x in (sender, base, alias)):
        raise ValueError("UNTRUSTED_HISTORICAL_MAIL_EVIDENCE_ROWS")
    if (sender.get("observed_from") != "phil@mail.empire-ai.co.uk"
        or sender.get("dkim_signing_domain") != "empire-ai.co.uk"
        or sender.get("header_from_domain") != "mail.empire-ai.co.uk"
        or base.get("original_recipient") != "reply@mail.empire-ai.co.uk"
        or alias.get("synthetic_test_only") is not True):
        raise ValueError("HISTORICAL_MAIL_EVIDENCE_IDENTITY_MISMATCH")
    for field in ("spf_pass", "dkim_pass", "dmarc_pass", "recipient_is_founder_controlled"):
        if sender.get(field) is not True:
            raise ValueError("HISTORICAL_SENDER_AUTHENTICATION_UNVERIFIED")
    for field in ("visible_forward_to_founder", "provider_inbound_observed"):
        if base.get(field) is not True or alias.get(field) is not True:
            raise ValueError("HISTORICAL_REPLY_FORWARD_UNVERIFIED")
    if alias.get("intent_alias_correlated") is not True:
        raise ValueError("HISTORICAL_INTENT_ALIAS_UNVERIFIED")
    ids = [sender.get("gmail_message_id"), base.get("gmail_message_id"), alias.get("gmail_message_id")]
    if len(set(ids)) != 3 or not all(isinstance(x, str) and re.fullmatch(r"[0-9a-f]{16}", x) for x in ids):
        raise ValueError("HISTORICAL_SOURCE_MESSAGE_ID_INVALID")
    return {
        "schema_version": "empire.founder_mail.delivery_observation_summary.v1",
        "evidence_source": "FOUNDER_CONNECTED_GMAIL_MANUALLY_REVIEWED",
        "test_date": data["historical_test_date"],
        "observed_on": data["observed_on"],
        "founder_sender_reached_controlled_inbox": True,
        "sender_spf_dkim_dmarc_passed": True,
        "reply_base_forwarded": True,
        "reply_alias_forwarded": True,
        "direct_workspace_inbox_verified": False,
        "canonical_business_reply_verified": False,
        "prospect_send_authorized": False,
        "new_email_sent": False,
    }
