"""Single-command read-only Postfix receiver prerequisites.

No service install, Docker access, user namespace request or package
download. Treat isolated SMTP runtime as UNKNOWN until separately certified.
"""
from __future__ import annotations

import argparse
import grp
import json
import pwd
from pathlib import Path

from empire_os.owned_postfix_receiver_preflight import (
    assess_postfix_receiver_prerequisites,
)


def _principal(name: str) -> dict[str, int] | None:
    try:
        user=pwd.getpwnam(name)
    except KeyError:
        return None
    return {"uid": user.pw_uid, "gid": user.pw_gid}


def _postdrop() -> dict[str, int] | None:
    try:
        group=grp.getgrnam("postdrop")
    except KeyError:
        return None
    return {"uid": 0, "gid": group.gr_gid}


def inspect_preflight() -> dict:
    binaries={
        name: (Path("/usr/sbin") / name).is_file()
        for name in ("postfix","postconf","postmap")
    }
    return assess_postfix_receiver_prerequisites(
        binaries=binaries, mail_owner=_principal("postfix"),
        postdrop=_postdrop(), default_privs=_principal("nobody"),
        isolated_runtime_available=None,
    )


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(
        description="No-permission/no-email receiver readiness probe"
    )
    parser.add_argument("--read-only",action="store_true")
    parsed=parser.parse_args(argv)
    if not parsed.read_only:
        print(json.dumps({
            "schema_version":"empire.mail.postfix_receiver_prerequisites.v1",
            "status":"RECEIVER_PREFLIGHT_NOT_REQUESTED",
            "execution_authority":"none", "mail_sent":False,
            "services_changed":False,
        },sort_keys=True))
        return 0
    try:
        outcome=inspect_preflight()
        print(json.dumps(outcome,sort_keys=True))
    except Exception:
        print(json.dumps({
            "schema_version":"empire.mail.postfix_receiver_prerequisites.v1",
            "status":"RECEIVER_PREFLIGHT_UNAVAILABLE",
            "activation_authorized":False,
            "execution_authority":"none",
            "mail_sent":False,"services_changed":False,
        },sort_keys=True))
    return 2


if __name__=="__main__":
    raise SystemExit(main())
