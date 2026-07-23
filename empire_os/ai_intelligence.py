#!/usr/bin/env python3
"""
Empire OS v3 — AI Intelligence Layer
=====================================
Unified AI brain for the entire revenue pipeline:
- Page-level niche analysis & buying signal extraction
- Predictive revenue formula (LTV * P(close) * velocity)
- Omega tiering via LLM reasoning
- A2A buyer matching via semantic similarity
- Dynamic strategy selection per lead
"""

import json
import os
import time
import hashlib
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# LLM client (supports OpenRouter, OpenAI-compatible)
try:
    import openai
except ImportError:
    openai = None

# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────
def _get_openrouter_key() -> str:
    """Get OpenRouter key from env or secrets file."""
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        # Try secrets file
        try:
            key = Path("/root/empire_secrets/openrouter_api_key").read_text().strip()
        except Exception:
            pass
    return key

def _get_default_model() -> str:
    return os.environ.get("AI_MODEL", "google/gemini-2.5-flash")

DEFAULT_MODEL = _get_default_model()
CACHE_DIR = Path("/root/empire_os/cache/ai")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = 86400 * 7  # 7 days

# ──────────────────────────────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────────────────────────────

@dataclass
class PageAnalysis:
    """AI analysis of a single page/domain."""
    domain: str
    niche: str                    # roofing, hvac, plumbing, etc.
    sub_niche: str               # residential_roofing, commercial_hvac, etc.
    buying_signals: List[str]    # ["hiring", "expansion", "funding", "permit_filed", "negative_reviews"]
    company_size_estimate: str   # "solo", "small_2_10", "mid_11_50", "large_50_200", "enterprise_200+"
    tech_stack: List[str]        # ["jobber", "housecall_pro", "servicetitan", "quickbooks"]
    location_signals: List[str]  # ["dallas_metro", "texas", "service_radius_50mi"]
    revenue_estimate: Dict       # {"min": 500000, "max": 2000000, "confidence": 0.7}
    urgency_score: float         # 0-1 (how badly they need leads now)
    fit_score: float             # 0-1 (how well they match our buyer criteria)
    reasoning: str               # LLM explanation
    tokens_used: int
    model: str
    cached: bool

@dataclass
class PredictiveRevenue:
    """Predictive revenue formula output."""
    lead_id: str
    domain: str
    niche: str
    metro: str
    
    # Core formula components
    ltv_estimate: float          # Lifetime value if they become a buyer
    p_close: float               # Probability of closing (0-1)
    velocity_days: float         # Expected days to close
    
    # Revenue prediction
    expected_revenue: float      # LTV * P(close)
    revenue_per_day: float       # Expected revenue / velocity
    
    # Risk factors
    risk_factors: List[str]
    confidence: float            # 0-1 overall confidence
    
    # Omega tier recommendation
    omega_tier: str              # S, A, B, C, D
    omega_reasoning: str
    
    # Strategy
    recommended_strategy: str    # "immediate_outreach", "nurture", "buyer_marketplace", "ignore"
    next_action: str
    priority_score: float        # 0-100 for queue prioritization

@dataclass
class BuyerMatch:
    """A2A buyer marketplace match."""
    lead_domain: str
    buyer_id: str
    buyer_name: str
    match_score: float           # 0-1 semantic similarity
    buyer_criteria_match_revenue_share: float  # % they pay
    buyer_volume_capacity: int   # leads/month they can handle
    reasoning: str

# ──────────────────────────────────────────────────────────────────────
# LLM Client with Caching
# ──────────────────────────────────────────────────────────────────────

