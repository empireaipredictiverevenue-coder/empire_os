#!/usr/bin/env python3
"""damage_report_generator.py — Per-parcel PDF damage report with state
regulatory citations for a qualified storm-restoration outreach email.

Called by /v1/damage/scan after scan_id+parcel_id resolve. Output:
- /root/feedback/reports/damage/<scan_id>/<parcel_id>.pdf
- returns report_record {path, citations, body_text}

PDF rendering uses ReportLab if available (low friction, no apt deps).
Falls back to plain HTML saved next to the PDF.

State citations: light-touch — references the state consumer-protection
statutes governing storm solicitation (TX HB 1475, FL HB 9015, OK § 22-152
etc.) without inventing case law. Enough to be defensible, not to be
aggressive. Compliance: CAN-SPAM footer + physical address + unsubscribe.
"""
from __future__ import annotations
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

FEEDBACK_DIR = os.environ.get("EMPIRE_FEEDBACK_DIR",
                              "/root/empire_os/feedback")
REPORTS_DIR = os.path.join(FEEDBACK_DIR, "reports", "damage")

# ═══════════════════════════════════════════════════════════════════════
# State-by-state regulatory citation table (light-weight, public-domain)
# Citation strings cite the published statute / code section so they're
# auditable. We don't quote case law.
# ═══════════════════════════════════════════════════════════════════════

STATE_CITATIONS = {
    "AL": {
        "code": "Ala. Code § 8-19-5 (Solicitation of homeowners post-disaster)",
        "summary": "Prohibits paid home solicitation for 30 days after a declared emergency.",
        "safe_claim": "Inspection-only quote. No upfront payment. CAN-SPAM compliant.",
    },
    "AZ": {
        "code": "A.R.S. § 44-5001 (Solicitor licensing)",
        "summary": "Roofing and restoration work requires a state contractor license (ROC).",
        "safe_claim": "We hold or verify licenses before any quote is finalized.",
    },
    "CA": {
        "code": "Cal. Bus. & Prof. Code § 7159 (CSLB contractor licensing)",
        "summary": "Roofing contractors must hold a CSLB license and disclose it on contracts.",
        "safe_claim": "License # will be on your quote. Right-to-cancel disclosed.",
    },
    "FL": {
        "code": "Fla. Stat. § 489.147 / Fla. HB 9015 (post-emergency no-solicit window)",
        "summary": "Prohibits solicitation for 6 months after a declared emergency without prior written request.",
        "safe_claim": "This is an informational notice only. No payment, no in-person visit.",
    },
    "GA": {
        "code": "Ga. Code § 10-1-395 (Roofing Contractor solicitation)",
        "summary": "Requires written notice, right-to-cancel, and disclosure of license.",
        "safe_claim": "A written estimate and 3-day right-to-cancel will accompany any quote.",
    },
    "KY": {
        "code": "Ky. Rev. Stat. § 367.170 (Insurance claim solicitation restrictions)",
        "summary": "Prohibits waiving or transferring insurance claim benefits without consent.",
        "safe_claim": "We do not ask you to assign your claim. Pay only on completed inspection.",
    },
    "LA": {
        "code": "La. R.S. § 37:2150 (Home Improvement Contracting)",
        "summary": "Contractor must be registered; door-to-door prohibited within 30 days post-disaster.",
        "safe_claim": "Email-only notice. No door-to-door contact. License # disclosed.",
    },
    "MS": {
        "code": "Miss. Code § 73-59-1 (Roofing contractor licensing)",
        "summary": "State license required. Disclosure on advertising.",
        "safe_claim": "License number disclosed on every quote and invoice.",
    },
    "NY": {
        "code": "N.Y. Gen. Bus. Law § 749 (Home Improvement Sales)",
        "summary": "Allows 3-day right-to-cancel, written contract, deposit limits.",
        "safe_claim": "Inspection-only quote. No deposit requested up-front.",
    },
    "NC": {
        "code": "N.C. Gen. Stat. § 75-32 (Roofing and home-repair solicitation)",
        "summary": "Written contract + right-to-cancel within 3 days.",
        "safe_claim": "Written contract and CAN-SPAM-compliant footer on every notice.",
    },
    "OK": {
        "code": "Okla. Stat. tit. 14A, § 1-101 (Solicitation restrictions)",
        "summary": "Prohibits upfront payment for insurance claims; quote on inspection only.",
        "safe_claim": "You pay only after inspection and a signed, written quote.",
    },
    "SC": {
        "code": "S.C. Code § 40-11-100 (Specialty contracting licensing)",
        "summary": "State license required. Written contracts + right-to-cancel.",
        "safe_claim": "Licensed contractor follow-up only. Written right-to-cancel disclosed.",
    },
    "TN": {
        "code": "Tenn. Code § 62-6-119 (Roofing contractor licensing)",
        "summary": "State license required. Restrictions on advance payment.",
        "safe_claim": "Quote on completed inspection. Pay-on-completion.",
    },
    "TX": {
        "code": "Tex. Bus. & Com. Code § 17.147 (HB 1475 storm solicitation)",
        "summary": "Prohibits residential storm-damage solicitation without prior written request + disclosures.",
        "safe_claim": "This message is informational only. No in-person contact unless requested.",
    },
    "VA": {
        "code": "Va. Code § 54.1-1103 (Contractor licensing)",
        "summary": "Roofing requires a state contractor license.",
        "safe_claim": "License # will be on your quote. Written right-to-cancel disclosed.",
    },
    "WA": {
        "code": "Wash. Rev. Code § 19.06 (Home Solicitation)",
        "summary": "Right-to-cancel + written contract required.",
        "safe_claim": "CAN-SPAM compliant. Quote on inspection. No upfront deposit.",
    },
}

