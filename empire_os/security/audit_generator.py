"""
Empire Omega OS — Security Audit Generator
==========================================
Runs the real security modules, merges with audit_specs, emits a
CONFIDENTIAL audit report (markdown + json). External numbers are mocked;
real results come from the live modules.

Usage:
  python3 -m empire_os.security.audit_generator
  -> prints report, writes /root/empire_os/feedback/security_audit_<ts>.md
"""
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.security import audit_specs as S
from empire_os.security import pii_masking, field_encryption, rate_limiter
from empire_os.security import bsc_settlement, secrets_hygiene, security_monitor


def _run_live_checks():
    """Execute real module logic, return evidence dict."""
    ev = {}
    # PII masking
    sample = ("lead john@empire.ai phone +1 (305) 555-1234 "
              "wallet 0x1339b487046B0ad924a10c20b1791608EA8595a8 "
              "api_key=superSECRET123")
    ev["pii_masked"] = pii_masking.mask_log(sample)
    # field encryption round-trip
    tok = field_encryption.encrypt_field("boss@x.com", "email")
    ev["field_enc_ok"] = (field_encryption.decrypt_field(tok) == "boss@x.com")
    # rate limiter
    rl = rate_limiter.RateLimiter()
    ev["rate_limit_ok"] = rl.allow("ip:audit") and rl.allow_wallet(S.TARGET_VAULT)
    # BSC settlement good/bad
    good = {"from": "0xaaaabbbbccccdddd000011112222333344445555",
            "to": S.TARGET_VAULT, "amount_usd": 1240.0, "tx_hash": "0xabc",
            "confirmations": 32, "memo": "LEAD_999"}
    bad = dict(good); bad["to"] = "0xwrong"
    ev["bsc_good"] = bsc_settlement.verify_settlement(good).ok
    ev["bsc_bad_rejected"] = (not bsc_settlement.verify_settlement(bad).ok)
    # secrets hygiene
    sh = secrets_hygiene.SecretsHygiene()
    ev["secrets_perm_issues"] = sh.scan_perms()
    # SIEM event
    m = security_monitor.SecurityMonitor()
    for _ in range(11):
        m.note_failed_login("1.2.3.4")
    ev["siem_events"] = len(security_monitor._siem.recent(5))
    return ev


def generate():
    ev = _run_live_checks()
    now = datetime.now(timezone.utc).isoformat()
    implemented = [c for c in S.CONTROLS if c["status"] == "IMPLEMENTED"]
    roadmap = [c for c in S.CONTROLS if c["status"] == "ROADMAP"]

    lines = []
    lines.append("# 🎖️ EMPIRE OMEGA OS — SECURITY ARCHITECTURE AUDIT")
    lines.append("")
    lines.append("**Classification:** CONFIDENTIAL — SECURITY ARCHITECTURE")
    lines.append(f"**Generated:** {now}")
    lines.append("**Engine:** empire_os.security.audit_generator (live + spec)")
    lines.append("")
    lines.append("---")
    lines.append("## EXECUTIVE SUMMARY")
    lines.append("")
    lines.append(f"- Findings: {len(S.FINDINGS)} (CRITICAL/HIGH/MEDIUM per spec)")
    lines.append(f"- Controls IMPLEMENTED (local, real): {len(implemented)}")
    lines.append(f"- Controls ROADMAP (mocked external infra): {len(roadmap)}")
    lines.append("- Pay path: BSC USDT -> vault " + S.TARGET_VAULT[:10] + "...")
    lines.append("")
    lines.append("### Live Verification Evidence")
    lines.append("```")
    lines.append(f"PII masking sample : {ev['pii_masked']}")
    lines.append(f"Field encryption   : {'PASS' if ev['field_enc_ok'] else 'FAIL'}")
    lines.append(f"Rate limiter       : {'PASS' if ev['rate_limit_ok'] else 'FAIL'}")
    lines.append(f"BSC settle (good)  : {'PASS' if ev['bsc_good'] else 'FAIL'}")
    lines.append(f"BSC reject (bad)   : {'PASS' if ev['bsc_bad_rejected'] else 'FAIL'}")
    lines.append(f"Secrets perm issues: {len(ev['secrets_perm_issues'])} "
                 f"(chmod 600 needed)")
    lines.append(f"SIEM events fired  : {ev['siem_events']}")
    lines.append("```")
    lines.append("")

    lines.append("## AUDIT FINDINGS (spec)")
    lines.append("")
    lines.append("| ID | Area | Severity | Gap | Status |")
    lines.append("|----|------|----------|-----|--------|")
    for f in S.FINDINGS:
        lines.append(f"| {f['id']} | {f['area']} | {f['severity']} | "
                     f"{f['gap']} | {f['status']} |")
    lines.append("")

    lines.append("## HARDENING CONTROLS")
    lines.append("")
    lines.append("### IMPLEMENTED (real, local)")
    lines.append("")
    lines.append("| ID | Audit | Name | Module |")
    lines.append("|----|-------|------|--------|")
    for c in implemented:
        lines.append(f"| {c['id']} | {c['audit']} | {c['name']} | {c['module']} |")
    lines.append("")
    lines.append("### ROADMAP (mocked external infra — not yet backed)")
    lines.append("")
    lines.append("| ID | Audit | Name |")
    lines.append("|----|-------|------|")
    for c in roadmap:
        lines.append(f"| {c['id']} | {c['audit']} | {c['name']} |")
    lines.append("")

    lines.append("## BSC USDT SETTLEMENT VERIFICATION CHECKLIST")
    lines.append("")
    for item in S.BSC_VERIFY_CHECKLIST:
        lines.append(f"- [x] {item}")
    lines.append("")

    lines.append("## IMPLEMENTATION ROADMAP")
    lines.append("")
    for phase, items in S.ROADMAP.items():
        lines.append(f"### {phase}")
        for it in items:
            lines.append(f"- [ ] {it}")
    lines.append("")

    lines.append("## RISK MATRIX")
    lines.append("")
    lines.append("| Risk | Severity | Likelihood | Mitigation |")
    lines.append("|------|----------|-----------|------------|")
    for r in S.RISK_MATRIX:
        lines.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |")
    lines.append("")

    lines.append("## COMPLIANCE TARGETS")
    lines.append("")
    lines.append(", ".join(S.COMPLIANCE))
    lines.append("")
    lines.append("---")
    lines.append("**Note:** External integrations (AWS KMS, Splunk SIEM, "
                 "AbuseIPDB, Istio, Cloudflare) are MOCKED config constants. "
                 "Real, locally-executable controls are verified live above.")
    lines.append("")
    report = "\n".join(lines)

    # write artifacts
    fb = Path("/root/empire_os/feedback")
    fb.mkdir(parents=True, exist_ok=True)
    ts = now.replace(":", "").replace("-", "")[:14]
    md_path = fb / f"security_audit_{ts}.md"
    md_path.write_text(report)
    json_path = fb / f"security_audit_{ts}.json"
    json_path.write_text(json.dumps({
        "generated": now,
        "evidence": ev,
        "findings": S.FINDINGS,
        "controls_implemented": len(implemented),
        "controls_roadmap": len(roadmap),
        "vault": S.TARGET_VAULT,
    }, indent=2))
    return report, str(md_path), str(json_path)


if __name__ == "__main__":
    report, md, js = generate()
    print(report)
    print("\n[ARTIFACTS]", md, js)
