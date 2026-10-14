#!/usr/bin/env python3
"""One-hit non-sending readiness check of existing Empire founder mail paths.

Uses live loopback services, the existing Gmail OAuth token and public DNS.
Returns only boolean identity checks and provider names, never credentials,
message content, token strings or contact records. Never sends or edits DNS.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError

EXPECTED_FROM = "phil@mail.empire-ai.co.uk"
EXPECTED_REPLY = "reply@mail.empire-ai.co.uk"
TOKEN_PATH = Path("/srv/empire_os/runtime/secrets/google-workspace-internal-token.json")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def local_get(port: int, path: str) -> dict:
    if port not in (8775, 8766, 8097) or path not in (
        "/health", "/v1/founder-mailbox/readiness"
    ):
        raise ValueError("UNEXPECTED_LOCAL_READINESS_ROUTE")
    request = Request(f"http://127.0.0.1:{port}{path}", method="GET")
    with build_opener(NoRedirect()).open(request, timeout=4) as response:
        if response.status != 200:
            raise ValueError("READINESS_HTTP_NON_200")
        value = json.loads(response.read(8192))
    if not isinstance(value, dict):
        raise ValueError("INVALID_MAIL_READINESS_JSON")
    return value


def _relay_environment_status() -> dict[str, bool]:
    """Read only existing service's published identities, never print its env."""
    proc = subprocess.run(
        ["systemctl", "show", "empire-gmail-relay.service", "--property=MainPID", "--value"],
        capture_output=True, text=True, check=True, timeout=3,
    )
    pid = int(proc.stdout.strip())
    if pid <= 1:
        raise ValueError("MAIL_RELAY_NOT_RUNNING")
    raw = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    # Read only the four low-risk identity and gate keys. Secret values may
    # coexist in the environment and MUST never be included in output/logs.
    selected: dict[str, str] = {}
    keys = {
        "EMPIRE_GMAIL_SENDER", "EMPIRE_MAIL_RELAY_REPLY_TO",
        "EMPIRE_MAIL_RELAY_MODE", "EMPIRE_MAIL_RELAY_SEND_AUTHORIZED",
    }
    for entry in raw:
        key, sep, val = entry.partition(b"=")
        if sep and key.decode("ascii", "ignore") in keys:
            selected[key.decode("ascii")] = val.decode("utf-8", "replace")
    sender = selected.get("EMPIRE_GMAIL_SENDER", "").lower()
    return {
        "founder_sender_config_matches": bool(
            re.search(r"<phil@mail\.empire-ai\.co\.uk>$", sender)
            or sender.strip() == EXPECTED_FROM
        ),
        "reply_to_config_matches": selected.get("EMPIRE_MAIL_RELAY_REPLY_TO", "").casefold() == EXPECTED_REPLY,
        "relay_observe_mode": selected.get("EMPIRE_MAIL_RELAY_MODE", "").upper() == "OBSERVE",
        "relay_send_authorized": selected.get("EMPIRE_MAIL_RELAY_SEND_AUTHORIZED", "").lower() == "true",
    }


def _lookup_dns(record_type: str, name: str) -> list[str]:
    if record_type not in ("MX", "TXT") or name not in (
        "mail.empire-ai.co.uk", "empire-ai.co.uk"
    ):
        raise ValueError("UNEXPECTED_DNS_QUERY")
    result = subprocess.run(
        ["dig", "+short", record_type, name],
        capture_output=True, text=True, check=True, timeout=5,
    )
    return [line.strip().strip('"') for line in result.stdout.splitlines() if line.strip()]


def _oauth_probe() -> dict[str, bool]:
    from empire_os.gmail_api_transport import GMAIL_SEND_SCOPE, load_gmail_credentials
    from requests import post
    # This may refresh the existing OAuth access token into its original 0600
    # private file; it does not initiate consent or any Gmail send operation.
    credentials = load_gmail_credentials(TOKEN_PATH)
    response = post(
        "https://oauth2.googleapis.com/tokeninfo",
        data={"access_token": credentials.token}, timeout=8,
    )
    if response.status_code != 200:
        return {"token_active_at_google": False, "gmail_send_scope_verified": False,
                "founder_google_account_identity_verified": False}
    value = response.json()
    granted_scopes = set(str(value.get("scope", "")).split())
    owner_verified = False
    from empire_os.google_workspace_mailbox import GoogleWorkspaceMailboxProvider, READ_SCOPE
    if READ_SCOPE in granted_scopes:
        # Google's authenticated getProfile is the account-identity proof;
        # a send-only token or configured From header is not sufficient.
        try:
            provider = GoogleWorkspaceMailboxProvider()
            if provider.configured:
                provider._service()  # profile only; no email or message read
                owner_verified = True
        except Exception:
            owner_verified = False
    return {
        "token_active_at_google": True,
        "gmail_send_scope_verified": GMAIL_SEND_SCOPE in granted_scopes,
        "founder_google_account_identity_verified": owner_verified,
    }


