"""
Empire OS v3 — USASpending.gov lead source (REAL, no key)
========================================================
Federal contract awards = companies winning gov money.
Hot B2B leads across every niche (free, no key, JSON API, POST).

VERIFY-GATE: probe() posts one award search, expects >=1 result.
"""
import time
from empire_os.lead_sources.models import LeadCandidate, SourceInfo

NICHE_KEYWORDS = ["roofing", "hvac", "plumbing", "solar", "construction",
                  "electric", "landscaping", "cleaning", "it services"]

API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
# field names MUST be Contract Award display labels (see USASpending API docs)
FIELDS = ["Recipient Name", "Award Amount", "Recipient State Code",
          "Recipient City", "Description", "Award ID"]

def _post(keyword, limit=50):
    import requests
    ua = {"User-Agent": "Mozilla/5.0 (EmpireOS-Crawler/1.0)"}
    payload = {
        "filters": {
            "keywords": [keyword],
            "award_type_codes": ["A", "B", "C", "D"],
            "time_period": [{"start_date": "2025-01-01", "end_date": "2026-12-31"}],
        },
        "fields": FIELDS,
        "limit": limit,
        "page": 1,
        "sort": "Award Amount",
        "order": "desc",
    }
    r = requests.post(API, json=payload, headers=ua, timeout=30)
    r.raise_for_status()
    return r.json()

def run(metro=None, limit=200):
    out = []
    per = max(5, limit // len(NICHE_KEYWORDS))
    for kw in NICHE_KEYWORDS:
        try:
            data = _post(kw, per)
        except Exception:
            continue
        for row in data.get("results", []):
            name = (row.get("Recipient Name") or "").strip()
            if not name:
                continue
            amt = row.get("Award Amount") or 0
            out.append(LeadCandidate(
                name=name,
                niche=kw,
                metro=(row.get("Recipient City") or ""),
                state=(row.get("Recipient State Code") or ""),
                details=f"Fed contract ${amt} — {(row.get('Description') or '')[:80]}",
                source="usaspending",
                lead_score=60,
            ))
        time.sleep(1)
    return out

def _probe():
    try:
        data = _post("construction", 1)
        return len(data.get("results", [])) >= 1
    except Exception:
        return False

def register_source(reg):
    reg(SourceInfo(
        name="usaspending",
        tier="real",
        requires=[],
        description="USASpending federal contract awards — fundable businesses, free, no key",
        run_fn=run,
        probe=_probe,
    ))