class LLMClient:
    def __init__(self):
        self.client = None
        key = _get_openrouter_key()
        if key and openai:
            self.client = openai.OpenAI(
                api_key=key,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "https://empireos.ai",
                    "X-Title": "Empire OS v3"
                }
            )
    
    def _cache_key(self, prompt: str, model: str) -> Path:
        h = hashlib.sha256(f"{model}:{prompt}".encode()).hexdigest()[:16]
        return CACHE_DIR / f"{model.replace('/', '_')}_{h}.json"
    
    def complete(self, prompt: str, model: str = None, temperature: float = 0.1, 
                 max_tokens: int = 2000, use_cache: bool = True) -> Dict:
        model = model or DEFAULT_MODEL
        
        # Check cache
        if use_cache:
            cache_path = self._cache_key(prompt, model)
            if cache_path.exists():
                try:
                    data = json.loads(cache_path.read_text())
                    if time.time() - data.get("ts", 0) < CACHE_TTL:
                        data["cached"] = True
                        return data
                except Exception:
                    pass
        
        if not self.client:
            return {"error": "No LLM client configured", "content": ""}
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            result = {
                "content": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens,
                "model": model,
                "cached": False,
                "ts": time.time()
            }
            
            # Save to cache
            if use_cache:
                try:
                    cache_path = self._cache_key(prompt, model)
                    cache_path.write_text(json.dumps(result))
                except Exception:
                    pass
            
            return result
        except Exception as e:
            return {"error": str(e), "content": "", "tokens_used": 0, "model": model}

llm = LLMClient()

# ──────────────────────────────────────────────────────────────────────
# Prompt Templates
# ──────────────────────────────────────────────────────────────────────

PAGE_ANALYSIS_PROMPT = """
You are an expert B2B lead analyst for home services / contractor verticals.
Analyze this webpage content and extract structured intelligence.

DOMAIN: {domain}
METRO: {metro}
PAGE CONTENT (first 8000 chars):
---
{content}
---

Extract the following as JSON:
{{
  "niche": "primary_niche_slug",           // roofing, hvac, plumbing, electrical, solar, landscaping, pest_control, painting, fencing, windows, flooring, concrete, excavation, tree_service, pool_service, cleaning, security, moving, storage, trucking, logistics, warehouse, manufacturing, fintech, ecommerce, chiropractic, veterinary, physiotherapy, auto, tire, title, mortgage, property_mgmt, restaurant, hotel, retail, fitness, photography, webdev, seo, consulting, recruiter, courier, waste, equipment, flooring, painting, cabinetry, countertops, glass, masonry, foundation, demolition, junk_removal, handyman, general_contractor
  "sub_niche": "specific_sub_niche",       // residential_roofing, commercial_hvac, emergency_plumbing, solar_install, tree_removal, etc.
  "buying_signals": [                      // Array of detected signals
    "hiring", "expansion", "funding_announced", "permit_filed", 
    "negative_reviews", "website_redesign", "ad_spend_detected", 
    "new_location", "acquisition", "partnership_announced",
    "certification_earned", "award_won", "media_mention"
  ],
  "company_size_estimate": "solo|small_2_10|mid_11_50|large_50_200|enterprise_200_plus",
  "tech_stack": ["jobber", "housecall_pro", "servicetitan", "quickbooks", "hubspot", "salesforce", "zoho", "pipedrive", "monday", "asana", "clickup", "google_ads", "facebook_ads", "angie_ads", "yelp_ads", "thrive_ads", "call_rail", "call_tracking"],
  "location_signals": ["dallas_metro", "texas", "service_radius_50mi", "multiple_locations"],
  "revenue_estimate": {{"min": 500000, "max": 2000000, "confidence": 0.7}},
  "urgency_score": 0.8,                    // 0-1: how badly they need leads NOW
  "fit_score": 0.75,                       // 0-1: how well they match ideal buyer profile (home services, $500k-$50M revenue, growth-minded)
  "reasoning": "Detailed explanation of analysis..."
}}

Return ONLY valid JSON. No markdown, no extra text.
"""

