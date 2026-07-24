#!/usr/bin/env python3
"""
secrets_admin.py — Empire OS vault writer (separated from loader for safety).

Writes secrets to /root/empire_secrets/<KEY.lower()> atomically:
  1. Create temp file in same dir (so atomic rename works)
  2. chmod 0600 BEFORE writing the value
  3. Write value
  4. fsync
  5. os.replace() to final path
This pattern prevents the "secret briefly world-readable" race that
plain `open(...).write()` has.

NEVER prints values. NEVER accepts values via argv (visible in `ps`).
ONLY stdin (visible only in this process's own memory).

Usage:
  printf '%s' 'YOUR_VALUE' | /root/venv/bin/python3 scripts/secrets_admin.py set SOLANA_VAULT_WALLET

Or interactive:
  /root/venv/bin/python3 scripts/secrets_admin.py set SOLANA_VAULT_WALLET
  (then paste — input is not echoed via getpass fallback)
"""
from __future__ import annotations
import os
import sys
import tempfile
from pathlib import Path

VAULT_DIR = Path("/root/empire_secrets")


def _ensure_vault() -> None:
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(VAULT_DIR, 0o700)


def _atomic_write(path: Path, value: str) -> None:
    """Write value to path atomically with mode 0600 set BEFORE write."""
    fd, tmp = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=str(VAULT_DIR),
    )
    try:
        os.chmod(tmp, 0o600)  # set perms BEFORE writing value
        with os.fdopen(fd, "w") as f:
            f.write(value)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)  # atomic
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def cmd_set(key: str) -> int:
    if not key.replace("_", "").isalnum() or not key.isupper():
        sys.stderr.write(f"ERROR: invalid key name: {key}\n")
        return 1

    _ensure_vault()
    path = VAULT_DIR / key.lower()

    # Read value from stdin (preferred — never appears in argv)
    if sys.stdin.isatty():
        # Interactive TTY — use getpass if available, else raw input
        try:
            import getpass
            value = getpass.getpass(f"Enter value for {key} (hidden): ")
        except Exception:
            sys.stderr.write("WARN: getpass unavailable, input WILL be visible\n")
            value = input(f"Enter value for {key}: ")
    else:
        value = sys.stdin.read()

    value = value.strip()
    if not value:
        sys.stderr.write(f"ERROR: empty value for {key}, nothing written\n")
        return 1

    _atomic_write(path, value)
    # Confirm without revealing
    shown = f"{value[:4]}...{value[-4:]} ({len(value)} chars)" if len(value) > 12 else "***"
    sys.stderr.write(f"WROTE {key} = {shown} to {path} (mode 0600)\n")
    return 0


def cmd_list() -> int:
    if not VAULT_DIR.exists():
        print(f"(no vault at {VAULT_DIR})")
        return 0
    print(f"Vault contents ({VAULT_DIR}):")
    for p in sorted(VAULT_DIR.iterdir()):
        if p.name.startswith("."):
            continue
        try:
            size = p.stat().st_size
            mode = oct(p.stat().st_mode & 0o777)
        except OSError:
            size, mode = -1, "?"
        print(f"  {p.name:<40} {size:>6} bytes  mode={mode}")
    return 0


def cmd_check(key: str) -> int:
    path = VAULT_DIR / key.lower()
    if not path.exists():
        print(f"  {key}: MISSING")
        return 1
    try:
        size = path.stat().st_size
        mode = path.stat().st_mode & 0o777
        if mode != 0o600:
            print(f"  {key}: mode={oct(mode)} (should be 0o600)")
            return 1
        if size == 0:
            print(f"  {key}: EMPTY")
            return 1
        print(f"  {key}: OK ({size} bytes, mode=0o600)")
        return 0
    except OSError as e:
        print(f"  {key}: ERROR {e}")
        return 1


def main() -> int:
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: secrets_admin.py {set KEY|list|check KEY}\n")
        return 1
    cmd = sys.argv[1]
    if cmd == "set":
        if len(sys.argv) != 3:
            sys.stderr.write("Usage: secrets_admin.py set KEY  (pipe value via stdin)\n")
            return 1
        return cmd_set(sys.argv[2])
    if cmd == "list":
        return cmd_list()
    if cmd == "check":
        if len(sys.argv) != 3:
            sys.stderr.write("Usage: secrets_admin.py check KEY\n")
            return 1
        return cmd_check(sys.argv[2])
    sys.stderr.write(f"Unknown command: {cmd}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())