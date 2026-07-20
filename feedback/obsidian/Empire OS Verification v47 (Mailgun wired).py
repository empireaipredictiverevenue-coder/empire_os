#!/usr/bin/env python3
"""Ad-hoc verify v47: mail_sender switched to Mailgun-first."""
import subprocess
import sys

results = []
def chk(name, ok, detail=""):
    results.append((name, ok))
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}" + (f" -- {detail}" if detail else ""))


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)


def main():
    # 1. Mailgun env vars
    r = sh("grep ^MAILGUN_API_KEY= /root/empire_os/.env")
    chk("MAILGUN_API_KEY set in .env", "MAILGUN_API_KEY=" in r.stdout)

    r = sh("grep ^MAILGUN_DOMAIN= /root/empire_os/.env")
    chk("MAILGUN_DOMAIN set in .env", "MAILGUN_DOMAIN=" in r.stdout and "sandbox" in r.stdout)

    # 2. mail_sender.py has _mailgun_send
    r = sh("incus exec empire-hub -- bash -c 'grep -c _mailgun_send /root/empire_os/empire_os/mail_sender.py'")
    chk("mail_sender.py has _mailgun_send", "0" not in r.stdout.strip())

    # 3. Mailgun-first priority
    r = sh("incus exec empire-hub -- bash -c 'grep -A 1 MAILGUN_API_KEY /root/empire_os/empire_os/mail_sender.py | head -3'")
    chk("mail_sender.py Mailgun-first", "MAILGUN_API_KEY" in r.stdout)

    # 4. hub.py Mailgun first
    r = sh("incus exec empire-hub -- bash -c 'grep -A 1 MAILGUN_API_KEY /root/empire_os/empire_os/hub.py | head -3'")
    chk("hub.py outreach_webhook Mailgun", "MAILGUN_API_KEY" in r.stdout)

    # 5. Mailgun API auth
    r = sh("KEY=$(grep ^MAILGUN_API_KEY= /root/empire_os/.env | cut -d= -f2-); curl -sS --max-time 10 -u api:$KEY https://api.mailgun.net/v3/domains")
    has_domains = "items" in r.stdout and "sandbox" in r.stdout
    chk("Mailgun API authenticates", has_domains, r.stdout[:80])

    # 6. mail_sender active
    r = sh("incus exec empire-hub -- bash -c 'systemctl is-active empire-mail-sender'")
    chk("empire-mail-sender.service active (container)", r.stdout.strip() == "active", r.stdout.strip())

    # 7. Recent webhook hits Mailgun (returns Mailgun error, not Resend)
    r = sh("tail -1 /root/feedback/outreach_webhook.jsonl 2>/dev/null")
    hit_mailgun = "Forbidden" in r.stdout and "Mailgun" in r.stdout or "mailgun.org" in r.stdout
    chk("Hub webhook now hits Mailgun first", hit_mailgun,
        "Mailgun 'Please activate' = correct wiring" if hit_mailgun else r.stdout[:100])

    # 8. Verify mail_sender.jsonl has Mailgun attempts (not just Resend 401)
    r = sh("tail -5 /root/feedback/mail_sender.jsonl 2>/dev/null")
    has_mailgun_attempt = "mailgun" in r.stdout.lower() or "Mailgun" in r.stdout
    chk("mail_sender.jsonl shows Mailgun attempts", has_mailgun_attempt,
        "Recent entries still 401 from old Resend attempts" if not has_mailgun_attempt
        else "Mailgun attempts confirmed")

    # 9. Mailgun activation status
    r = sh("KEY=$(grep ^MAILGUN_API_KEY= /root/empire_os/.env | cut -d= -f2-); DOMAIN=$(grep ^MAILGUN_DOMAIN= /root/empire_os/.env | cut -d= -f2-); curl -sS --max-time 10 -u api:$KEY https://api.mailgun.net/v3/$DOMAIN/messages -X POST -F from=test@test.com -F to=test@test.com -F subject=test -F text=test")
    is_activated = "is not allowed to send" not in r.stdout and "Please activate" not in r.stdout
    chk("Mailgun account ACTIVATED (user must click activation email)",
        is_activated,
        "ACTIVATED" if is_activated else f"NEEDS ACTIVATION: user click email from Mailgun")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n=== {passed}/{total} passing ===")
    print("ad-hoc verification; not a green-suite run")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