PREDICTIVE_REVENUE_PROMPT = """
You are a revenue operations analyst for a B2B lead marketplace.
Given this lead analysis, compute the predictive revenue formula.

LEAD DATA:
- Domain: {domain}
- Niche: {niche}
- Sub-niche: {sub_niche}
- Metro: {metro}
- Company Size: {company_size}
- Revenue Estimate: {revenue_estimate}
- Buying Signals: {buying_signals}
- Tech Stack: {tech_stack}
- Urgency Score: {urgency_score}
- Fit Score: {fit_score}
- Page Analysis Reasoning: {reasoning}

MARKET CONTEXT:
- Average deal size for {niche} in {metro}: ${avg_deal_size}
- Average sales cycle: {avg_cycle_days} days
- Buyer pay-per-lead range: ${ppc_min}-${ppc_max}
- Buyer take rate: {buyer_take_rate}%
- Our platform fee: {platform_fee}%

Compute the PREDICTIVE REVENUE FORMULA:

LTV = (avg_deal_size * buyer_take_rate * (1 - platform_fee)) * expected_deals_per_year
P_CLOSE = f(urgency, fit, buying_signals, company_size, tech_sophistication)
VELOCITY = f(urgency, sales_cycle, buyer_readiness)

EXPECTED_REVENUE = LTV * P_CLOSE
REVENUE_PER_DAY = EXPECTED_REVENUE / VELOCITY

OMEGA TIER:
- S: EXPECTED_REVENUE > $10k, P_CLOSE > 0.7, VELOCITY < 30 days
- A: EXPECTED_REVENUE $5k-10k, P_CLOSE > 0.5, VELOCITY < 60 days
- B: EXPECTED_REVENUE $1k-5k, P_CLOSE > 0.3, VELOCITY < 90 days
- C: EXPECTED_REVENUE $100-1k, P_CLOSE > 0.15
- D: Everything else

STRATEGY:
- immediate_outreach: High urgency, high fit, buyer ready
- nurture: Good fit but low urgency, needs education
- buyer_marketplace: Strong buyer demand exists, push to A2A
- ignore: Low fit, low revenue potential

Return JSON:
{
  "ltv_estimate": 12500.0,
  "p_close": 0.65,
  "velocity_days": 45,
  "expected_revenue": 8125.0,
  "revenue_per_day": 180.55,
  "risk_factors": ["long_sales_cycle", "low_tech_sophistication"],
  "confidence": 0.72,
  "omega_tier": "A",
  "omega_reasoning": "Strong fit, good urgency, reasonable velocity",
  "recommended_strategy": "immediate_outreach",
  "next_action": "Send personalized video proposal to owner",
  "priority_score": 87.5
}

Return ONLY valid JSON.
"""

OMEGA_TIER_PROMPT = """
You are the Omega Tiering Engine for Empire OS.
Given a lead's predictive revenue profile, assign the Omega tier and provide reasoning.

LEAD PROFILE:
- Domain: {domain}
- Niche: {niche}
- Metro: {metro}
- Expected Revenue: ${expected_revenue}
- P(Close): {p_close}
- Velocity: {velocity_days} days
- LTV: ${ltv_estimate}
- Risk Factors: {risk_factors}
- Company Size: {company_size}
- Buying Signals: {buying_signals}

TIER DEFINITIONS:
S: "Strategic" - $10k+ expected revenue, >70% close probability, <30 days velocity. Immediate C-suite attention.
A: "Accelerate" - $5k-10k, >50% close, <60 days. Sales team priority queue.
B: "Build" - $1k-5k, >30% close, <90 days. Nurture with automated sequences.
C: "Consider" - $100-1k, >15% close. Low-touch automation only.
D: "Discard" - Below thresholds. Do not pursue.

Return JSON:
{{
  "tier": "S|A|B|C|D",
  "confidence": 0.85,
  "reasoning": "Detailed explanation...",
  "recommended_actions": ["action1", "action2"],
  "escalation_path": "sales_rep|sales_manager|vp_sales|c_suite|none"
}}
"""

