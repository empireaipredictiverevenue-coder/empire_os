"""Render a first-party, no-submit EIP-191 wallet signing page from an issued challenge.

Static-only. Never sends signature, invokes a contract, changes the runtime
payment configuration, or generates a new challenge on page load.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path

TOKEN = "__ESCROW_CHALLENGE_JSON__"
SCHEMA = "empire.bsc-treasury-control-challenge.v1"
EXPECTED_ADDRESS = "0x1339b487046B0ad924a10c20b1791608EA8595a8"


def render(template: Path, challenge: Path, destination: Path) -> dict:
    if not template.is_file() or template.is_symlink():
        raise ValueError("trusted template required")
    if challenge.stat().st_mode & 0o077:
        raise ValueError("private challenge file permissions required")
    c = json.loads(challenge.read_text(encoding="utf-8"))
    if (
        c.get("schema_version") != SCHEMA
        or c.get("candidate_wallet") != EXPECTED_ADDRESS
        or c.get("network_chain_id") != 56
        or not isinstance(c.get("message"), str)
        or c.get("actual_funds_moved") is not False
        or c.get("production_payment_activation") is not False
    ):
        raise ValueError("untrusted wallet challenge")
    markup = template.read_text(encoding="utf-8")
    if markup.count(TOKEN) != 1:
        raise ValueError("template challenge slot missing or duplicated")
    # Prevent a challenge payload escaping its JSON script context.
    literal = json.dumps(c, ensure_ascii=True, sort_keys=True).replace("<", r"\u003c").replace(">", r"\u003e")
    markup = markup.replace(TOKEN, literal)
    if any(bad in markup for bad in ("<form", "fetch(", "XMLHttpRequest", "eth_sendTransaction", "eth_signTypedData")):
        raise ValueError("unsafe web signing template operation detected")
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(markup)
            out.flush()
            os.fsync(out.fileno())
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return {"status": "FIRST_PARTY_OFFLINE_WALLET_SIGNER_PAGE_WRITTEN", "url_path": "/" + destination.name,
            "challenge_expires_at": c["expires_at"], "wallet": c["candidate_wallet"],
            "requests_funds": False, "uploads_signature": False}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--challenge", required=True, type=Path)
    p.add_argument("--destination", required=True, type=Path)
    args = p.parse_args()
    template = Path(__file__).resolve().parents[1] / "apps/empire-public-site/treasury-proof-template.html"
    print(json.dumps(render(template, args.challenge, args.destination), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
