"""One-hit, OFFLINE Postfix staging profile generator and validator.

No live Postfix installed or required; nothing listens. All files are
restricted fixture files in a temporary 0700 directory, destroyed on exit.
Never edits /etc/postfix, MX, systemd, credentials or the production mailbox.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import tempfile
from uuid import UUID

from empire_os.owned_postfix_staging_profile import (
    StageIdentity, generate_candidate_postfix_profile,
    validate_candidate_postfix_profile,
)


def fixture_smoke() -> dict[str, object]:
    test_intent=str(UUID(int=121))
    identity=StageIdentity(test_intent, uid=15000, gid=15000)
    with tempfile.TemporaryDirectory(prefix="empire-postfix-stage-", dir="/tmp") as path:
        root=Path(path)
        if root.lstat().st_mode & 0o777 != 0o700:
            raise ValueError("test root must be owner-only")
        files=generate_candidate_postfix_profile(identity,root=root)
        for name, body in files.items():
            p=root/name
            if p.exists() or p.is_symlink():
                raise ValueError("staged file exists")
            fd=os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                data=body.encode("utf8")
                with os.fdopen(fd,"wb",closefd=False) as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(fd)
            finally:
                os.close(fd)
            mode=stat.S_IMODE(p.lstat().st_mode)
            if mode != 0o600 or p.read_bytes() != body.encode("utf8"):
                raise ValueError("private staged file readback mismatch")
        verified=validate_candidate_postfix_profile(
            {name:(root/name).read_text(encoding="utf8") for name in files},
            identity=identity,root=root,
        )
        return {
            **verified,
            "status":"OFFLINE_POSTFIX_PROFILE_VERIFIED",
            "staged_file_count":len(files),
            "staged_files_owner_only":True,
            "stage_was_temporary":True,
            "synthetic_intent_only":True,
            "mta_binary_invoked":False,
            "actual_mta_parser_verified":False,
            "live_dns_queried":False,
            "live_mailbox_accessed":False,
            "network_calls":0,
            "runtime_socket_bound":False,
            "producer_signing_key_provisioned":False,
        }


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description="Never deploy Postfix; stage only")
    parser.add_argument("--fixture-smoke",action="store_true")
    args=parser.parse_args(argv)
    if not args.fixture_smoke:
        print(json.dumps({
            "schema_version":"empire.mail.postfix_staging_probe.v1",
            "status":"STAGING_NOT_REQUESTED",
            "network_calls":0,
            "runtime_socket_bound":False,
            "receiver_deployed":False,
            "mx_changed":False,
            "execution_authority":"none",
        },sort_keys=True))
        return 0
    result=fixture_smoke()
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"]=="OFFLINE_POSTFIX_PROFILE_VERIFIED" else 2


if __name__=="__main__":
    raise SystemExit(main())