BUYER_MATCH_PROMPT = """
You are the A2A (Agent-to-Agent) Matching Engine.
Match this lead to the best buyer in our marketplace.

LEAD:
- Domain: {lead_domain}
- Niche: {niche}
- Sub-niche: {sub_niche}
- Metro: {metro}
- Company Size: {company_size}
- Revenue Range: ${rev_min}-${rev_max}
- Buying Signals: {buying_signals}
- Tech Stack: {tech_stack}
- Omega Tier: {omega_tier}
- Expected Revenue: ${expected_revenue}

AVAILABLE BUYERS:
{buyers_json}

Each buyer has: id, name, niches[], metros[], min_revenue, max_revenue, company_sizes[], 
tech_preferences[], payout_per_lead, monthly_capacity, current_load, specialties[], 
performance_score (0-1), response_time_hours.

Match on: niche overlap, metro overlap, revenue fit, capacity, performance.
Score 0-1. Only return matches > 0.6.

Return JSON:
{{
  "matches": [
    {{
      "buyer_id": "buyer_123",
      "buyer_name": "Acme Roofing Leads",
      "match_score": 0.87,
      "match_reasons": ["niche:roofing", "metro:dallas", "revenue_fit:500k-2m", "capacity:50/mo"],
      "buyer_revenue_share": 0.7,
      "buyer_volume_capacity": 50,
      "estimated_monthly_revenue": 3500
    }}
  ],
  "best_match": "buyer_123",
  "routing_decision": "push_to_buyer_now|queue_for_morning|hold_for_capacity"
}}
"""

# ──────────────────────────────────────────────────────────────────────
# Core Functions
# ──────────────────────────────────────────────────────────────────────

def analyze_page(domain: str, metro: str, content: str, max_chars: int = 8000) -> PageAnalysis:
    """Analyze a single page with AI (or fallback to heuristics)."""
    content = content[:max_chars]
    
    # Check if LLM is available
    if not llm.client:
        return _analyze_page_heuristic(domain, metro, content)
    
    prompt = PAGE_ANALYSIS_PROMPT.format(domain=domain, metro=metro, content=content)
    
    result = llm.complete(prompt, temperature=0.1, max_tokens=1500)
    
    if result.get("error"):
        return _analyze_page_heuristic(domain, metro, content)
    
    try:
        data = json.loads(result["content"])
        return PageAnalysis(
            domain=domain,
            niche=data.get("niche", "unknown"),
            sub_niche=data.get("sub_niche", "unknown"),
            buying_signals=data.get("buying_signals", []),
            company_size_estimate=data.get("company_size_estimate", "unknown"),
            tech_stack=data.get("tech_stack", []),
            location_signals=data.get("location_signals", []),
            revenue_estimate=data.get("revenue_estimate", {}),
            urgency_score=float(data.get("urgency_score", 0.0)),
            fit_score=float(data.get("fit_score", 0.0)),
            reasoning=data.get("reasoning", ""),
            tokens_used=result.get("tokens_used", 0),
            model=result.get("model", DEFAULT_MODEL),
            cached=result.get("cached", False)
        )
    except Exception as e:
        return _analyze_page_heuristic(domain, metro, content)


