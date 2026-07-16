"""
Email template CLI — list, render, dump to file.

Usage:
    python -m empire_os.templates.email.cli list
    python -m empire_os.templates.email.cli avenues
    python -m empire_os.templates.email.cli render outreach_first_touch \\
        --recipient "Sarah" --niche roofing --metro "Dallas, TX" \\
        --source-detail "23 verified reviews" --avenue leadgen \\
        --out /tmp/email.html
    python -m empire_os.templates.email.cli render lead_delivered \\
        --recipient "Operator" --niche hvac --metro "PHX" \\
        --lead-id "lead_abc123" --out /tmp/lead.html
"""
from __future__ import annotations

import argparse
import json
import sys

from . import (
    render, render_subject, list_all, list_outreach, list_internal,
    avenue_ids, get_avenue, AVENUES,
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="empire-email",
        description="Empire AI branded email template CLI",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List all templates (outreach + internal)")
    sub.add_parser("outreach", help="List outreach templates only")
    sub.add_parser("internal", help="List internal templates only")
    sub.add_parser("avenues", help="List configured business avenues")

    rend = sub.add_parser("render", help="Render a template to stdout or file")
    rend.add_argument("template", help="Template name (see list)")
    rend.add_argument("--avenue", choices=avenue_ids(),
                      help="Business avenue id (leadgen, paypercall, saas, loans)")
    rend.add_argument("--tenant", default="default", help="Tenant id for unsub link")
    rend.add_argument("--recipient", default="there", help="recipient_name")
    rend.add_argument("--niche", default="", help="niche")
    rend.add_argument("--metro", default="", help="metro")
    rend.add_argument("--source-detail", default="", help="source_detail")
    rend.add_argument("--lead-id", default="", help="lead_id (internal only)")
    rend.add_argument("--lead-url", default="", help="lead_url (internal only)")
    rend.add_argument("--amount", default="", help="amount (payout_settled only)")
    rend.add_argument("--period", default="this week", help="period")
    rend.add_argument("--method", default="USDC", help="payout method")
    rend.add_argument("--tx-id", default="", help="tx_id")
    rend.add_argument("--reply-to", default="ops@empire-ai.co.uk")
    rend.add_argument("--sender", default="Empire OS team")
    rend.add_argument("--out", "-o", default="", help="Output path (HTML)")
    rend.add_argument("--out-text", default="", help="Output path (plain text)")
    rend.add_argument("--format", "-f", choices=["html", "text", "both"],
                      default="both")

    return p


def _vars_from_args(args: argparse.Namespace) -> dict:
    return {
        "avenue_id":     args.avenue,
        "tenant_id":     args.tenant,
        "recipient_name":args.recipient,
        "niche":         args.niche,
        "metro":         args.metro,
        "source_detail": args.source_detail,
        "lead_id":       args.lead_id,
        "lead_url":      args.lead_url,
        "amount":        args.amount,
        "period":        args.period,
        "method":        args.method,
        "tx_id":         args.tx_id,
        "reply_to":      args.reply_to,
        "sender_name":   args.sender,
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "list":
        print("Templates:")
        for n in list_all():
            print(f"  {n}")
        return 0

    if args.cmd == "outreach":
        for n in list_outreach():
            print(f"  {n}")
        return 0

    if args.cmd == "internal":
        for n in list_internal():
            print(f"  {n}")
        return 0

    if args.cmd == "avenues":
        for aid in avenue_ids():
            a = AVENUES[aid]
            print(f"  [{aid:12s}] {a['name']:38s} accent={a['accent']} cta={a['primary_cta']!r}")
        return 0

    if args.cmd == "render":
        vars = _vars_from_args(args)
        try:
            html, text = render(args.template, vars)
        except KeyError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1

        subject = render_subject(args.template, vars)

        if args.format in ("html", "both"):
            if args.out:
                with open(args.out, "w") as f:
                    f.write(f"<!-- subject: {subject} -->\n{html}")
                print(f"wrote {args.out}")
            else:
                print(f"<!-- subject: {subject} -->")
                print(html)

        if args.format in ("text", "both"):
            if args.out_text:
                with open(args.out_text, "w") as f:
                    f.write(f"Subject: {subject}\n\n{text}")
                print(f"wrote {args.out_text}")
            elif args.format == "text":
                print(f"Subject: {subject}\n")
                print(text)
            else:
                # "both" + no out_text → also dump text to stderr so user sees it
                print(f"\n--- plain text (subject: {subject}) ---", file=sys.stderr)
                print(text, file=sys.stderr)

        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())