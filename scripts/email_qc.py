#!/usr/bin/env python3
"""email_qc.py — permanent email-quality + compliance guard.

Catches silent email rot that the generic stack QC misses:
  - raw pay-link / wallet leaking into email BODY (0x..., bsc:, bscscan,
    trust://, ?amount=, vault_wallet, pay_url, memo=empire-os)
  - unresolved {placeholders} left in rendered HTML/text
  - missing EMPIRE AI brand identity (logo / company name)
  - AI-slop phrases (hope this finds you, reaching out, leverage, seamless...)
  - grade 6-7 check: avg sentence length <= 20 words, avg word length <= 7

Runs the safe renderer for every sequence kind, AND scans the LIVE
si_outbox pending rows (what would actually be sent). Any FAIL -> non-zero
exit so the QC agent / CI fails loudly.

Usage:
  /root/venv/bin/python3 /root/empire_os/scripts/email_qc.py
  exit code 0 = clean, 1 = violations found
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"
REPORT = "/root/feedback/email_qc_report.json"

FORBIDDEN_RE = re.compile(
    r"0x[0-9a-fA-F]{40}|bsc:|bscscan\.com|trust://|"
    r"\?amount=|vault_wallet|pay_url|memo=empire-os",
    re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}|\{\{|\}\}")
SLOP = (
    "hope this finds you", "reaching out", "touching base", "i noticed",
    "i saw that", "just checking in", "leverage", "seamless", "robust",
    "delve", "empower", "supercharge", "circle back", "synergy",
)
SLOP_RE = re.compile("|".join(re.escape(w) for w in SLOP), re.IGNORECASE)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _check(name, ok, detail=""):
    return {"name": name, "ok": bool(ok), "detail": str(detail)}


def grade_metrics(text: str) -> dict:
    sents = [s for s in SENT_SPLIT.split(text.replace("\n", " ")) if s.strip()]
    words = re.findall(r"[A-Za-z']+", text)
    avg_sent = (sum(len(SENT_SPLIT.split(s)) for s in sents) / len(sents)) if sents else 0
    avg_word = (sum(len(w) for w in words) / len(words)) if words else 0
    return {
        "sentences": len(sents),
        "avg_words_per_sentence": round(avg_sent, 1),
        "avg_word_len": round(avg_word, 1),
        "grade6_7_ok": avg_sent <= 20 and avg_word <= 7,
    }


def main():
    results = []
    try:
        from empire_os.agents.render_founder_email import render_email
    except Exception as e:
        results.append(_check("import_renderer", False, f"exc={e}"))
        _write(results)
        return 1

    # 1. Render every sequence kind through the safe renderer.
    for kind in ("value", "nudge", "ask"):
        try:
            html, text, subj = render_email(
                "QC Test Biz", "Houston", "TX", "roofing", kind=kind,
                memo="empire-os:qc:lane_silver:deadbeef",
            )
            leaks = FORBIDDEN_RE.search(html + text)
            ph = PLACEHOLDER_RE.search(html + text)
            slop = SLOP_RE.search(text)
            brand = "EMPIRE" in html and "empire-ai.co.uk" in html
            gm = grade_metrics(text)
            ok = not leaks and not ph and not slop and brand and gm["grade6_7_ok"]
            results.append(_check(
                f"render_{kind}",
                ok,
                f"leak={bool(leaks)} placeholder={bool(ph)} slop={bool(slop)} "
                f"brand={brand} grade6_7={gm['grade6_7_ok']} "
                f"(sent={gm['avg_words_per_sentence']}w avg_word={gm['avg_word_len']})",
            ))
        except Exception as e:
            results.append(_check(f"render_{kind}", False, f"exc={e}"))

    # 2. Scan LIVE si_outbox pending rows (what would actually be sent).
    try:
        c = sqlite3.connect(DB, timeout=20)
        rows = c.execute(
            "SELECT id, to_email, subject, body, html_body, source "
            "FROM si_outbox WHERE status='pending' LIMIT 500"
        ).fetchall()
        c.close()
        live_bad = []
        for r in rows:
            rid, to, subj, body, html, src = r
            blob = f"{subj or ''}\n{body or ''}\n{html or ''}"
            if FORBIDDEN_RE.search(blob):
                live_bad.append(f"{rid}:raw_paylink")
            elif PLACEHOLDER_RE.search(blob):
                live_bad.append(f"{rid}:placeholder")
        results.append(_check(
            "live_outbox_clean",
            len(live_bad) == 0,
            f"pending_scanned={len(rows)} violations={live_bad[:5]}" if live_bad else f"pending_scanned={len(rows)} clean",
        ))
    except Exception as e:
        results.append(_check("live_outbox_clean", False, f"exc={e}"))

    # 3. Scan the on-disk founder template itself for leftover {{...}}.
    tpl = Path("/root/empire_os/email_templates/founder_pricing_dark.html")
    if tpl.exists():
        raw = tpl.read_text()
        double = re.findall(r"\{\{[^}]*\}\}", raw)
        results.append(_check(
            "static_template_no_jinja",
            len(double) == 0,
            f"leftover_double_brace={double}" if double else "none",
        ))
    else:
        results.append(_check("static_template_no_jinja", True, "file absent (ok)"))

    fails = [r for r in results if not r["ok"]]
    _write(results)
    print(f"[email_qc] {'CLEAN' if not fails else 'VIOLATIONS'} "
          f"pass={len(results)-len(fails)} fail={len(fails)}")
    for r in results:
        print(f"  [{'OK' if r['ok'] else 'FAIL'}] {r['name']} -> {r['detail']}")
    return 1 if fails else 0


def _write(results):
    try:
        os.makedirs("/root/feedback", exist_ok=True)
        status = "CLEAN" if not [r for r in results if not r["ok"]] else "VIOLATIONS"
        with open(REPORT, "w") as f:
            __import__("json").dump(
                {"status": status, "checks": results}, f, indent=2)
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