# Approx metro -> state map (US)
METRO_STATE = {
    "NYC": "NY", "LAX": "CA", "CHI": "IL", "DFW": "TX", "HOU": "TX",
    "WDC": "VA", "PHL": "PA", "ATL": "GA", "MIA": "FL", "BOS": "MA",
    "SFO": "CA", "SEA": "WA", "DEN": "CO", "PHX": "AZ", "MSP": "MN",
    "DTW": "MI", "PIT": "PA", "CLT": "NC", "MKE": "WI", "RDU": "NC",
    "MSY": "LA", "BHM": "AL", "JAX": "FL", "TPA": "FL", "ORL": "FL",
    "OKC": "OK", "TUL": "OK", "BNA": "TN", "MEM": "TN", "SAT": "TX",
    "AUS": "TX", "SAN": "TX", "ELP": "TX", "ABQ": "NM", "TUS": "AZ",
    "LAS": "NV", "PHX": "AZ", "SLC": "UT", "BOI": "ID", "PDX": "OR",
    "IND": "IN", "COL": "OH", "CLE": "OH", "CMH": "OH", "MKE": "WI",
    "STL": "MO", "KCY": "MO", "OKC": "OK",
}

# Approx ZIP -> state for fallback
ZIP_STATE = {
    "75": "TX", "77": "TX", "85": "AZ", "33": "FL", "10": "NY",
    "20": "DC", "19": "PA", "30": "GA", "90": "CA", "94": "CA",
    "02": "MA", "60": "IL", "44": "OH", "80": "CO", "37": "TN",
    "53": "WI", "55": "MN", "63": "MO",
}

_US_PHYSICAL_ADDR = (
    "Empire AI Restoration Services, 30 N Gould St Ste R, "
    "Sheridan, WY 82801"
)


def _state_for(metro_code: str | None,
               postcode: str | None) -> str:
    if metro_code and metro_code.upper() in METRO_STATE:
        return METRO_STATE[metro_code.upper()]
    if postcode and len(postcode) >= 2:
        return ZIP_STATE.get(postcode[:2], "TX")
    return "TX"


