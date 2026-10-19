"""Private cross-vertical source observations vs canonical Exchange.

Reads already-created local aggregate receipts from RECC and CMS NPPES,
never raw business names or medical records. Holds unknown schemas/claims.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

from empire_os.lead_exchange_live_inventory import build_lead_exchange_live_inventory
from empire_os.official_vertical_source_packs import SOURCES


def _read(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > 5_000_000:
        raise ValueError("source_snapshot_missing_or_unbounded")
    d = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(d, dict):
        raise ValueError("source_snapshot_invalid")
    return d


def build_coverage(exchange: dict, recc: dict, nppes: dict, nyc: dict | None = None) -> dict:
    core = build_lead_exchange_live_inventory(exchange)
    if core["state"] == "HOLD":
        raise ValueError("canonical_exchange_snapshot_unverified")
    if (recc.get("schema_version") != "empire.recc_solar_supply_sweep.v1"
            or recc.get("source_id") != "gb_recc_solar"
            or recc.get("state") not in ("COMPLETED", "COMPLETED_WITH_SOURCE_ERRORS")
            or recc.get("canonical_empiredb_writes") is not False
            or recc.get("outbound_authorized") is not False):
        raise ValueError("untrusted_recc_source_review")
    if (nppes.get("schema_version") != "empire.cms_nppes_dental_org_sweep.v1"
            or nppes.get("source_id") != "us_cms_nppes_dental_npi2"
            or nppes.get("state") != "COMPLETED"
            or nppes.get("canonical_empiredb_writes") is not False
            or nppes.get("outbound_authorized") is not False):
        raise ValueError("untrusted_nppes_source_review")
    solar = recc.get("unique_research_observations")
    dental = nppes.get("unique_private_organization_observations")
    if (type(solar) is not int or not 0 <= solar <= 40
            or type(dental) is not int or not 0 <= dental <= 48
            or recc.get("commercial_exchange_inventory_added") != 0
            or nppes.get("commercial_exchange_inventory_additions") != 0):
        raise ValueError("source_reports_attempted_canonical_inventory_promotion")
    contractor_count = 0
    if nyc is not None:
        if (not isinstance(nyc, dict)
                or nyc.get("schema_version") != "empire.us_nyc_home_improvement_company_pilot.v1"
                or nyc.get("source_id") != "us_nyc_dcwp_home_improvement_companies"
                or nyc.get("state") != "COMPLETED"
                or nyc.get("canonical_empiredb_writes") is not False
                or nyc.get("outbound_authorized") is not False
                or nyc.get("commercial_exchange_inventory_additions") != 0):
            raise ValueError("untrusted_nyc_contractor_source_receipt")
        contractor_count = nyc.get("corporate_business_licences_observed")
        if type(contractor_count) is not int or not 0 <= contractor_count <= 20:
            raise ValueError("invalid_nyc_source_observation_count")
    pools = [
        {"source_id": "gb_recc_solar", "market": "GB solar",
         "private_observations": solar, "canonical_additions": 0,
         "observed_at": recc["observed_at"]},
        {"source_id": "us_cms_nppes_dental_npi2", "market": "US dental organisations",
         "private_observations": dental, "canonical_additions": 0,
         "observed_at": nppes["observed_at"]},
    ]
    if nyc is not None:
        pools.append({"source_id": "us_nyc_dcwp_home_improvement_companies",
                      "market": "US NYC general home improvement companies",
                      "private_observations": contractor_count,
                      "specific_trade_verified": False,
                      "canonical_additions": 0,
                      "observed_at": nyc["observed_at"]})
    return {
        "schema_version": "empire.multivertical_source_inventory_review.v1",
        "mode": "READ_ONLY_PRIVATE_RESEARCH_AGGREGATES",
        "canonical_exchange_observed_at": core["observed_at"],
        "canonical_exchange_selected_inventory": core["selected_inventory_records"],
        "canonical_exchange_evidence_holds": core["evidence_hold_records"],
        "canonical_exchange_capacity_waitlist": core["buyer_capacity_waitlist_records"],
        "canonical_exchange_delivery_ready": 0,
        "separate_research_pools": pools,
        "source_observation_total_no_cross_source_dedup_claim": solar + dental + contractor_count,
        "official_source_packs_registered": len(SOURCES),
        "public_inventory_claim_allowed": False,
        "automatic_outreach_authorized": False,
        "canonical_empiredb_writes": False,
        "execution_authority": "none",
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--read-only", action="store_true", required=True)
    p.add_argument("--exchange", type=Path, required=True)
    p.add_argument("--recc", type=Path, required=True)
    p.add_argument("--nppes", type=Path, required=True)
    p.add_argument("--nyc", type=Path)
    opts = p.parse_args(argv)
    try:
        result = build_coverage(_read(opts.exchange), _read(opts.recc), _read(opts.nppes),
                                _read(opts.nyc) if opts.nyc else None)
    except (OSError, ValueError, TypeError, UnicodeError) as e:
        result = {
            "state": "HOLD", "reason": type(e).__name__,
            "canonical_empiredb_writes": False, "execution_authority": "none",
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("mode") == "READ_ONLY_PRIVATE_RESEARCH_AGGREGATES" else 2


if __name__ == "__main__":
    raise SystemExit(main())
