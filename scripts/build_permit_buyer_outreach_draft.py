#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.permit_buyer_outreach_draft import (
    build_permit_buyer_outreach_draft,
    write_permit_buyer_outreach_draft,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--founder-name", default="Phil")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    domain = str(args.domain).strip().lower()
    packet_path = (
        root
        / "runtime/revenue/permit_buyer_packets"
        / f"{domain}.json"
    )
    packet = json.loads(packet_path.read_text(encoding="utf-8"))

    draft = build_permit_buyer_outreach_draft(
        packet,
        founder_name=args.founder_name,
    )
    output = write_permit_buyer_outreach_draft(root, draft)

    print(json.dumps({
        "ok": True,
        "output": str(output),
        "business_name": draft["business_name"],
        "recipient_email": draft["recipient_route"]["email"],
        "attention": draft["recipient_route"]["attention"],
        "send_gate_ready": draft["send_gate_ready"],
        "send_gate_blockers": draft["send_gate_blockers"],
        "live_outbound_send": draft["live_outbound_send"],
        "terms_accepted": draft["terms_accepted"],
        "actual_revenue": draft["actual_revenue"],
        "execution_authority": draft["execution_authority"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
