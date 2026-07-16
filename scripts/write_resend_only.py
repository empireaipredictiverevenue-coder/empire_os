#!/usr/bin/env python3
"""Add (or replace) RESEND_API_KEY in the existing /root/empire_os/.env
without touching any other keys. Sets 0600 perms before writing. Never
echoes the value."""
import os, sys
from pathlib import Path

ENV_PATH = Path("/root/empire_os/.env")


def safe_show(s, show=6):
    if not s:
        return "(empty)"
    return s[:show] + "..." + s[-4:] if len(s) > show + 8 else s[:3] + "..."


if not ENV_PATH.exists():
    print(f"ERROR: {ENV_PATH} does not exist. Run write_env.py first.",
          file=sys.stderr)
    sys.exit(1)

mode = ENV_PATH.stat().st_mode & 0o777
if mode != 0o600:
    print(f"Fixing perms ({oct(mode)} → 0o600)", file=sys.stderr)
    os.chmod(ENV_PATH, 0o600)

lines = ENV_PATH.read_text().splitlines()
new_lines = []
removed = False
for line in lines:
    if line.startswith("RESEND_API_KEY="):
        removed = True
        continue
    if line.strip() and not line.strip().startswith("#"):
        new_lines.append(line)

# Read key
api_key = ""
if not sys.stdin.isatty():
    api_key = sys.stdin.read().strip()
    api_key = api_key.split("\n")[0].strip()
else:
    try:
        api_key = input("Enter RESEND_API_KEY (visible — paste in your TTY, not chat): ").strip()
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)

if not api_key or api_key.lower() in ("none", "skip"):
    print("No key entered, exiting.", file=sys.stderr)
    sys.exit(1)

os.chmod(ENV_PATH, 0o600)
new_lines.append(f"RESEND_API_KEY={api_key}")
ENV_PATH.write_text("\n".join(new_lines) + "\n")
os.chmod(ENV_PATH, 0o600)

print(f"Wrote RESEND_API_KEY = {safe_show(api_key)} to {ENV_PATH}", file=sys.stderr)
print(f"  perms: 0o600", file=sys.stderr)
print(f"  {'replaced' if removed else 'added'}: RESEND_API_KEY")
