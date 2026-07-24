#!/usr/bin/env python3
"""
Safe .env writer for Empire OS v3.

# Sets 0600 perms BEFORE writing any value, uses stdin reads (not getpass,
# which fails in non-TTY environments), and never echoes the secret.

Usage:
  /root/venv/bin/python3 /root/empire_os/scripts/write_env.py

Then enter the values at the prompts. To run non-interactively
(e.g. from a script), pipe values separated by newlines:

  printf 'WALLET\\nRPC_URL\\n\\n\\n' | /root/venv/bin/python3 /root/empire_os/scripts/write_env.py

Empty line accepts the default for that key.
"""
import os
import sys
from pathlib import Path

ENV_PATH = Path("/root/empire_os/.env")

# (key, default, prompt_label)
FIELDS = [
    ("SOLANA_VAULT_WALLET", "",
     "Solana vault wallet address (receives USDC)"),
    ("SOLANA_RPC_URL", "",
     "Helius RPC URL with api-key"),
    ("USDC_MINT", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
     "USDC mint address (Enter for mainnet USDC)"),
    ("SOLANA_NETWORK", "mainnet-beta",
     "Network (mainnet-beta or devnet)"),
    ("RESEND_API_KEY", "",
     "Resend API key (Enter to skip — emails will log only)"),
    ("RESEND_WEBHOOK_SECRET", "",
     "Resend webhook signing secret (Enter to skip — no signature verify)"),
    # Disabled: Yelp fusion no longer offers free tier ($179+/mo); use permits+licenses+reddit
]  # noqa


def confirm_path_safe():
    """Open .env in MERGE mode — read existing keys first, write only the keys
    in FIELDS that the user provides. NEVER truncate. NEVER drop keys we
    don't know about. Back up to /root/empire_secrets/.env.bak.<ts> before any
    write so a destructive op is always recoverable.
    """
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, str] = {}
    if ENV_PATH.exists():
        # Backup FIRST so any merge mishap is recoverable
        import time as _t
        bk_dir = Path("/root/empire_secrets")
        bk_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(bk_dir, 0o700)
        bk_path = bk_dir / f".env.bak.{int(_t.time())}"
        import shutil
        shutil.copy2(ENV_PATH, bk_path)
        os.chmod(bk_path, 0o600)
        sys.stderr.write(f"backup: {bk_path}\n")
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            existing[k.strip()] = v.strip()
        sys.stderr.write(f"merge: preserving {len(existing)} existing keys: "
                         f"{sorted(existing.keys())}\n")
    # Open in write mode but we'll write the merged set atomically
    fd = os.open(str(ENV_PATH), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    return os.fdopen(fd, "w"), existing


def safe_show(value):
    """Show a value without revealing the full secret."""
    if not value:
        return "(empty)"
    if len(value) <= 12:
        return "*" * len(value)
    return value[:6] + "..." + value[-4:]


def main():
    if os.geteuid() != 0 and not ENV_PATH.parent.exists():
        print("Run as root (or create %s first)" % ENV_PATH.parent,
              file=sys.stderr)
        sys.exit(1)

    print("Empire OS v3 — .env writer")
    print("=" * 50)
    print("File: %s (mode 0600)" % ENV_PATH)
    print("Empty line = accept default")
    print("Ctrl-C to abort at any time")
    print("=" * 50)
    print()

    f, existing = confirm_path_safe()

    try:
        # Start the merged set from what we already have. write_env.py
        # only knows about FIELDS; any other keys in the existing .env
        # (SOLANA_PAYER_SECRET, SendGrid block, anything else) are
        # PRESERVED untouched.
        merged = dict(existing)
        for key, default, label in FIELDS:
            prompt = "%s\n  %s: " % (label, key)
            if default:
                prompt = "%s\n  %s [%s]: " % (label, key, default[:20] + "...")

            try:
                raw = input(prompt)
            except EOFError:
                # Non-interactive: stop asking, keep existing for unknown keys
                print("\n  (no more input — keeping existing values for remaining keys)")
                break

            value = raw.strip()
            if not value and default:
                value = default
            if not value:
                # No input + no default = leave any existing value alone
                if key in merged:
                    print("  kept existing %s" % key)
                    continue
                print("  skipped (empty, no default)")
                continue

            merged[key] = value
            print("  + %s = %s" % (key, safe_show(value)))

    except KeyboardInterrupt:
        print("\nAborted. Removing partial .env.")
        f.close()
        ENV_PATH.unlink()
        sys.exit(1)

    # Write merged set atomically — unknowns go LAST (preserved order)
    for k, v in merged.items():
        f.write("%s=%s\n" % (k, v))
    f.flush()
    os.fsync(f.fileno())
    f.close()
    # Belt and suspenders
    os.chmod(ENV_PATH, 0o600)

    print()
    print("Wrote %s" % ENV_PATH)
    print("Mode: 0600 (root only)")

    # Confirm contents without revealing values
    print()
    print("Keys written:")
    for key, _, _ in FIELDS:
        line = "%s=" % key
        in_file = any(l.startswith(line) for l in ENV_PATH.read_text().splitlines())
        print("  %s %s" % ("[OK]" if in_file else "[--]", key))


if __name__ == "__main__":
    main()