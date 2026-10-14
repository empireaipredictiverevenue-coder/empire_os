"""One-hit JEV mail route reconciliation. No credentials, messages or writes.

Composes the EXISTING founder-mail read-only probes; no second mailbox
implementation. Explicit --live-readonly required before any GET or DNS query.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from empire_os.jev_gtm_mail_source_truth import assess_jev_ingress_truth
from scripts.verify_founder_mail_end_to_end_readonly import local_get, _lookup_dns

DROPIN = Path(
    "/etc/systemd/system/empire-founder-dashboard-api.service.d/"
    "30-canonical-reply-view.conf"
)
READER_FILE = Path("/etc/empire/founder_reply_reader.dsn")


def _present_only(path: Path) -> bool | None:
    try:
        if path.is_symlink():
            return False
        return path.is_file()
    except OSError:
        return None


def inspect_public_route(
    *,
    local_probe: Callable[[int, str], dict] = local_get,
    dns_probe: Callable[[str, str], list[str]] = _lookup_dns,
    release_presence: Callable[[Path], bool | None] = _present_only,
) -> dict[str, Any]:
    probes = {
        "relay": lambda: local_probe(8775, "/health"),
        "founder": lambda: local_probe(8766, "/v1/founder-mailbox/readiness"),
        "inbound": lambda: local_probe(8097, "/health"),
        "root_mx": lambda: dns_probe("MX", "empire-ai.co.uk"),
        "reply_mx": lambda: dns_probe("MX", "mail.empire-ai.co.uk"),
        "canonical_dropin": lambda: release_presence(DROPIN),
        "canonical_reader": lambda: release_presence(READER_FILE),
    }
    values = {}
    unavailable = []
    for key, call in probes.items():
        try:
            value = call()
            if value is None:
                raise ValueError("evidence unavailable")
            values[key] = value
        except Exception:
            # Never surface credentials, HTTP headers or provider exception.
            unavailable.append(key)
    return assess_jev_ingress_truth(
        relay_health=values.get("relay"),
        founder_readiness=values.get("founder"),
        inbound_health=values.get("inbound"),
        root_mx=values.get("root_mx", ()),
        reply_mx=values.get("reply_mx", ()),
        canonical_release_dropin_present=values.get("canonical_dropin"),
        canonical_reader_credential_present=values.get("canonical_reader"),
        probe_errors=unavailable,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only founder mail source truth; no send or DNS changes"
    )
    parser.add_argument("--live-readonly", action="store_true")
    args = parser.parse_args(argv)
    if not args.live_readonly:
        print(json.dumps({
            "schema_version": "empire.jev.mail_ingress_source_truth.v1",
            "status": "LIVE_READONLY_NOT_REQUESTED",
            "readiness_unknown": True,
            "network_calls": 0,
            "dns_modified": False,
            "mail_sent": False,
            "database_reads": False,
            "execution_authority": "none",
        }, sort_keys=True))
        return 0
    try:
        outcome = inspect_public_route()
        print(json.dumps(outcome, sort_keys=True))
        return 2 if outcome["blocked_reasons"] else 0
    except Exception:
        print(json.dumps({
            "schema_version": "empire.jev.mail_ingress_source_truth.v1",
            "status": "READONLY_SOURCE_TRUTH_UNAVAILABLE",
            "release_authorized": False,
            "outbound_authorized": False,
            "dns_modified": False,
            "mail_sent": False,
            "execution_authority": "none",
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