def _analyze_page_heuristic(domain: str, metro: str, content: str) -> PageAnalysis:
    """Fallback heuristic analysis when no LLM available."""
    content_lower = content.lower()
    
    # Niche detection via keywords
    NICHE_KEYWORDS = {
        "roofing": ["roof", "roofing", "shingle", "gutter", "storm damage", "leak repair"],
        "hvac": ["hvac", "air condition", "heating", "cooling", "furnace", "ac repair", "duct"],
        "plumbing": ["plumb", "pipe", "drain", "sewer", "water heater", "leak", "clog"],
        "electrical": ["electric", "wiring", "panel", "outlet", "circuit", "generator"],
        "solar": ["solar", "panel", "photovoltaic", "renewable energy", "solar install"],
        "landscaping": ["landscape", "lawn", "mowing", "sprinkler", "irrigation", "yard"],
        "pest_control": ["pest", "termite", "rodent", "ant", "roach", "exterminat"],
        "painting": ["paint", "painting", "stain", "exterior paint", "interior paint"],
        "fencing": ["fence", "fencing", "gate", "privacy fence"],
        "windows": ["window", "replacement window", "vinyl window", "double pane"],
        "flooring": ["floor", "flooring", "hardwood", "tile", "carpet", "laminate"],
        "concrete": ["concrete", "driveway", "patio", "foundation", "slab"],
        "excavation": ["excavat", "grading", "site prep", "earthwork", "trenching"],
        "tree_service": ["tree", "arborist", "stump", "trimming", "removal"],
        "pool_service": ["pool", "spa", "hot tub", "pool clean", "pool repair"],
        "cleaning": ["clean", "janitor", "maid", "pressure wash", "power wash"],
        "security": ["security", "alarm", "camera", "surveillance", "access control"],
        "moving": ["move", "moving", "relocation", "packing", "storage"],
        "handyman": ["handyman", "repair", "fix", "maintenance", "odd jobs"],
        "general_contractor": ["general contractor", "remodel", "renovation", "addition", "build"],
    }
    
    niche = "unknown"
    sub_niche = "unknown"
    for n, keywords in NICHE_KEYWORDS.items():
        if any(k in content_lower for k in keywords):
            niche = n
            sub_niche = f"{n}_services"
            break
    
    # Buying signals
    buying_signals = []
    if any(k in content_lower for k in ["hiring", "join our team", "careers", "now hiring", "employment"]):
        buying_signals.append("hiring")
    if any(k in content_lower for k in ["expand", "expansion", "new location", "growing"]):
        buying_signals.append("expansion")
    if any(k in content_lower for k in ["permit", "permitted", "permitting"]):
        buying_signals.append("permit_filed")
    if any(k in content_lower for k in ["bad review", "negative review", "complaint", "unhappy"]):
        buying_signals.append("negative_reviews")
    if any(k in content_lower for k in ["new website", "redesign", "rebrand", "new site"]):
        buying_signals.append("website_redesign")
    if any(k in content_lower for k in ["google ads", "facebook ads", "advertising", "marketing budget"]):
        buying_signals.append("ad_spend_detected")
    if any(k in content_lower for k in ["certified", "certification", "licensed", "insured", "bonded"]):
        buying_signals.append("certification_earned")
    if any(k in content_lower for k in ["award", "best of", "top rated", "5 star"]):
        buying_signals.append("award_won")
    
    # Company size estimate
    if any(k in content_lower for k in ["family owned", "owner operated", "sole proprietor", "i am", "my business"]):
        size = "solo"
    elif any(k in content_lower for k in ["team of", "employees", "staff of", "crew of"]):
        size = "small_2_10"
    elif any(k in content_lower for k in ["team of 20", "team of 30", "50 employees", "100 employees"]):
        size = "mid_11_50"
    elif any(k in content_lower for k in ["200 employees", "500 employees", "national", "multiple states"]):
        size = "large_50_200"
    else:
        size = "small_2_10"
    
    # Tech stack detection
    tech_stack = []
    tech_keywords = {
        "jobber": ["jobber"],
        "housecall_pro": ["housecall pro", "housecallpro"],
        "servicetitan": ["service titan", "servicetitan"],
        "quickbooks": ["quickbooks", "quickbook"],
        "hubspot": ["hubspot"],
        "salesforce": ["salesforce"],
        "google_ads": ["google ads", "adwords"],
        "facebook_ads": ["facebook ads", "meta ads"],
        "angie_ads": ["angie", "angies list"],
        "yelp_ads": ["yelp ads"],
        "call_rail": ["call rail", "callrail"],
        "zoho": ["zoho"],
        "pipedrive": ["pipedrive"],
    }
    for tech, keywords in tech_keywords.items():
        if any(k in content_lower for k in keywords):
            tech_stack.append(tech)
    
    # Location signals
    location_signals = []
    metro_lower = metro.lower()
    if metro_lower in content_lower:
        location_signals.append(f"{metro_lower}_metro")
    if any(k in content_lower for k in ["texas", "tx", "dallas", "houston", "austin", "san antonio"]):
        location_signals.append("texas")
    if any(k in content_lower for k in ["service area", "service radius", "miles from", "surrounding"]):
        location_signals.append("service_radius_defined")
    
    # Revenue estimate (very rough)
    rev_min = {"solo": 100000, "small_2_10": 300000, "mid_11_50": 1000000, "large_50_200": 5000000, "enterprise_200_plus": 50000000}.get(size, 300000)
    rev_max = rev_min * 3
    
    # Urgency score
    urgency = 0.3
    if "hiring" in buying_signals: urgency += 0.2
    if "expansion" in buying_signals: urgency += 0.2
    if "ad_spend_detected" in buying_signals: urgency += 0.15
    if "negative_reviews" in buying_signals: urgency += 0.1
    urgency = min(1.0, urgency)
    
    # Fit score
    fit = 0.5
    if niche != "unknown": fit += 0.2
    if size in ("small_2_10", "mid_11_50"): fit += 0.15
    if tech_stack: fit += 0.1
    if buying_signals: fit += 0.1
    fit = min(1.0, fit)
    
    reasoning = f"Heuristic analysis: niche={niche}, size={size}, signals={buying_signals}, tech={tech_stack}"
    
    return PageAnalysis(
        domain=domain,
        niche=niche,
        sub_niche=sub_niche,
        buying_signals=buying_signals,
        company_size_estimate=size,
        tech_stack=tech_stack,
        location_signals=location_signals,
        revenue_estimate={"min": rev_min, "max": rev_max, "confidence": 0.4},
        urgency_score=urgency,
        fit_score=fit,
        reasoning=reasoning,
        tokens_used=0,
        model="heuristic",
        cached=False
    )

