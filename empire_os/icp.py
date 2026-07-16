"""
Empire OS — Ideal Customer Profile (ICP) Engine

Scoring engine that matches leads against defined ICP profiles across all
avenues (leadgen, paypercall, saas, loans). Each ICP is a weighted criteria
map. Leads are scored 0–100 against each profile and assigned a tier
(A: perfect, B: strong, C: partial, D: weak, E: mismatch).

Key functions:
  score_lead_vs_icp(lead, profile) → dict
  find_best_icp(lead) → str
  get_icp_analytics(backend) → dict
  suggest_icp_from_leads(backend, niche=None) → dict
"""

import logging
from typing import Any

logger = logging.getLogger("empire-icp")

# ── Default ICP Profiles ────────────────────────────────────────────
# Each ICP profile has:
#   id:         short unique key
#   name:       human-readable label
#   avenue:     which business avenue (leadgen, paypercall, saas, loans)
#   description: what this segment looks like
#   criteria:   list of {field, op, value, weight, label}
#               op: one of eq, neq, gt, gte, lt, lte, in, not_in,
#                   has_any, has_all, regex, truthy, falsy, exists
#   icon:       emoji for display

DEFAULT_ICP_PROFILES = [
    # ── LEADGEN: Homeowner → Contractor ──────────────────────────
    {
        "id": "roofing_pro",
        "name": "Roofing Pro — Ready to Buy",
        "avenue": "leadgen",
        "niche_filter": ["roof_repair", "residential_roofing", "roofing"],
        "description": "Licensed, established roofing contractor actively seeking work. High-intent buyer.",
        "icon": "🏠",
        "criteria": [
            {"field": "omega_score", "op": "gte", "value": 0.7, "weight": 25, "label": "Omega Score ≥ 0.7"},
            {"field": "license_no", "op": "exists", "weight": 20, "label": "Has License"},
            {"field": "website", "op": "truthy", "weight": 15, "label": "Has Website"},
            {"field": "employee_count", "op": "gte", "value": 2, "weight": 10, "label": "≥2 Employees"},
            {"field": "bbb_rating", "op": "in", "value": ["A+", "A", "A-", "B+"], "weight": 10, "label": "BBB A- or Better"},
            {"field": "year_founded", "op": "lte", "value": 2023, "weight": 5, "label": "Founded ≤2023"},
            {"field": "phone", "op": "truthy", "weight": 5, "label": "Has Phone"},
            {"field": "email", "op": "truthy", "weight": 5, "label": "Has Email"},
            {"field": "revenue_est", "op": "gte", "value": 100000, "weight": 5, "label": "Revenue ≥$100k"},
        ],
    },
    {
        "id": "growing_roofer",
        "name": "Growing Roofer — Expansion Stage",
        "avenue": "leadgen",
        "niche_filter": ["roof_repair", "residential_roofing"],
        "description": "Small to mid roofing company scaling up. Multiple estimators, expanding service area.",
        "icon": "📈",
        "criteria": [
            {"field": "omega_score", "op": "gte", "value": 0.5, "weight": 20, "label": "Omega ≥ 0.5"},
            {"field": "website", "op": "truthy", "weight": 15, "label": "Has Website"},
            {"field": "employee_count", "op": "gte", "value": 5, "weight": 15, "label": "≥5 Employees"},
            {"field": "revenue_est", "op": "gte", "value": 250000, "weight": 15, "label": "Revenue ≥$250k"},
            {"field": "year_founded", "op": "lte", "value": 2020, "weight": 10, "label": "Established ≥5yr"},
            {"field": "phone", "op": "truthy", "weight": 10, "label": "Has Phone"},
            {"field": "niche", "op": "in", "value": ["roof_repair", "residential_roofing"], "weight": 10, "label": "Repair + Residential"},
            {"field": "social_links", "op": "has_any", "value": ["linkedin", "facebook"], "weight": 5, "label": "Social Presence"},
        ],
    },
    # ── PAY PER CALL ─────────────────────────────────────────────
    {
        "id": "high_value_homeowner",
        "name": "High-Value Homeowner — Urgent Need",
        "avenue": "paypercall",
        "niche_filter": [],
        "description": "Homeowner with urgent roofing/repair need, high property value, ready to pay for call referral.",
        "icon": "📞",
        "criteria": [
            {"field": "niche", "op": "in", "value": ["roof_repair", "residential_roofing"], "weight": 20, "label": "Repair/Residential Niche"},
            {"field": "omega_score", "op": "gte", "value": 0.6, "weight": 20, "label": "Omega ≥ 0.6"},
            {"field": "phone", "op": "truthy", "weight": 20, "label": "Has Phone (callable)"},
            {"field": "website", "op": "truthy", "weight": 10, "label": "Has Website"},
            {"field": "email", "op": "truthy", "weight": 10, "label": "Has Email"},
            {"field": "city", "op": "exists", "weight": 10, "label": "Location Known"},
            {"field": "state", "op": "exists", "weight": 5, "label": "State Known"},
            {"field": "license_no", "op": "exists", "weight": 5, "label": "Has License"},
        ],
    },
    # ── SAAS ─────────────────────────────────────────────────────
    {
        "id": "saas_ready",
        "name": "SaaS-Ready Contractor",
        "avenue": "saas",
        "niche_filter": ["roof_repair", "residential_roofing", "roofing"],
        "description": "Modern contractor who would adopt SaaS tools — has digital presence, growing, tech-aware.",
        "icon": "☁️",
        "criteria": [
            {"field": "website", "op": "truthy", "weight": 25, "label": "Digital Presence"},
            {"field": "email", "op": "truthy", "weight": 20, "label": "Has Email"},
            {"field": "employee_count", "op": "gte", "value": 3, "weight": 15, "label": "≥3 Employees"},
            {"field": "revenue_est", "op": "gte", "value": 200000, "weight": 15, "label": "Revenue ≥$200k"},
            {"field": "omega_score", "op": "gte", "value": 0.4, "weight": 10, "label": "Omega ≥ 0.4"},
            {"field": "social_links", "op": "has_any", "value": ["linkedin"], "weight": 10, "label": "LinkedIn"},
            {"field": "year_founded", "op": "lte", "value": 2022, "weight": 5, "label": "Founded ≤2022"},
        ],
    },
    {
        "id": "premium_leads_buyer",
        "name": "Premium Leads Buyer",
        "avenue": "paypercall",
        "niche_filter": [],
        "description": "High-intent buyer willing to pay premium for qualified homeowner leads.",
        "icon": "💰",
        "criteria": [
            {"field": "omega_score", "op": "gte", "value": 0.8, "weight": 30, "label": "Omega ≥ 0.8 (Premium)"},
            {"field": "license_no", "op": "exists", "weight": 20, "label": "Licensed"},
            {"field": "website", "op": "truthy", "weight": 15, "label": "Professional Presence"},
            {"field": "employee_count", "op": "gte", "value": 5, "weight": 15, "label": "≥5 Employees"},
            {"field": "bbb_rating", "op": "in", "value": ["A+", "A", "A-"], "weight": 10, "label": "BBB A or Better"},
            {"field": "phone", "op": "truthy", "weight": 5, "label": "Phone Available"},
            {"field": "email", "op": "truthy", "weight": 5, "label": "Email Available"},
        ],
    },
]


