#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from empire_os.legal_mass_tort_intelligence import legacy_mass_tort_agent_status

ROOT = Path("/srv/empire_os")
OUTPUT = ROOT / "runtime" / "legal_mass_tort" / "latest.json"

VERTICALS = (
    "camp_lejeune",
    "asbestos",
    "afff_pfas",
    "3m_earplugs",
    "roundup",
    "hernia_mesh",
    "talc",
    "hair_relaxer",
    "hormone_therapy",
    "nec_formula",
)


def main() -> int:
    source_checks = {
        "courtlistener": (
            ROOT / "empire_os/lead_sources/court_listener.py"
        ).exists(),
        "firm_sources": (
            ROOT / "empire_os/firm_sources.json"
        ).exists(),
        "search_fabric": (
            ROOT / "empire_os/search_fabric/search.py"
        ).exists(),
        "legal_industry_surface": (
            ROOT / "apps/empire-public-site/out/industries/legal-mass-tort.html"
        ).exists(),
        "intelligence_node": (
            ROOT / "empire_os/intelligence_nodes.py"
        ).exists(),
    }
    payload = {
        "schema_version": "empire.legal_mass_tort_intelligence.v1",
        "mode": "OBSERVE",
        "market": "plaintiff_law_firms_and_legal_marketing",
        "verticals": list(VERTICALS),
        "source_readiness": source_checks,
        "source_count_ready": sum(bool(v) for v in source_checks.values()),
        "source_count_total": len(source_checks),
        "consumer_targeting": False,
        "individual_health_legal_profiling": False,
        "firm_buyer_intelligence": True,
        "court_market_intelligence": True,
        "search_market_intelligence": True,
        "live_market_evidence_bound": False,
        "market_opportunities_observed": None,
        "legacy_agent": legacy_mass_tort_agent_status(),
        "execution_authority": "none",
        "outreach_authority": "none",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(OUTPUT)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
