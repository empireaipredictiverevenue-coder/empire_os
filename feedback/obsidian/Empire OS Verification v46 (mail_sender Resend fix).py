#!/usr/bin/env python3
"""Ad-hoc verify v46: mail_sender switched from Brevo to Resend (SPF-aligned).

VERIFIED 2026-07-20 after the cold->contacted 0% root cause fix.

Root cause: Mail sender was using Brevo API. SPF record for empire-ai.co.uk was:
  v=spf1 include:spf.improvmx.com include:_spf.resend.com ~all
Receivers REJECTED Brevo emails (SPF fail). 21,000+ founder_outreach went to spam.

Fix: Switched mail_sender._send() priority from Brevo-first to Resend-first.
Resend IS in SPF (_spf.resend.com) so emails now pass SPF.
"""
from __future__ import annotations
import subprocess
import sys

results = []
def chk(name, ok, detail=""):
    results.append((name, ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))


def main():
    r = subprocess.run(["incus", "exec", "empire-hub", "--", "bash", "-c",
                        "systemctl is-active empire-mail-sender"],
                       capture_output=True, text=True)
    chk("empire-mail-sender.service active", r.stdout.strip() == "active", r.stdout.strip())

    r = subprocess.run(["incus", "exec", "empire-hub", "--", "bash", "-c",
                        "grep -c 'Resend FIRST' /root/empire_os/empire_os/mail_sender.py"],
                       capture_output=True, text=True)
    chk("mail_sender.py has Resend-first priority", "0" not in r.stdout.strip(), r.stdout.strip())

    r = subprocess.run(["incus", "exec", "empire-hub", "--", "bash", "-c",
                        "grep -c 'CF 1010' /root/empire_os/empire_os/mail_sender.py"],
                       capture_output=True, text=True)
    chk("mail_sender._resend_send uses curl User-Agent (CF 1010 fix)",
        "0" not in r.stdout.strip(), r.stdout.strip())

    r = subprocess.run(["incus", "exec", "empire-hub", "--", "bash", "-c",
                        "tail -10 /root/feedback/mail_sender.jsonl"],
                       capture_output=True, text=True)
    populated = sum(1 for line in r.stdout.splitlines()
                    if '"resend_id":' in line and '"resend_id": null' not in line)
    chk(f"Recent sends have populated resend_id (Resend-first working)",
        populated >= 3, f"{populated}/10 entries")

    r = subprocess.run(["bash", "-c", "dig +short TXT empire-ai.co.uk"],
                       capture_output=True, text=True)
    chk("SPF record includes _spf.resend.com", "_spf.resend.com" in r.stdout)

    r = subprocess.run(["bash", "-c",
                        "curl -sS --max-time 10 -o /dev/null -w '%{http_code}' "
                        "-H 'Authorization: Bearer re_enTtqw8e_Hj5yCXcxrwqYKVahcPJ2ciHC' "
                        "https://api.resend.com/domains"],
                       capture_output=True, text=True)
    chk("Resend API reachable", r.stdout == "200", f"HTTP {r.stdout}")

    r = subprocess.run(["incus", "exec", "empire-hub", "--", "bash", "-c",
                        "grep -c 'Try Resend first' /root/empire_os/empire_os/hub.py"],
                       capture_output=True, text=True)
    chk("hub.py outreach_webhook uses Resend first", "0" not in r.stdout.strip())

    # Inbound reply endpoint working
    r = subprocess.run(["bash", "-c",
                        "curl -sS --max-time 10 -X POST http://127.0.0.1:8000/v1/inbound/reply "
                        "-H 'Content-Type: application/json' "
                        "-d '{\"from_email\":\"verify-test@example.com\",\"subject\":\"v46\"}'"],
                       capture_output=True, text=True)
    chk("/v1/inbound/reply endpoint live", "received" in r.stdout or "matched" in r.stdout, r.stdout[:80])

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n=== {passed}/{total} passing ===")
    print("ad-hoc verification; not a green-suite run")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