# ── Scoring ─────────────────────────────────────────────────────────

def _apply_criterion(lead: dict, criterion: dict) -> bool:
    """Check a single criterion against a lead's fields."""
    field = criterion["field"]
    op = criterion["op"]
    value = criterion.get("value")
    actual = lead.get(field)

    # Normalise missing to None
    if actual is None and op not in ("exists", "truthy", "falsy", "not_in", "neq"):
        return False

    try:
        if op == "eq":
            return str(actual) == str(value)
        elif op == "neq":
            return str(actual) != str(value)
        elif op == "gt":
            return float(actual) > float(value)
        elif op == "gte":
            return float(actual) >= float(value)
        elif op == "lt":
            return float(actual) < float(value)
        elif op == "lte":
            return float(actual) <= float(value)
        elif op == "in":
            return str(actual) in [str(v) for v in value]
        elif op == "not_in":
            return str(actual) not in [str(v) for v in value]
        elif op == "has_any":
            # actual is assumed to be a list (e.g., social_links)
            if not isinstance(actual, (list, str)):
                return False
            if isinstance(actual, str):
                import json
                try:
                    actual = json.loads(actual)
                except Exception:
                    actual = [actual]
            return any(str(v).lower().find(str(k).lower()) >= 0 for k in value for v in actual)
        elif op == "has_all":
            return all(
                str(k).lower() in str(actual).lower()
                for k in value
            )
        elif op == "regex":
            import re
            return bool(re.search(str(value), str(actual or "")))
        elif op == "truthy":
            return bool(actual)
        elif op == "falsy":
            return not bool(actual)
        elif op == "exists":
            return actual is not None and str(actual).strip() != ""
        else:
            return False
    except (ValueError, TypeError) as e:
        logger.debug("Criterion eval error: field=%s op=%s val=%s actual=%s err=%s", field, op, value, actual, e)
        return False


