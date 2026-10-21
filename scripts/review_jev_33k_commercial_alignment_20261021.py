"""Jev executive commercial alignment for the historical ~33k reservoir.

Composes ONLY existing read-only signal/Buyer Scout/CRM aggregate readers.
Does not open the prospects table, identify contacts, infer buying intent,
send email, allocate leads, insert CRM rows, spend funds, or approve reuse.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

from empire_os.jev_commercial_action_readiness import review_portfolio_commercial_readiness
from empire_os.jev_commercial_signal_portfolio import review_existing_intent_signals
from scripts.review_jev_commercial_action_readiness_20261021 import _safe_source
from scripts.review_jev_prospect_reservoir_20261021 import review_current_reservoir

OUTPUT="JEV_EXECUTIVE_32899_PROSPECT_COMMERCIAL_ALIGNMENT_20261021.json"


def compose_commercial_reservoir(*,as_of:datetime)->dict:
    signals=_safe_source("signals")
    if signals is None:
        raise ValueError("canonical pre-identity source not available")
    candidates=review_existing_intent_signals(signals)
    reservoir=review_current_reservoir(as_of=as_of)
    return review_portfolio_commercial_readiness(
        candidates,
        buyer_capacity=_safe_source("capacity"),
        relationships=_safe_source("relationships"),
        prospect_reservoir=reservoir,
        as_of=as_of,
    )


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true",required=True)
    args=parser.parse_args()
    output=Path(__file__).resolve().parents[1]/"docs/commercial"/OUTPUT
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("read-only historical reservoir packet already exists")
    r=compose_commercial_reservoir(as_of=datetime.now(timezone.utc))
    with output.open("x",encoding="utf-8") as dest:
        json.dump(r,dest,sort_keys=True,indent=2)
        dest.write("\n")
    print(json.dumps({
        "status":r["status"],
        "historic_prospect_reservoir":r["prospect_reservoir_review"]["historical_canonical_prospect_count"],
        "portfolio_intent_signals":r["source_signal_review_count"],
        "owner_tasks":len(r["review_steps"]),
        "buyer_capacity_status":r["buyer_capacity_status"],
        "contactable_lead_total_verified":r["prospect_reservoir_review"]["contactable_qualified_leads_verified"],
        "outbound":r["outreach_sent"],
    },sort_keys=True))


if __name__=="__main__":
    main()