def analyze_pages_batch(pages: List[Dict], max_workers: int = 3) -> List[PageAnalysis]:
    """Analyze multiple pages in parallel."""
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(analyze_page, p["domain"], p.get("metro", ""), p.get("content", "")): p
            for p in pages
        }
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                p = futures[future]
                results.append(PageAnalysis(
                    domain=p["domain"], niche="error", sub_niche="error",
                    buying_signals=[], company_size_estimate="unknown",
                    tech_stack=[], location_signals=[], revenue_estimate={},
                    urgency_score=0.0, fit_score=0.0, reasoning=f"Batch error: {e}",
                    tokens_used=0, model=DEFAULT_MODEL, cached=False
                ))
    return results

def predict_revenue(analysis: PageAnalysis, metro: str, 
                    market_context: Dict = None) -> PredictiveRevenue:
    """Compute predictive revenue formula for a lead."""
    market_context = market_context or {}
    
    # Defaults by niche/metro
    avg_deal = market_context.get("avg_deal_size", 2500)
    avg_cycle = market_context.get("avg_cycle_days", 45)
    ppc_min = market_context.get("ppc_min", 15)
    ppc_max = market_context.get("ppc_max", 75)
    buyer_take = market_context.get("buyer_take_rate", 0.7)
    platform_fee = market_context.get("platform_fee", 0.1)
    
    # LTV estimation
    deals_per_year = max(1, 12 / (analysis.revenue_estimate.get("max", 1000000) / 100000))
    ltv = avg_deal * buyer_take * (1 - platform_fee) * deals_per_year
    
    # P(close) model
    base_close = 0.3
    urgency_boost = analysis.urgency_score * 0.3
    fit_boost = analysis.fit_score * 0.2
    size_mod = {"solo": -0.1, "small_2_10": 0.0, "mid_11_50": 0.1, "large_50_200": 0.15, "enterprise_200_plus": 0.2}.get(
        analysis.company_size_estimate, 0.0
    )
    signal_boost = min(len(analysis.buying_signals) * 0.05, 0.2)
    tech_boost = 0.1 if any(t in analysis.tech_stack for t in ["servicetitan", "housecall_pro", "jobber", "hubspot", "salesforce"]) else 0.0
    
    p_close = min(0.95, base_close + urgency_boost + fit_boost + size_mod + signal_boost + tech_boost)
    
    # Velocity model
    base_velocity = avg_cycle
    urgency_reduction = analysis.urgency_score * 15
    size_reduction = {"solo": 0, "small_2_10": -5, "mid_11_50": -10, "large_50_200": -15, "enterprise_200_plus": -20}.get(
        analysis.company_size_estimate, 0
    )
    velocity = max(7, base_velocity - urgency_reduction + size_reduction)
    
    # Expected revenue
    ltv_est = ltv * p_close
    expected_rev = ltv_est
    rev_per_day = expected_rev / max(1, velocity)
    
    # Risk factors
    risks = []
    if velocity > 90: risks.append("long_sales_cycle")
    if p_close < 0.3: risks.append("low_close_probability")
    if analysis.company_size_estimate == "solo": risks.append("solo_operator_risk")
    if not analysis.tech_stack: risks.append("low_tech_sophistication")
    if analysis.fit_score < 0.4: risks.append("poor_fit")
    
    # Omega tier
    if expected_rev > 10000 and p_close > 0.7 and velocity < 30:
        tier, tier_reason = "S", "High revenue, high close prob, fast velocity"
    elif expected_rev > 5000 and p_close > 0.5 and velocity < 60:
        tier, tier_reason = "A", "Strong revenue, good close prob, reasonable velocity"
    elif expected_rev > 1000 and p_close > 0.3 and velocity < 90:
        tier, tier_reason = "B", "Moderate revenue, decent close prob, manageable velocity"
    elif expected_rev > 100 and p_close > 0.15:
        tier, tier_reason = "C", "Low revenue potential but viable"
    else:
        tier, tier_reason = "D", "Below minimum thresholds"
    
    # Strategy — REVERSED 2026-07-23: tier B+ → buyer_marketplace FIRST.
    # Old logic sent tier B+fit>0.6 → nurture, starving A2A. We're a B2B
    # lead-gen business: leads go to BUYERS, nurture is fallback only.
    if tier in ("S", "A") and analysis.urgency_score > 0.7:
        strategy, next_action = "immediate_outreach", "Send personalized video proposal within 2 hours"
    elif tier in ("S", "A", "B"):
        # Any tier B+ lead goes to buyer marketplace. If no buyer matches,
        # a2a_buyer_marketplace.push_cycle will skip and the lead stays
        # pending — better than silently routing to nurture.
        strategy, next_action = "buyer_marketplace", "Push to A2A buyer marketplace immediately"
    elif analysis.fit_score > 0.6:
        # Nurture ONLY for tier C/D with good fit — long-tail pipeline
        strategy, next_action = "nurture", "Add to automated nurture sequence + schedule discovery call"
    else:
        strategy, next_action = "ignore", "Log and monitor for signal changes"
    
    priority = min(100, expected_rev / 100 * p_close * (100 / max(1, velocity)) * 10)
    
    return PredictiveRevenue(
        lead_id=f"lead_{hash(analysis.domain) % 100000}",
        domain=analysis.domain,
        niche=analysis.niche,
        metro=metro,
        ltv_estimate=round(ltv, 2),
        p_close=round(p_close, 3),
        velocity_days=round(velocity, 1),
        expected_revenue=round(expected_rev, 2),
        revenue_per_day=round(rev_per_day, 2),
        risk_factors=risks,
        confidence=round(min(0.95, analysis.fit_score * 0.5 + analysis.urgency_score * 0.3 + 0.2), 3),
        omega_tier=tier,
        omega_reasoning=tier_reason,
        recommended_strategy=strategy,
        next_action=next_action,
        priority_score=round(priority, 1)
    )

