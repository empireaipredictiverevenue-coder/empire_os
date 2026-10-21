"""Jev executive inventory audit: historical 33k EmpireDB reservoir + current lanes.

Snapshot-only read, bounded aggregate output. No DB connection, original
contact fields, CRM mutation, email, bulk model inference or activation.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from empire_os.jev_prospect_reservoir_review import audit_jev_prospect_reservoir

ROOT=Path("/srv/empire_os")
INPUTS={
    "verified":("runtime/data_cloud/shadow_independent_verify_latest.json",100000),
    "dual":("runtime/data_cloud/dual_read_compare_latest.json",100000),
    "leads":("runtime/leads_control/leads_runtime_observer_latest.json",100000),
    "permits":("runtime/recovery/legacy_permit_inventory_summary.json",100000),
    "markets":("runtime/market_sweeps/revenue_gps_latest.json",250000),
}
OUTPUT="JEV_PROSPECT_32899_RESERVOIR_TRUTH_20261021.json"


def _snapshot(name:str)->dict|None:
    relative,limit=INPUTS[name]
    file=ROOT/relative
    try:
        if (file.is_symlink() or not file.is_file()
            or not 0<file.stat().st_size<=limit
            or not file.resolve().is_relative_to(ROOT.resolve())):
            return None
        row=json.loads(file.read_text(encoding="utf8"))
        return row if isinstance(row,dict) else None
    except (OSError,ValueError,UnicodeError,TypeError):
        return None


def review_current_reservoir(*,as_of:datetime)->dict:
    earlier=_snapshot("verified")
    pair=_snapshot("dual")
    if earlier is None or pair is None:
        raise ValueError("historically verified canonical source references unavailable")
    return audit_jev_prospect_reservoir(
        historic_verified=earlier,historic_dual_read=pair,
        leads_runtime=_snapshot("leads"),legacy_permit=_snapshot("permits"),
        current_markets=_snapshot("markets"),as_of=as_of)


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true",required=True)
    args=parser.parse_args()
    dest=Path(__file__).resolve().parents[1]/"docs/commercial"/OUTPUT
    if dest.exists() or dest.is_symlink() or not dest.parent.is_dir():
        raise ValueError("refuse replace original Jev reservoir audit")
    result=review_current_reservoir(as_of=datetime.now(timezone.utc))
    result["snapshot_audited_at_utc"]=datetime.now(timezone.utc).isoformat()
    with dest.open("x",encoding="utf8") as out:
        json.dump(result,out,sort_keys=True,indent=2)
        out.write("\n")
    print(json.dumps({
        "status":result["status"],
        "historic_prospects":result["historical_empiredb_prospect_count"],
        "current_empiredb_count":result["current_empiredb_prospect_count"],
        "current_lead_control":result["existing_leads_control_rows"],
        "local_permit_inventory":result["permit_recovery_local_rows"],
        "recent_market_window":result["recent_market_observed_acquisition_total"],
        "bulk_contactable_total_verified":result["bulk_qualified_or_contactable_lead_total_proven"],
        "outreach":result["automatic_outreach_authorized"],
    },sort_keys=True))


if __name__=="__main__":
    main()
