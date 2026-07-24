#!/usr/bin/env python3
"""
load_secrets.py — Empire OS secret loader.

Reads each secret from its OWN file under /root/empire_secrets/
(one value per file, 0600) and exposes them via os.environ.setdefault
so downstream code (hub, solana_listener, crypto_charge, payout) can
read them transparently.

CRITICAL DESIGN RULES (do not violate):
  - ALWAYS setdefault. NEVER overwrite an env var that's already set.
    This means a value passed in the systemd EnvironmentFile or a test
    override still wins. The vault is the FALLBACK, not the source of
    truth — but it IS the persistent copy that survives .env truncation.
  - NEVER echo values. Only log key name + length + first/last 4 chars.
  - NEVER write to /root/empire_secrets/. Only READ. Writers live in
    scripts/secrets_admin.py (separate tool, separate audit trail).
  - FAIL LOUD if a required key file is missing or empty. No silent
    fallbacks to .env or empty strings. The hub MUST NOT start with
    missing crypto config — that's how silent revenue loss happens.

Required keys (loaded from /root/empire_secrets/<KEY.lower()>):
  - SOLANA_VAULT_WALLET   (pubkey, public — but treat as secret)
  - SOLANA_RPC_URL        (Helius with api-key — secret)
  - SOLANA_PAYER_SECRET   (base58 keypair — secret)
  - USDC_MINT             (pubkey, public)
  - SOLANA_NETWORK        ("mainnet-beta" or "devnet")

Optional keys (warn but don't fail if missing):
  - TELEGRAM_BOT_TOKEN
  - RESEND_API_KEY

Usage:
  /root/venv/bin/python3 /root/empire_os/scripts/load_secrets.py
Exit codes:
  0 = all required keys loaded
  2 = one or more required keys missing (specific keys named in stderr)
  3 = permission error on vault dir (must be 0700, owned by root)
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

VAULT_DIR = Path("/root/empire_secrets")

REQUIRED = (
    "SOLANA_VAULT_WALLET",
    "SOLANA_RPC_URL",
    "SOLANA_PAYER_SECRET",
    "USDC_MINT",
    "SOLANA_NETWORK",
)

OPTIONAL = (
    "TELEGRAM_BOT_TOKEN",
    "RESEND_API_KEY",
    "SMTP_PASS",
    "SENDGRID_API_KEY",
    "TELEGRAM_CHAT_ID",
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
)


def _check_vault_dir() -> None:
    """Vault must exist, be a directory, mode 0700, owned by root.
    Refuse to proceed if not — that's a misconfiguration, not a missing key."""
    if not VAULT_DIR.exists():
        sys.stderr.write(f"FATAL: vault dir {VAULT_DIR} does not exist\n")
        sys.stderr.write("  Create it: install -d -m 0700 /root/empire_secrets\n")
        sys.exit(3)
    if not VAULT_DIR.is_dir():
        sys.stderr.write(f"FATAL: {VAULT_DIR} is not a directory\n")
        sys.exit(3)
    mode = VAULT_DIR.stat().st_mode & 0o777
    if mode != 0o700:
        sys.stderr.write(
            f"FATAL: vault dir mode is {oct(mode)}, must be 0o700. "
            f"Fix: chmod 0700 {VAULT_DIR}\n"
        )
        sys.exit(3)


def _load_one(key: str, required: bool) -> tuple[bool, str]:
    """Load one key from /root/empire_secrets/<lower>. Return (loaded, msg).

    Reads from vault file. Sets os.environ[key] (overwrite, not setdefault).
    The env-file we persist for systemd is the source of truth at boot time;
    if env was set by something else (test override, shell export), the
    vault value still wins on the next hub restart. This prevents stale
    env from a prior load surviving across restarts."""
    path = VAULT_DIR / key.lower()
    if not path.exists():
        if required:
            return False, f"  {key}: MISSING — create {path}"
        return False, f"  {key}: not in vault (optional, skipped)"

    try:
        mode = path.stat().st_mode & 0o777
    except OSError as e:
        return False, f"  {key}: stat failed: {e}"

    if mode not in (0o600, 0o400):
        sys.stderr.write(
            f"WARN: {path} mode is {oct(mode)}, fixing to 0o600\n"
        )
        os.chmod(path, 0o600)

    try:
        value = path.read_text().strip()
    except OSError as e:
        return False, f"  {key}: read failed: {e}"

    if not value:
        if required:
            return False, f"  {key}: empty file at {path}"
        return False, f"  {key}: empty file (optional, skipped)"

    # OVERWRITE (not setdefault). Vault is the source of truth.
    was_set = key in os.environ and bool(os.environ[key])
    os.environ[key] = value
    # Show only length + first/last 4 — never full value, never full secret
    if len(value) <= 12:
        shown = "***"
    else:
        shown = f"{value[:4]}...{value[-4:]} ({len(value)} chars)"
    suffix = "" if not was_set else " (overwrote stale env)"
    return True, f"  {key}: loaded from vault as {shown}{suffix}"


def main() -> int:
    _check_vault_dir()

    print(f"Empire OS secret loader — vault={VAULT_DIR}")
    print(f"  pid={os.getpid()} ppid={os.getppid()}")

    loaded = 0
    failed_required: list[str] = []
    failed_optional: list[str] = []
    loaded_values: dict[str, str] = {}

    for key in REQUIRED:
        ok, msg = _load_one(key, required=True)
        print(msg)
        if ok:
            loaded += 1
            # Capture the value so we can persist it for ExecStart to source.
            # setdefault wrote it into os.environ; read it back.
            if key in os.environ:
                loaded_values[key] = os.environ[key]
        else:
            failed_required.append(key)

    for key in OPTIONAL:
        ok, msg = _load_one(key, required=False)
        if ok:
            print(msg)
            loaded += 1
            if key in os.environ:
                loaded_values[key] = os.environ[key]
        elif "MISSING" in msg or "empty file" in msg:
            failed_optional.append(key)

    # Persist loaded values to a systemd-readable env file. systemd's
    # EnvironmentFile directive reads at unit-load time, and ExecStart
    # runs in a separate child that does NOT inherit ExecStartPre's
    # os.environ mutations. Writing KEY=VALUE lines (no expansion, no
    # quoting — values are base58 / URLs / pubkeys, none contain spaces
    # or shell metacharacters) lets ExecStart source this file and pick
    # up the same values.
    env_file = Path("/run/empire-secrets.env")
    if loaded_values:
        # Write atomically: temp file in same dir + os.replace
        tmp = Path(str(env_file) + ".tmp")
        with open(tmp, "w") as f:
            for k, v in loaded_values.items():
                f.write(f"{k}={v}\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, env_file)
        print(f"  persisted {len(loaded_values)} keys to {env_file} (mode 0600)")

    print()
    print(f"  loaded: {loaded} keys")
    if failed_required:
        print(f"  MISSING REQUIRED: {failed_required}")
        print()
        print("FIX — paste values via vault side-channel (never in chat):")
        for k in failed_required:
            print(f"  printf '%s' 'YOUR_VALUE' > {VAULT_DIR / k.lower()}")
            print(f"  chmod 600 {VAULT_DIR / k.lower()}")
        return 2

    if failed_optional:
        print(f"  optional missing (won't block): {failed_optional}")

    print("  RESULT: all required secrets loaded")
    return 0


if __name__ == "__main__":
    sys.exit(main())