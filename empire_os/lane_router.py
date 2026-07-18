"""Lead routing engine — matches prospects to the correct lane.

Uses keyword scoring against the multi-niche with sub-niches structure.
Each sub-niche has weighted keyword patterns; the engine picks the best match.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from empire_os.lanes import CATEGORIES, METROS, all_sub_niches, state_to_metros, STATE_METRO

logger = logging.getLogger("lane-router")

# ── Keyword matching library ────────────────────────────────────────
# Keywords per niche category. Returned as a dict of sub_niche → match tokens.

MATCH_KEYWORDS = {
    # ── Mass Torts ──
    "camp_lejeune": [
        "camp lejeune", "marine corps", "lejeune water", "camp lejeune cancer",
        "toxic water", "marine base", "lejeune lawsuit",
    ],
    "roundup": [
        "roundup", "glyphosate", "monsanto", "weed killer", "roundup cancer",
        "roundup lymphoma", "non-hodgkin", "weedkiller",
    ],
    "paraquat": [
        "paraquat", "gramoxone", "herbicide parkinson", "paraquat parkinson",
        "paraquat lawsuit", "paraquat exposure",
    ],
    "afff": [
        "afff", "firefighting foam", "pfas", "forever chemicals", "aqueous film",
        "firefighter cancer", "military firefighting foam", "pfas cancer",
    ],
    "zantac": [
        "zantac", "ranitidine", "heartburn cancer", "ndma", "zantac cancer",
        "ranitidine cancer", "zantac lawsuit",
    ],
    "ozempic": [
        "ozempic", "mounjaro", "wegovy", "semaglutide", "tirzepatide",
        "glp-1 stomach paralysis", "glp-1 lawsuit", "gastroparesis ozempic",
        "ozempic gallbladder", "weight loss drug lawsuit",
    ],
    # ── Home Services ──
    "electrical": [
        "electrician", "electrical repair", "wiring", "electrical contractor",
        "circuit breaker", "panel upgrade", "electrical service",
    ],
    "hvac": [
        "hvac", "air conditioning", "furnace", "heating and cooling",
        "ac repair", "ac installation", "heat pump", "thermostat",
    ],
    "plumbing": [
        "plumber", "plumbing repair", "drain", "water heater", "pipe leak",
        "sewer line", "toilet repair", "faucet",
    ],
    "residential_roofing": [
        "roofing", "roof", "roofer", "roof repair", "shingles", "roof leak",
        "roof replacement", "roofing contractor", "residential roofing",
        "new roof", "roof estimate",
    ],
    "commercial_roofing": [
        "commercial roofing", "flat roof", "tpo roofing", "metal roof commercial",
        "warehouse roof", "commercial roofer", "roofing business",
    ],
    "roof_repair": [
        "roof leak repair", "emergency roof repair", "storm damage roof",
        "roof patch", "roofing emergency", "leaking roof", "roof tarp",
    ],
    # ── Medical & Health ──
    "weight_loss": [
        "weight loss", "weight management", "semaglutide weight loss",
        "ozempic weight loss", "medical weight loss", "diet program",
        "bmi", "lose weight",
    ],
    "hormone_therapy": [
        "hormone therapy", "hormone replacement", "testosterone", "hrt",
        "menopause treatment", "low testosterone", "estrogen therapy",
        "bioidentical hormones",
    ],
    "dental": [
        "dentist", "dental implant", "teeth whitening", "orthodontist",
        "braces", "invisalign", "dental crown", "root canal", "oral surgery",
    ],
    "vision": [
        "optometrist", "ophthalmologist", "lasik", "eye exam", "cataract",
        "glasses", "contact lenses", "vision correction",
    ],
    "pt_rehab": [
        "physical therapy", "sports medicine", "rehab", "chiropractor",
        "occupational therapy", "back pain", "knee pain", "physical therapist",
    ],
    "addiction": [
        "addiction treatment", "rehab center", "detox", "alcohol rehab",
        "drug rehab", "substance abuse", "sober living", "opioid treatment",
    ],
    # ── Business Services ──
    "marketing": [
        "marketing agency", "digital marketing", "seo services", "ppc",
        "social media marketing", "content marketing", "lead generation",
        "marketing consultant",
    ],
    "web_dev": [
        "web development", "web design", "website builder", "web developer",
        "ecommerce development", "wordpress", "react developer", "full stack",
    ],
    "accounting": [
        "accountant", "bookkeeping", "tax accountant", "cpa",
        "small business accounting", "payroll", "quickbooks",
    ],
    "consulting": [
        "business consultant", "management consulting", "strategy consultant",
        "business coach", "operations consulting", "growth consultant",
    ],
    "staffing": [
        "staffing agency", "recruitment", "employment agency", "temp agency",
        "headhunter", "talent acquisition", "job placement",
    ],
    "legal_services": [
        "lawyer", "attorney", "law firm", "legal services", "business lawyer",
        "contract attorney", "family law", "estate planning",
    ],
    # ── Financial ──
    "real_estate": [
        "real estate agent", "realtor", "home buying", "sell my house",
        "property listing", "real estate broker", "home valuation",
    ],
    "mortgage": [
        "mortgage", "home loan", "refinance", "mortgage broker",
        "home equity loan", "fha loan", "mortgage lender", "rate quote",
    ],
    "insurance": [
        "insurance agent", "insurance broker", "life insurance", "home insurance",
        "auto insurance", "health insurance", "insurance quote",
    ],
    "investing": [
        "financial advisor", "wealth management", "investment advisor",
        "retirement planning", "stock broker", "financial planner", "robo advisor",
    ],
    "debt_relief": [
        "debt relief", "debt settlement", "credit card debt", "bankruptcy",
        "debt consolidation", "credit repair", "loan modification",
    ],
    "tax_prep": [
        "tax preparation", "tax preparer", "tax return", "tax filing",
        "irs help", "business tax", "tax planning", "enrolled agent",
    ],
    # ── Technology ──
    "managed_it": [
        "managed it", "it support", "managed service provider", "msp",
        "computer repair business", "network support", "it consulting",
        "helpdesk",
    ],
    "cybersecurity": [
        "cybersecurity", "information security", "penetration testing",
        "security audit", "ransomware protection", "network security",
        "security consultant",
    ],
    "software_dev": [
        "software development", "custom software", "mobile app developer",
        "saas development", "api development", "software engineer",
        "devops consulting",
    ],
    "cloud": [
        "cloud migration", "cloud consulting", "aws consultant", "azure",
        "google cloud", "cloud infrastructure", "cloud architect",
    ],
    "ai_automation": [
        "ai consulting", "automation", "machine learning", "robotic process",
        "ai chatbot", "gpt integration", "intelligent automation",
    ],
    "data_analytics": [
        "data analytics", "business intelligence", "data science",
        "power bi", "tableau", "data engineering", "analytics consultant",
    ],
    # ── Restoration & Remediation ──
    "water_damage": [
        "water damage", "flood cleanup", "water removal", "water extraction",
        "basement flooding", "water damage restoration", "wet carpet",
        "drying service", "flood restoration",
    ],
    "fire_damage": [
        "fire damage", "smoke damage", "fire restoration", "soot cleanup",
        "fire cleanup", "smoke odor removal", "fire remediation",
        "structure fire", "burn damage",
    ],
    "mold_remediation": [
        "mold", "mold inspection", "mold removal", "mold remediation",
        "black mold", "mold testing", "toxic mold", "mold cleanup",
        "mold abatement", "musty smell",
    ],
    "storm_damage": [
        "storm damage", "wind damage", "hail damage", "hurricane damage",
        "tornado damage", "storm restoration", "tree fell on house",
        "storm cleanup", "emergency board up",
    ],
    "sewage_cleanup": [
        "sewage backup", "sewer backup", "biohazard cleanup", "septic backup",
        "wastewater cleanup", "raw sewage", "toilet overflow", "sewage cleanup",
    ],
    "disaster_restoration": [
        "disaster restoration", "large loss", "catastrophe response",
        "commercial restoration", "emergency response team", "disaster recovery",
        "iaa", "insurance restoration", "rapid response restoration",
    ],
}

# ── Metro routing ────────────────────────────────────────────────────

def get_primary_metro(state: str) -> str:
    """Resolve state abbreviation to the primary metro key."""
    metros = state_to_metros(state)
    return metros[0] if metros else "DFW"


def match_niche(text: str) -> list[tuple[str, float]]:
    """Score all sub-niches against a prospect's description text.

    Returns list of (sub_niche_key, confidence 0-10) sorted by confidence desc.
    """
    if not text:
        return []

    text_lower = text.lower()
    scores: dict[str, float] = {}

    for niche, keywords in MATCH_KEYWORDS.items():
        score = 0.0
        for kw in keywords:
            # Count occurrences and weight by keyword length
            count = len(re.findall(re.escape(kw.lower()), text_lower))
            if count:
                # Base weight: keyword length / 2, capped at 3 per match
                weight = min(len(kw) / 6, 3.0)
                score += count * weight

        if score > 0:
            # Normalize to 0-10 scale
            scores[niche] = min(score / 1.5, 10.0)

    # Sort desc
    result = sorted(scores.items(), key=lambda x: -x[1])
    return result


def route_lead(backend, prospect_id: str, details: str,
               state: str = "", zip_code: str = "") -> dict:
    """Route a prospect to the best matching lane.

    Returns routing result with lane_id, niche match, metro, and seat status.
    """
    # Resolve metro: prefer explicit state param, else scan details text
    # for US state abbreviations (handles "AZ & TX" style multi-state leads).
    resolved_state = state
    if not resolved_state:
        import re as _re
        _found = _re.findall(r"\b([A-Z]{2})\b", details or "")
        for _ab in _found:
            if _ab in STATE_METRO:
                resolved_state = _ab
                break
    metro = get_primary_metro(resolved_state)
    matches = match_niche(details)

    if not matches:
        return {
            "ok": False,
            "error": "No matching niche found for prospect description",
            "prospect_id": prospect_id,
            "metro": metro,
        }

    best_niche = matches[0][0]
    best_confidence = round(matches[0][1], 1)
    lane_id = f"{best_niche}:{metro}"

    # Check if lane exists and has a seat
    lane = backend.execute(
        "SELECT * FROM lanes WHERE id=?", (lane_id,)
    ).fetchone()

    occupied = False
    firm_name = None
    firm_tier = None

    if lane and lane["occupied_by"]:
        occupied = True
        firm_name = lane["occupied_by"]
        firm_tier = lane.get("firm_tier", "standard")

    result = {
        "ok": True,
        "prospect_id": prospect_id,
        "lane_id": lane_id,
        "niche_matches": matches[:3],  # top 3
        "best_niche": best_niche,
        "confidence": best_confidence,
        "metro": metro,
        "seat_occupied": occupied,
        "seat_firm": firm_name,
        "seat_tier": firm_tier,
    }

    # Log the lead
    try:
        backend.execute(
            "INSERT INTO lane_leads (lane_id, prospect_id, status, created_at) VALUES (?,?,?,?)",
            (lane_id, prospect_id, "routed", datetime.now(timezone.utc).isoformat()),
        )
        backend.commit()
    except Exception as e:
        logger.warning(f"Failed to log lead route: {e}")

    return result