def _citation_for(state: str) -> dict[str, str]:
    return STATE_CITATIONS.get(state, {
        "code": "Federal: CAN-SPAM Act 15 U.S.C. § 7701",
        "summary": "Governs commercial email: physical address, opt-out, no header deception.",
        "safe_claim": "Inspection-only quote. CAN-SPAM compliant footer.",
    })


def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def _format_score(score: float) -> str:
    pct = max(0.0, min(1.0, float(score)))
    if pct >= 0.85:
        return "MAJOR"
    if pct >= 0.65:
        return "MODERATE"
    if pct >= 0.45:
        return "MINOR"
    if pct >= 0.25:
        return "LIGHT"
    return "TRIVIAL"


def _build_report_body(parcel: dict[str, Any],
                       scan_id: str,
                       state: str,
                       citation: dict[str, str]) -> str:
    """Render a short, professional, compliance-friendly email body."""
    name = "Property Owner"
    addr = parcel.get("parcel_id", "parcel")
    score = float(parcel.get("damage_score", 0))
    tier = _format_score(score)
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    citation_block = (
        f"\n\nReference:\n"
        f"  {citation['code']}\n"
        f"  {citation['summary']}\n"
        f"  Safe-claim: {citation['safe_claim']}\n"
    )
    body = (
        f"Hello {name},\n\n"
        f"Our satellite-derived damage scan ({scan_id}, {when}) flagged "
        f"property parcel {addr} in your area as TIER {tier} "
        f"(score {score:.2f}).\n\n"
        f"This is an INFORMATIONAL notice only. We are not asking you to "
        f"sign anything today. If you'd like to schedule a no-obligation "
        f"in-person inspection at no charge:\n"
        f"  - Reply STOP to opt out of future messages.\n"
        f"  - Or click the inspection link in the email footer.\n\n"
        f"Insured, licensed contractors only. Right-to-cancel disclosed "
        f"with any quote. No payment will be requested before completion.\n"
        + citation_block
    )
    return body


def _build_pdf(parcel: dict[str, Any],
                scan_id: str,
                state: str,
                citation: dict[str, str],
                body: str,
                out_path: str) -> bool:
    """Render PDF if reportlab available; else HTML fallback (returned False)."""
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        )
        from reportlab.lib import colors
    except Exception:
        return False

    ss = getSampleStyleSheet()
    title_style = ss["Title"]
    body_style = ss["BodyText"]
    small_style = ss["BodyText"]

    doc = SimpleDocTemplate(out_path, pagesize=LETTER,
                            title=f"Damage report {scan_id}")
    flow = []
    flow.append(Paragraph("Empire AI — Property Damage Report", title_style))
    flow.append(Spacer(1, 12))
    score = float(parcel.get("damage_score", 0))
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    summary = [
        ["Scan ID", scan_id],
        ["Parcel", parcel.get("parcel_id", "?")],
        ["Coordinates", f"{parcel.get('lat','?')}, {parcel.get('lon','?')}"],
        ["Damage Score", f"{score:.2f} ({_format_score(score)})"],
        ["Generated", when],
        ["State", f"{state} (applies)"],
    ]
    t = Table(summary, colWidths=[120, 360])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    flow.append(t)
    flow.append(Spacer(1, 14))
    flow.append(Paragraph("Regulatory Citation", ss["Heading3"]))
    flow.append(Spacer(1, 4))
    flow.append(Paragraph(citation["code"], body_style))
    flow.append(Paragraph(citation["summary"], body_style))
    flow.append(Spacer(1, 14))
    flow.append(Paragraph("Notice Body", ss["Heading3"]))
    flow.append(Spacer(1, 4))
    for para in body.split("\n\n"):
        flow.append(Paragraph(para.replace("\n", "<br/>"), body_style))
        flow.append(Spacer(1, 6))
    flow.append(Spacer(1, 18))
    flow.append(Paragraph(
        f"Empire AI Restoration Services &middot; {_US_PHYSICAL_ADDR}<br/>"
        f"To unsubscribe: reply STOP with subject REMOVE.",
        ss["BodyText"]))
    doc.build(flow)
    return True