def tier_lead(analysis: PageAnalysis, revenue: PredictiveRevenue) -> Dict:
    """Omega tiering via LLM reasoning."""
    prompt = OMEGA_TIER_PROMPT.format(
        domain=analysis.domain,
        niche=analysis.niche,
        metro=revenue.metro,
        expected_revenue=revenue.expected_revenue,
        p_close=revenue.p_close,
        velocity_days=revenue.velocity_days,
        ltv_estimate=revenue.ltv_estimate,
        risk_factors=revenue.risk_factors,
        company_size=analysis.company_size_estimate,
        buying_signals=analysis.buying_signals
    )
    result = llm.complete(prompt, temperature=0.1, max_tokens=1000)
    if result.get("error"):
        return {"tier": revenue.omega_tier, "confidence": 0.5, "reasoning": "LLM error, using formula tier", "escalation_path": "none"}
    try:
        return json.loads(result["content"])
    except Exception:
        return {"tier": revenue.omega_tier, "confidence": 0.5, "reasoning": "Parse error", "escalation_path": "none"}

def match_buyers(analysis: PageAnalysis, revenue: PredictiveRevenue, buyers: List[Dict]) -> List[BuyerMatch]:
    """A2A buyer matching via LLM."""
    if not buyers:
        return []
    
    prompt = BUYER_MATCH_PROMPT.format(
        lead_domain=analysis.domain,
        niche=analysis.niche,
        sub_niche=analysis.sub_niche,
        metro=revenue.metro,
        company_size=analysis.company_size_estimate,
        rev_min=analysis.revenue_estimate.get("min", 0),
        rev_max=analysis.revenue_estimate.get("max", 0),
        buying_signals=analysis.buying_signals,
        tech_stack=analysis.tech_stack,
        omega_tier=revenue.omega_tier,
        expected_revenue=revenue.expected_revenue,
        buyers_json=json.dumps(buyers, indent=2)
    )
    
    result = llm.complete(prompt, temperature=0.1, max_tokens=1500)
    if result.get("error"):
        return []
    
    try:
        data = json.loads(result["content"])
        matches = []
        for m in data.get("matches", []):
            matches.append(BuyerMatch(
                lead_domain=analysis.domain,
                buyer_id=m.get("buyer_id", ""),
                buyer_name=m.get("buyer_name", ""),
                match_score=float(m.get("match_score", 0)),
                buyer_revenue_share=float(m.get("buyer_revenue_share", 0)),
                buyer_volume_capacity=int(m.get("buyer_volume_capacity", 0)),
                reasoning=m.get("match_reasons", "")
            ))
        return matches
    except Exception:
        return []

