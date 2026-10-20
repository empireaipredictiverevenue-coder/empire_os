#!/usr/bin/env python3
"""Read-only Commercial Exchange checkout, fulfilment and recurring-revenue gate.

Reads bounded existing canonical snapshot. Emits no contacts or secrets.
Does not perform checkout, payment, allocation, API delivery or CRM mutation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.exchange_self_serve_fulfilment_review_v1 import (
    build_exchange_self_serve_fulfilment_review,
)
from empire_os.exchange_seat_renewal_lifecycle_v1 import (
    review_exchange_seat_renewal_lifecycle,
)

DEFAULT = Path("/srv/empire_os/runtime/commercial_exchange/latest.json")

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only",action="store_true",required=True)
    parser.add_argument("--snapshot",type=Path,default=DEFAULT)
    parser.add_argument("--a2a-owner-queue",type=Path,default=None)
    parser.add_argument("--private-renewal-cycles-file",type=Path,default=None)
    args=parser.parse_args()
    p=args.snapshot
    try:
        if not p.is_file() or p.is_symlink() or p.stat().st_size>5_000_000:
            raise ValueError("untrusted_or_missing_snapshot_file")
        snapshot=json.loads(p.read_text(encoding="utf-8"))
        a2a=None
        if args.a2a_owner_queue is not None:
            q=args.a2a_owner_queue
            if not q.is_file() or q.is_symlink() or q.stat().st_size>1_000_000:
                raise ValueError("untrusted_a2a_owner_queue")
            a2a=json.loads(q.read_text(encoding="utf-8"))
        value=build_exchange_self_serve_fulfilment_review(snapshot,a2a_owner_queue=a2a)
        value["private_renewal_review"]={
            "state":"NO_AUTHENTICATED_RENEWAL_OWNER_SOURCE_ATTACHED",
            "actual_entitlements_verified":0,
            "recognized_mrr_cents":0,
        }
        if args.private_renewal_cycles_file is not None:
            f=args.private_renewal_cycles_file
            if (not f.is_file() or f.is_symlink() or f.stat().st_size>1_000_000
                    or f.stat().st_mode & 0o077):
                raise ValueError("missing_or_unprotected_private_renewal_file")
            ledger=json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(ledger,dict) or set(ledger)!={"membership","periods"}:
                raise ValueError("untrusted_renewal_ledger_shape")
            value["private_renewal_review"]=review_exchange_seat_renewal_lifecycle(
                ledger["membership"],ledger["periods"],
            )
    except (ValueError, OSError, UnicodeError, TypeError):
        value={
            "schema_version":"empire.exchange.self_serve_fulfilment_mrr_review.v1",
            "state":"HOLD",
            "reason":"missing_or_invalid_canonical_snapshot",
            "subscription_activation_authorized":False,
            "lead_delivery_authorized":False,
            "recognized_mrr_cents":0,
            "external_messages_sent":0,
            "database_writes":False,
        }
    print(json.dumps(value,sort_keys=True))
    return 0 if value.get("state")=="OPERATOR_REVIEW_ONLY" else 2

if __name__=="__main__":
    raise SystemExit(main())