def score_lead_vs_icp(lead: dict, profile: dict) -> dict:
    """Score a single lead against one ICP profile.

    Returns: {
        "profile_id": str,
        "profile_name": str,
        "score": float,          # 0–100
        "tier": str,             # A / B / C / D / E
        "matched_criteria": [{field, label, weight, matched}],
        "total_weight": float,
        "earned_weight": float,
    }
    """
    criteria = profile.get("criteria", [])
    total_weight = sum(c.get("weight", 0) for c in criteria)
    earned = 0.0
    matched = []

    for c in criteria:
        ok = _apply_criterion(lead, c)
        if ok:
            earned += c.get("weight", 0)
        matched.append({
            "field": c["field"],
            "label": c.get("label", c["field"]),
            "weight": c.get("weight", 0),
            "matched": ok,
        })

    score = round((earned / total_weight * 100) if total_weight > 0 else 0, 1)
    if score >= 80:
        tier = "A"
    elif score >= 60:
        tier = "B"
    elif score >= 40:
        tier = "C"
    elif score >= 20:
        tier = "D"
    else:
        tier = "E"

    return {
        "profile_id": profile.get("id"),
        "profile_name": profile.get("name"),
        "score": score,
        "tier": tier,
        "matched_criteria": matched,
        "total_weight": total_weight,
        "earned_weight": earned,
    }


def find_best_icp(lead: dict, profiles: list[dict | None] = None) -> dict:
    """Score lead against all profiles and return best match + all scores.

    Returns: {
        "best": profile_result,   # highest score
        "scores": [profile_result, ...],
        "icp_fit_score": float,   # 0–100 best score for CRM display
        "icp_tier": str,
        "icp_name": str,
    }
    """
    if profiles is None:
        profiles = DEFAULT_ICP_PROFILES

    # Filter profiles by lead's niche
    lead_niche = (lead.get("niche") or "").lower()
    relevant = [
        p for p in profiles
        if not p.get("niche_filter") or lead_niche in p["niche_filter"]
    ]
    if not relevant:
        relevant = profiles  # fall back to all

    scores = [score_lead_vs_icp(lead, p) for p in relevant]
    scores.sort(key=lambda s: s["score"], reverse=True)
    best = scores[0] if scores else {"score": 0, "tier": "E", "profile_name": "No Match"}

    return {
        "best": best,
        "all_scores": scores,
        "icp_fit_score": best["score"],
        "icp_tier": best["tier"],
        "icp_name": best["profile_name"],
    }


# ── Analytics ───────────────────────────────────────────────────────