def assess(*, relay: dict, identity: dict, token: dict, imap: dict,
           inbound: dict, root_mx: list[str], sub_mx: list[str], sub_txt: list[str]) -> dict:
    """Pure proof assessment: fail closed when identity or reply path unknown."""
    google_root = any("smtp.google.com" in x.casefold() for x in root_mx)
    ses_subdomain = any("inbound-smtp" in x.casefold() and "amazonaws.com" in x.casefold()
                        for x in sub_mx)
    spf_sub = any("v=spf1" in x.casefold() for x in sub_txt)
    relay_ready = relay.get("ok") is True and relay.get("provider") == "gmail_api"
    imap_ready = imap.get("provider") == "owned_imap" and imap.get("configured") is True
    workspace_read_ready = imap.get("provider") == "google_workspace" and imap.get("configured") is True
    inbound_resend = inbound.get("provider") == "resend"
    blockers = []
    if not relay_ready or not identity.get("founder_sender_config_matches") or not identity.get("reply_to_config_matches"):
        blockers.append("LIVE_FOUNDER_SENDER_OR_REPLY_IDENTITY_UNVERIFIED")
    if not token.get("token_active_at_google") or not token.get("gmail_send_scope_verified"):
        blockers.append("GOOGLE_GMAIL_SEND_OAUTH_UNVERIFIED")
    if not token.get("founder_google_account_identity_verified"):
        blockers.append("GOOGLE_MAILBOX_OWNER_IDENTITY_UNVERIFIED")
    if not imap_ready and not workspace_read_ready:
        blockers.append("FOUNDER_READ_INBOX_NOT_CONFIGURED")
    if ses_subdomain:
        blockers.append("REPLY_SUBDOMAIN_STILL_ROUTES_TO_AMAZON_SES")
    if inbound_resend and ses_subdomain:
        blockers.append("PUBLIC_REPLY_MX_AND_INBOUND_WEBHOOK_PROVIDER_MISMATCH")
    if not spf_sub:
        blockers.append("FOUNDER_SENDER_SUBDOMAIN_SPF_ABSENT")
    blockers.append("INDEPENDENT_END_TO_END_SEND_AND_REPLY_NOT_VERIFIED")
    return {
        "schema_version": "empire.founder-mail-end-to-end-readiness.v1",
        "mode": "OBSERVE", "source": "LIVE_EMPIREOS_PROBES",
        "smtp_sender_configured_for_founder": identity.get("founder_sender_config_matches") is True,
        "reply_to_configured_for_founder": identity.get("reply_to_config_matches") is True,
        "relay_observe_mode": identity.get("relay_observe_mode") is True,
        "relay_send_authorized": identity.get("relay_send_authorized") is True,
        "google_token_verified": token.get("token_active_at_google") is True,
        "gmail_send_permission_verified": token.get("gmail_send_scope_verified") is True,
        "gmail_account_identity_verified": token.get("founder_google_account_identity_verified") is True,
        "founder_imap_configured": imap_ready,
        "founder_workspace_reader_configured": workspace_read_ready,
        "root_domain_mx_google": google_root,
        "reply_subdomain_mx_amazon_ses": ses_subdomain,
        "reply_subdomain_spf_present": spf_sub,
        "resend_inbound_webhook_service_active": inbound.get("ok") is True and inbound_resend,
        "readiness_blockers": blockers,
        "ready_for_internal_mail_test": False,
        "ready_for_prospect_outbound": False,
        "outbound_sent": False,
        "dns_modified": False,
        "services_restarted": False,
        "credential_values_disclosed": False,
    }


def main() -> int:
    relay = identity = token = imap = inbound = {}
    root_mx = sub_mx = sub_txt = []
    failures = []
    probes = (
        ("relay", lambda: local_get(8775, "/health")),
        ("identity", _relay_environment_status),
        ("token", _oauth_probe),
        ("imap", lambda: local_get(8766, "/v1/founder-mailbox/readiness")),
        ("inbound", lambda: local_get(8097, "/health")),
        ("root_mx", lambda: _lookup_dns("MX", "empire-ai.co.uk")),
        ("sub_mx", lambda: _lookup_dns("MX", "mail.empire-ai.co.uk")),
        ("sub_txt", lambda: _lookup_dns("TXT", "mail.empire-ai.co.uk")),
    )
    outputs = {}
    for label, runner in probes:
        try:
            outputs[label] = runner()
        except Exception:
            # No exception text: provider errors can contain private paths/data.
            failures.append(label)
    proof = assess(
        relay=outputs.get("relay", {}), identity=outputs.get("identity", {}),
        token=outputs.get("token", {}), imap=outputs.get("imap", {}),
        inbound=outputs.get("inbound", {}), root_mx=outputs.get("root_mx", []),
        sub_mx=outputs.get("sub_mx", []), sub_txt=outputs.get("sub_txt", []),
    )
    proof["unavailable_probes"] = failures
    print(json.dumps(proof, sort_keys=True))
    # Nonzero until *actual end-to-end deliverability* is proven.
    return 2 if proof["readiness_blockers"] or failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