# ──────────────────────────────────────────────────────────────────────
# Full Pipeline
# ──────────────────────────────────────────────────────────────────────

def process_lead(domain: str, metro: str, content: str, 
                 buyers: List[Dict] = None,
                 market_context: Dict = None) -> Dict:
    """
    Complete AI pipeline for a single lead.
    Returns all intelligence: page analysis, revenue prediction, tier, buyer matches.
    """
    # 1. Page analysis
    analysis = analyze_page(domain, metro, content)
    
    # 2. Predictive revenue
    revenue = predict_revenue(analysis, metro, market_context)
    
    # 3. Omega tiering (LLM reasoning)
    tier_info = tier_lead(analysis, revenue)
    
    # 4. Buyer matching
    matches = match_buyers(analysis, revenue, buyers or [])
    
    return {
        "lead_id": revenue.lead_id,
        "domain": domain,
        "metro": metro,
        "analysis": asdict(analysis),
        "revenue_prediction": asdict(revenue),
        "omega_tier": tier_info,
        "buyer_matches": [asdict(m) for m in matches],
        "routing": {
            "strategy": revenue.recommended_strategy,
            "next_action": revenue.next_action,
            "priority": revenue.priority_score,
            "escalation": tier_info.get("escalation_path", "none")
        },
        "tokens_total": analysis.tokens_used
    }

def process_leads_batch(leads: List[Dict], buyers: List[Dict] = None,
                        market_context: Dict = None, max_workers: int = 3) -> List[Dict]:
    """Process multiple leads through the full AI pipeline."""
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_lead, l["domain"], l.get("metro", ""), l.get("content", ""), buyers, market_context): l
            for l in leads
        }
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                l = futures[future]
                results.append({"error": str(e), "domain": l["domain"]})
    return results

# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python3 -m empire_os.ai_intelligence <domain> <metro> [content_file]")
        sys.exit(1)
    
    domain = sys.argv[1]
    metro = sys.argv[2]
    
    if len(sys.argv) > 3:
        with open(sys.argv[3]) as f:
            content = f.read()
    else:
        # Fetch live
        import urllib.request
        try:
            req = urllib.request.Request(f"https://{domain}", headers={"User-Agent": "Mozilla/5.0"})
            content = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "ignore")
        except Exception as e:
            content = f"FETCH_ERROR: {e}"
    
    result = process_lead(domain, metro, content)
    print(json.dumps(result, indent=2))