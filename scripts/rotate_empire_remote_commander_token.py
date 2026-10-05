#!/usr/bin/env python3
"""Generate or rotate Empire Remote Commander credentials safely.

The bearer secret is written to a root-readable environment file and never
printed. Only a SHA-256 fingerprint is emitted for operator verification.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import secrets
from pathlib import Path

DEFAULT_PATH = Path("/etc/empire_os/remote-commander.env")
RESOURCE_URL = "https://mcp.empire-ai.co.uk/mcp"
ISSUER_URL = "https://empire-ai.co.uk"


def render(token: str) -> str:
    return (
        f"EMPIRE_OPS_MCP_BEARER_TOKEN={token}\n"
        f"EMPIRE_OPS_MCP_RESOURCE_URL={RESOURCE_URL}\n"
        f"EMPIRE_OPS_MCP_ISSUER_URL={ISSUER_URL}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default=str(DEFAULT_PATH))
    parser.add_argument("--bytes", type=int, default=32)
    args = parser.parse_args()

    size = max(32, min(int(args.bytes), 64))
    token = secrets.token_urlsafe(size)
    target = Path(args.path)
    target.parent.mkdir(parents=True, exist_ok=True)

    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(render(token), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(target)
    os.chmod(target, 0o600)

    fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()
    print(f"path={target}")
    print(f"token_sha256={fingerprint}")
    print("secret_printed=false")
    print("restart_required=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
