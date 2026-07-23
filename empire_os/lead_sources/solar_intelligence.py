#!/usr/bin/env python3
"""
Solar Incentives & Installers — Free Data Sources
==================================================
- NREL PVWatts (solar potential by location)
- DSIRE (Database of State Incentives for Renewables & Efficiency)
- State solar license boards
- IRS tax credit data (ITC)
"""

import json, time, urllib.request, urllib.parse
from typing import Iterator, Optional, List
from empire_os.lead_sources.models import LeadCandidate, SourceInfo
from empire_os.lead_sources.utils import infer_niche


# ──────────────────────────────────────────────────────────────────────
# NREL PVWatts API — Solar potential by address/lat-lon
# ──────────────────────────────────────────────────────────────────────
NREL_API = "https://developer.nrel.gov/api/pvwatts/v6.json"
NREL_KEY = "DEMO_KEY"  # Replace with your free NREL API key

def pvwatts_potential(lat: float, lon: float, system_kw: float = 5.0) -> dict:
    """Get solar production estimate for a location."""
    params = {
        "api_key": NREL_KEY,
        "lat": lat,
        "lon": lon,
        "system_capacity": system_kw,
        "azimuth": 180,
        "tilt": 20,
        "array_type": 1,
        "module_type": 0,
        "losses": 14,
        "timeframe": "hourly",
    }
    url = f"{NREL_API}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"[solar] NREL error: {e}")
        return {}


# ──────────────────────────────────────────────────────────────────────
# DSIRE — State incentives database
# ──────────────────────────────────────────────────────────────────────
DSIRE_API = "https://programs.dsireusa.org/api/v1/programs"

def dsire_incentives(state: str, technology: str = "Solar Photovoltaics") -> List[dict]:
    """Get state-level solar incentives from DSIRE."""
    params = {
        "state": state.upper(),
        "technology": technology,
        "implementing_sector": "Residential",
    }
    url = f"{DSIRE_API}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read().decode()).get("data", [])
    except Exception as e:
        print(f"[solar] DSIRE error: {e}")
        return []


# ──────────────────────────────────────────────────────────────────────
# State Solar License Boards (contractor verification)
# ──────────────────────────────────────────────────────────────────────
STATE_SOLAR_LICENSE = {
    "CA": "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx",
    "TX": "https://www.tdlr.texas.gov/licensedata/",
    "FL": "https://www.myfloridalicense.com/VerifyLicense/",
    "AZ": "https://roc.az.gov/contractor-search",
    "NV": "https://www.nvcontractorsboard.com/verify-license",
    "CO": "https://dora.colorado.gov/licensing/lookup",
    "NY": "https://www.dos.ny.gov/licensing/lookup",
    "NJ": "https://www.njconsumeraffairs.gov/licensing/Pages/License-Verification.aspx",
}

def verify_solar_license(state: str, license_num: str) -> dict:
    """Check if a solar contractor holds valid state license."""
    # Placeholder - each state has different portal
    return {"state": state, "license": license_num, "verified": False, "note": "Manual check needed"}


# ──────────────────────────────────────────────────────────────────────
# IRS ITC (Investment Tax Credit) — Federal incentive
# ──────────────────────────────────────────────────────────────────────
ITC_RATE = 0.30  # 30% through 2032

def itc_value(system_cost: float) -> float:
    """Federal tax credit amount for solar system."""
    return round(system_cost * ITC_RATE, 2)


# ──────────────────────────────────────────────────────────────────────
# Lead Source Runner
# ──────────────────────────────────────────────────────────────────────
METRO_COORDS = {
    "LAX": (34.0522, -118.2437),
    "DFW": (32.7767, -96.7970),
    "HOU": (29.7604, -95.3698),
    "ATL": (33.7490, -84.3880),
    "MIA": (25.7617, -80.1918),
    "PHX": (33.4484, -112.0740),
    "NYC": (40.7128, -74.0060),
    "CHI": (41.8781, -87.6298),
    "SEA": (47.6062, -122.3321),
    "DEN": (39.7392, -104.9903),
}

STATE_MAP = {
    "LAX": "CA", "DFW": "TX", "HOU": "TX", "ATL": "GA",
    "MIA": "FL", "PHX": "AZ", "NYC": "NY", "CHI": "IL",
    "SEA": "WA", "DEN": "CO",
}

def run(metro: Optional[str] = None, niches: Optional[List[str]] = None, limit: int = 40) -> Iterator[LeadCandidate]:
    """
    Yield solar leads for a metro.
    Niches: solar, solar_installer, battery_storage, ev_charging
    """
    if niches and not any(n in ("solar", "solar_installer", "battery_storage", "ev_charging") for n in niches):
        return
    
    metros = [metro] if metro and metro in METRO_COORDS else list(METRO_COORDS.keys())
    
    for m in metros:
        lat, lon = METRO_COORDS[m]
        state = STATE_MAP.get(m, "")
        
        # 1. Solar potential for the metro center
        pv = pvwatts_potential(lat, lon, system_kw=7.0)
        annual_kwh = pv.get("outputs", {}).get("ac_annual", 0)
        
        # 2. State incentives
        incentives = dsire_incentives(state) if state else []
        
        # 3. Generate lead candidate (metro-level market intelligence)
        yield LeadCandidate(
            name=f"{m} Solar Market Intelligence",
            email="",
            phone="",
            niche="solar",
            metro=m,
            state=state,
            details=(
                f"Metro solar potential: {annual_kwh:,.0f} kWh/yr (7kW system). "
                f"Federal ITC: 30%. "
                f"State incentives: {len(incentives)} programs. "
                f"Key programs: {', '.join([i.get('program_name', '')[:30] for i in incentives[:3]])}"
            ),
            source="solar_intelligence",
            lead_score=70,
            url=f"https://pvwatts.nrel.gov/",
            raw={
                "metro": m,
                "lat": lat,
                "lon": lon,
                "annual_kwh": annual_kwh,
                "incentives_count": len(incentives),
                "incentives": [{"name": i.get("program_name"), "type": i.get("program_type")} for i in incentives[:5]],
            },
        )
        
        time.sleep(0.5)  # rate limit NREL


def register_source(reg):
    reg(SourceInfo(
        name="solar_intelligence",
        tier="real",
        requires=[],
        description="NREL PVWatts + DSIRE incentives + state license boards — solar market intelligence per metro",
        run_fn=run,
    ))


if __name__ == "__main__":
    for lead in run(metro="DFW", niches=["solar"], limit=1):
        print(f"{lead.name} | {lead.niche} | {lead.metro} | {lead.lead_score}")
        print(f"  {lead.details[:120]}")
        print()