def get_icp_analytics(backend, limit: int = 1000) -> dict:
    """Aggregate ICP fit stats across all CRM leads.

    Returns: {
        "total_scored": int,
        "profile_breakdown": {profile_id: {tier_A, tier_B, ...}},
        "tier_breakdown": {A: N, B: N, ...},
        "top_icp_matches": [
            {lead_id, business_name, niche, icp_name, icp_fit_score, icp_tier},
        ],
        "average_fit": float,
    }
    """
    rows = backend.execute(
        "SELECT id, business_name, contact_name, niche, omega_score, "
        "license_no, website, phone, email, employee_count, revenue_est, "
        "year_founded, bbb_rating, city, state, social_links, "
        "enrichment_score, status "
        "FROM crm_leads LIMIT ?", (limit,)
    ).fetchall()

    tier_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}
    profile_map = {}
    top_matches = []
    total_score = 0.0

    for r in rows:
        lead = dict(r)
        result = find_best_icp(lead)
        best = result["best"]
        total_score += best["score"]
        tier_counts[best["tier"]] = tier_counts.get(best["tier"], 0) + 1

        pid = best.get("profile_id", "unknown")
        if pid not in profile_map:
            profile_map[pid] = {"profile_name": best["profile_name"], **{t: 0 for t in "ABCDE"}}
        profile_map[pid][best["tier"]] = profile_map[pid].get(best["tier"], 0) + 1

        if best["score"] >= 60:
            top_matches.append({
                "lead_id": r["id"],
                "business_name": r.get("business_name") or r.get("contact_name") or f"Lead #{r['id']}",
                "niche": r.get("niche"),
                "icp_name": best["profile_name"],
                "icp_fit_score": best["score"],
                "icp_tier": best["tier"],
            })

    top_matches.sort(key=lambda x: x["icp_fit_score"], reverse=True)

    return {
        "total_scored": len(rows),
        "tier_breakdown": tier_counts,
        "profile_breakdown": profile_map,
        "top_icp_matches": top_matches[:50],
        "average_fit": round(total_score / max(len(rows), 1), 1),
    }


def update_lead_icp_score(backend, lead_id: int) -> dict:
    """Score a single lead against all ICPs and store result in crm_leads.

    Returns {icp_fit_score, icp_tier, icp_name}.
    """
    row = backend.execute(
        "SELECT * FROM crm_leads WHERE id = ?", (lead_id,)
    ).fetchone()
    if not row:
        raise ValueError(f"Lead {lead_id} not found")

    lead = dict(row)
    result = find_best_icp(lead)
    fit = result["best"]["score"]
    tier = result["best"]["tier"]
    name = result["best"]["profile_name"]

    backend.execute(
        "UPDATE crm_leads SET icp_fit_score = ?, icp_tier = ?, icp_name = ? WHERE id = ?",
        (fit, tier, name, lead_id),
    )
    backend.conn.commit()
    return {"icp_fit_score": fit, "icp_tier": tier, "icp_name": name}


def batch_update_icp_scores(backend, limit: int = 500) -> dict:
    """Score all un-scored leads and update crm_leads (targets NULL or default E)."""
    rows = backend.execute(
        "SELECT id FROM crm_leads WHERE icp_fit_score IS NULL OR (icp_fit_score = 0 AND icp_tier = 'E') LIMIT ?",
        (limit,),
    ).fetchall()
    updated = 0
    for r in rows:
        try:
            update_lead_icp_score(backend, r["id"])
            updated += 1
        except Exception as e:
            logger.error("ICP score lead %s failed: %s", r["id"], e)
    return {"updated": updated}


def score_lead_by_icp(backend, lead_id: int) -> dict:
    """Score a lead and return detailed ICP breakdown."""
    row = backend.execute(
        "SELECT * FROM crm_leads WHERE id = ?", (lead_id,)
    ).fetchone()
    if not row:
        raise ValueError(f"Lead {lead_id} not found")

    lead = dict(row)
    result = find_best_icp(lead)
    return result


# ── Schema ──────────────────────────────────────────────────────────

def ensure_icp_schema(backend):
    """Add ICP columns if missing."""
    existing = [r["name"] for r in backend.execute("PRAGMA table_info(crm_leads)").fetchall()]
    for col, dtype in [
        ("icp_fit_score", "REAL DEFAULT 0"),
        ("icp_tier", "TEXT DEFAULT 'E'"),
        ("icp_name", "TEXT DEFAULT ''"),
    ]:
        if col not in existing:
            backend.execute(f"ALTER TABLE crm_leads ADD COLUMN {col} {dtype}")
    backend.conn.commit()