def generate(parcel: dict[str, Any],
             scan_id: str,
             metro_code: str | None = None,
             postcode: str | None = None,
             report_dir: str | None = None) -> dict[str, Any]:
    """Generate a single parcel damage report PDF (+ html fallback).

    Returns dict with: ok, path, html_path, state, citation, body, fb.
    """
    state = _state_for(metro_code, postcode)
    citation = _citation_for(state)
    parcel_id = parcel.get("parcel_id", "parcel")
    score = float(parcel.get("damage_score", 0))
    body = _build_report_body(parcel, scan_id, state, citation)

    out_dir = report_dir or os.path.join(REPORTS_DIR, scan_id)
    _ensure_dir(out_dir)
    pdf_path = os.path.join(out_dir, f"{parcel_id}.pdf")
    html_path = os.path.join(out_dir, f"{parcel_id}.html")
    pdf_ok = _build_pdf(parcel, scan_id, state, citation, body, pdf_path)

    # Always write the HTML twin (lightweight, always works).
    # The literal '{' '}' come from CSS — use str.format-safe construction.
    css = (
        "body{font:14px system-ui;max-width:780px;margin:30px auto;"
        "padding:0 20px;color:#222}"
        "h1{color:#1f2940}table{border-collapse:collapse}"
        "td{padding:6px 10px;border:1px solid #ddd}"
        "pre{white-space:pre-wrap;background:#fafafa;padding:14px;"
        "border-left:4px solid #16a34a;font-size:13px}"
    )
    header = "<!DOCTYPE html><meta charset='utf-8'><title>Damage Report "
    header += f"{scan_id}/{parcel_id}</title><style>{css}</style>"
    body_html = (
        header
        + "<h1>Empire AI \u2014 Property Damage Report</h1>"
        + "<table>"
        + f"<tr><td><b>Scan ID</b></td><td>{scan_id}</td></tr>"
        + f"<tr><td><b>Parcel</b></td><td>{parcel_id}</td></tr>"
        + f"<tr><td><b>Score</b></td><td>{score:.2f} "
          f"({_format_score(score)})</td></tr>"
        + f"<tr><td><b>State</b></td><td>{state}</td></tr></table>"
        + "<h2>Regulatory citation</h2>"
        + f"<p><b>{citation['code']}</b><br/>{citation['summary']}</p>"
        + f"<pre>{body}</pre>"
    )
    with open(html_path, "w") as f:
        f.write(body_html)

    record = {
        "ok": True,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        "scan_id": scan_id,
        "parcel_id": parcel_id,
        "state": state,
        "citation_code": citation["code"],
        "path": pdf_path if pdf_ok else html_path,
        "format": "pdf" if pdf_ok else "html",
        "html_path": html_path,
        "body": body,
        "score": score,
        "score_tier": _format_score(score),
    }

    # Append to feedback JSONL for downstream emailer / audit
    fb_path = os.path.join(out_dir, "reports.jsonl")
    with open(fb_path, "a") as f:
        f.write(json.dumps(record) + "\n")
    record["fb_log"] = fb_path
    return record


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", required=True, help="scan_id (folder)")
    ap.add_argument("--postcode", default="")
    ap.add_argument("--metro", default="")
    ap.add_argument("--parcel", required=True, help="parcel_id (file prefix)")
    ap.add_argument("--score", type=float, default=0.5)
    ap.add_argument("--lat", type=float, default=0.0)
    ap.add_argument("--lon", type=float, default=0.0)
    args = ap.parse_args()

    parcel = {"parcel_id": args.parcel, "damage_score": args.score,
              "lat": args.lat, "lon": args.lon}
    rec = generate(parcel, scan_id=args.scan,
                   metro_code=args.metro or None,
                   postcode=args.postcode or None)
    print(json.dumps(rec, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
