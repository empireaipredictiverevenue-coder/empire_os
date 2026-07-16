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
    """Create .env with 0600 perms BEFORE any value is written."""
    if ENV_PATH.exists():
        # Don't overwrite a real config without asking
        resp = ""
        if sys.stdin.isatty():
            resp = input("%s exists. Overwrite? [y/N]: " % ENV_PATH).strip().lower()
        # In pipe mode or with empty input, default to NO (safe default)
        if resp != "y":
            print("Aborted. Existing .env left untouched.")
            sys.exit(1)
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Create the file with 0600 right now, before any secret enters it
    fd = os.open(str(ENV_PATH), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    return os.fdopen(fd, "w")


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

    f = confirm_path_safe()

    try:
        for key, default, label in FIELDS:
            prompt = "%s\n  %s: " % (label, key)
            if default:
                prompt = "%s\n  %s [%s]: " % (label, key, default[:20] + "...")

            try:
                raw = input(prompt)
            except EOFError:
                # Non-interactive: stop asking
                print("\n  (no more input — using defaults for remaining)")
                break

            value = raw.strip()
            if not value and default:
                value = default
            if not value:
                print("  skipped (empty, no default)")
                continue

            f.write("%s=%s\n" % (key, value))
            print("  + %s = %s" % (key, safe_show(value)))

    except KeyboardInterrupt:
        print("\nAborted. Removing partial .env.")
        f.close()
        ENV_PATH.unlink()
        sys.exit(1)

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