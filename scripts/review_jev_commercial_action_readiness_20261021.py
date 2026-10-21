"""Private-safe Jev executive commercial gap review.

Reads existing canonical signal, buyer-capacity and relationship snapshots
without credential, inbox, network or DB actions. Exports counts only: no
entity IDs, source posts, personal names, contact addresses or suppression
identities. Not an allowlist for any lead, buyer or outreach.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

from empire_os.jev_commercial_action_readiness import review_portfolio_commercial_readiness
from empire_os.jev_commercial_signal_portfolio import review_existing_intent_signals

ROOT=Path("/srv/empire_os")
SOURCES={
    "signals":("runtime/acquisition/signal_inbox.json",12_000_000),
    "capacity":("runtime/buyer_capacity_readiness/latest.json",250_000),
    "relationships":("runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json",1_500_000),
}
OUTPUT="JEV_COMMERCIAL_ACTION_READINESS_20261021.json"


def _safe_source(kind:str)->dict|None:
    name,bound=SOURCES[kind]
    path=ROOT/name
    try:
        if (path.is_symlink() or not path.is_file()
            or not 0<path.stat().st_size<=bound
            or not path.resolve().is_relative_to(ROOT.resolve())):
            return None
        data=json.loads(path.read_text(encoding="utf8"))
        return data if isinstance(data,dict) else None
    except (OSError,ValueError,TypeError,UnicodeError):
        return None


def current_readiness(*,as_of:datetime)->dict:
    inbox=_safe_source("signals")
    if inbox is None:
        raise ValueError("canonical signal inbox unavailable")
    portfolio=review_existing_intent_signals(inbox)
    return review_portfolio_commercial_readiness(
        portfolio,buyer_capacity=_safe_source("capacity"),
        relationships=_safe_source("relationships"),as_of=as_of)


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",required=True,action="store_true")
    args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1]
    output=repo/"docs/commercial"/OUTPUT
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError("refuse to overwrite commercial readiness report")
    report=current_readiness(as_of=datetime.now(timezone.utc))
    with output.open("x",encoding="utf8") as f:
        json.dump(report,f,sort_keys=True,indent=2)
        f.write("\n")
    print(json.dumps({
        "status":report["status"],
        "signals":report["source_signal_review_count"],
        "capacity":report["buyer_capacity_status"],
        "relationships":report["total_relationships"],
        "mailbox_current":report["mailbox_current"],
        "suppression_review_count":report["aggregate_suppression_or_bounce_review_count"],
        "outreach":report["outreach_sent"],
    },sort_keys=True))


if __name__=="__main__":
    main()
