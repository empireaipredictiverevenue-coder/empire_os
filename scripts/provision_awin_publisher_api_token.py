#!/usr/bin/env python3
"""One-time interactive Awin token provisioner. Never pass the token on command line."""
from __future__ import annotations
import getpass
import os
from pathlib import Path
import re
import stat
import sys

TOKEN = Path("/srv/empire_os/runtime/secrets/awin-publisher-api-token")

def main() -> int:
    if not sys.stdin.isatty():
        print("HELD: run in your own interactive EmpireOS terminal, not via a chat or pipeline")
        return 2
    parent=TOKEN.parent
    if not parent.is_dir() or parent.is_symlink():
        print("HELD: the original private secrets directory is missing or unsafe")
        return 2
    if TOKEN.is_symlink() or TOKEN.exists():
        print("HELD: a token location already exists; do not overwrite without separate rotation review")
        return 2
    value=getpass.getpass("Awin Publisher API token (hidden, not logged): ").strip()
    if not re.fullmatch(r"[A-Za-z0-9._~-]{24,2048}",value):
        print("HELD: invalid token format; no file written")
        return 2
    fd=None
    try:
        fd=os.open(TOKEN,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"w",encoding="ascii") as f:
            fd=None
            os.fchmod(f.fileno(),0o600)
            f.write(value)
            f.flush()
            os.fsync(f.fileno())
        print("AWIN_PUBLISHER_API_TOKEN_SECURELY_PROVISIONED (0600; value not displayed)")
        print("Next: /srv/empire_os/.venv/bin/python -B /srv/empire_os/scripts/review_awin_publisher_api.py --write")
        return 0
    except OSError:
        print("HELD: secure credential write unavailable")
        return 2
    finally:
        if fd is not None:
            os.close(fd)

if __name__=="__main__":
    raise SystemExit(main())
