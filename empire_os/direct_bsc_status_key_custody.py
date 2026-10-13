"""First-party buyer-status HMAC key custody; never logs secret bytes.

Root-only explicit installation to the local canonical filesystem.
The issuer and reader MUST load the same 32-byte key; no rotation by
reissuing credentials, no implicit regeneration and no default writes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import stat
import sys

KEY_FILE=Path("/etc/empire_direct_bsc_buyer_status_hmac.key")
FLAG="--approved-direct-bsc-status-key-only"


def read_key(path: Path=KEY_FILE, *, expected_owner: int=0) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("buyer status key absent or symlinked")
    attrs=path.stat()
    if (attrs.st_uid!=expected_owner or attrs.st_mode & 0o777 != 0o600
        or not stat.S_ISREG(attrs.st_mode)):
        raise ValueError("buyer status key permissions unsafe")
    with path.open("rb") as handle:
        key=handle.read(33)
    if len(key)!=32:
        raise ValueError("buyer status key length invalid")
    return key


def install_key(path: Path=KEY_FILE) -> None:
    if os.geteuid()!=0:
        raise ValueError("root operator required")
    if path!=KEY_FILE or not path.parent.is_dir() or path.is_symlink():
        raise ValueError("unapproved key location")
    if path.exists():
        raise ValueError("existing signing key requires no-op verification, never rotation")
    value=secrets.token_bytes(32)
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):
        flags|=os.O_NOFOLLOW
    handle=os.open(path,flags,0o600)
    try:
        os.fchmod(handle,0o600)
        with os.fdopen(handle,"wb",closefd=False) as output:
            output.write(value)
            output.flush()
            os.fsync(handle)
    finally:
        os.close(handle)
    if read_key(path)!=value:
        raise ValueError("created signing key could not be reread")


def main(args: list[str]|None=None)->int:
    args=sys.argv[1:] if args is None else args
    if args==["--verify-only"]:
        try:
            key=read_key()
            if len(key)!=32:raise ValueError("invalid")
            print(json.dumps({"status":"SHARED_STATUS_HMAC_KEY_VERIFIED",
                  "key_bytes_printed":False,"mode":"READ_ONLY"}))
            return 0
        except Exception:
            print(json.dumps({"status":"HELD_STATUS_HMAC_KEY_UNAVAILABLE",
                  "key_bytes_printed":False}))
            return 2
    if args!=["--apply",FLAG]:
        print(json.dumps({"status":"STAGED_NO_KEY_CREATED",
            "explicit_approval_required":True,"key_bytes_printed":False}))
        return 0 if not args else 3
    try:
        install_key()
    except Exception:
        print(json.dumps({"status":"HELD_STATUS_HMAC_KEY_INSTALL",
            "do_not_retry_without_readback":True,"key_bytes_printed":False}))
        return 4
    print(json.dumps({"status":"SHARED_STATUS_HMAC_KEY_INSTALLED",
        "mode":"ISOLATED_KEY_ONLY","key_bytes_printed":False,
        "buyer_token_issued":False,"payment_execution":False,
        "status_endpoint_activated":False}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
