"""Ad-Gen Architect Module — generates content improvement briefs.

Takes Judge scorecards and generates structured content briefs for
improving AEO pages. Outputs are designed to be consumed by human
writers or AI content generation pipelines.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger("adgen-architect")


def generate_brief(niche: str, scorecard: dict) -> dict:
    """Generate a complete content improvement brief from a judge scorecard.

    Args:
        niche: Sub-niche key (e.g., 'hvac', 'camp_lejeune')
        scorecard: Output from judge_page()

    Returns:
        Structured brief with content strategy, section breakdown, and priority items.
    """
    recs = scorecard.get("recommendations", [])
    dims = scorecard.get("dimensions", {})
    breakdown = scorecard.get("breakdown", {})

    # Categorize recommendations
    critical = [r for r in recs if r.startswith("CRITICAL")]
    high = [r for r in recs if not r.startswith("CRITICAL")][:3]
    medium = [r for r in recs if not r.startswith("CRITICAL")][3:]

    # Determine page sections needed
    sections = _recommend_sections(breakdown, niche)

    # Content type recommendations
    content_types = _recommend_content_types(niche, dims)

    brief = {
        "niche": niche,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_score": scorecard.get("total_score", 0),
        "current_tier": scorecard.get("tier", {}).get("tier", "unknown"),
        "target_score": min(scorecard.get("total_score", 0) + 25, 95),
        "priority_items": {
            "critical": critical,
            "high_priority": high,
            "medium_priority": medium,
        },
        "recommended_sections": sections,
        "recommended_content_types": content_types,
        "estimated_word_count": _estimate_word_count(sections),
        "key_phrases": _suggest_key_phrases(niche),
        "competitor_gaps": breakdown,
    }

    return brief


def _recommend_sections(breakdown: dict, niche: str) -> list[dict]:
    """Recommend page sections based on judge gaps."""
    sections = []
    seen = set()

    seo = breakdown.get("seo_optimization", {})
    conv = breakdown.get("conversion_quality", {})

    # Hero section (always recommend)
    sections.append({
        "section": "hero",
        "priority": "critical",
        "estimated_words": 100,
        "notes": "H1 with target keyword, subheadline with value prop, primary CTA button"
    })
    seen.add("hero")

    # Problem/agitation section
    sections.append({
        "section": "problem_agitation",
        "priority": "high",
        "estimated_words": 200,
        "notes": "Describe the pain point or legal/health concern the visitor has"
    })
    seen.add("problem_agitation")

    # Solution section
    sections.append({
        "section": "solution_overview",
        "priority": "high",
        "estimated_words": 250,
        "notes": "How we help — service description, case review, or consultation path"
    })
    seen.add("solution_overview")

    # Benefits section (if missing)
    depth = breakdown.get("content_depth", {})
    if not depth.get("structured_benefits"):
        sections.append({
            "section": "benefits_cards",
            "priority": "high",
            "estimated_words": 200,
            "notes": "3-4 benefit cards with icons — why choose us, what sets us apart"
        })
        seen.add("benefits_cards")

    # Trust signals section
    trust = breakdown.get("trust_signals", {})
    signals = trust.get("signals_found", [])
    if len(signals) < 3:
        sections.append({
            "section": "trust_signals",
            "priority": "high",
            "estimated_words": 150,
            "notes": "Testimonials, guarantees, credentials, awards, experience"
        })
        seen.add("trust_signals")

    # FAQ section
    sections.append({
        "section": "faq",
        "priority": "medium",
        "estimated_words": 300,
        "notes": "5-7 frequently asked questions with structured answers (schema markup)"
    })
    seen.add("faq")

    # CTA section (if form missing)
    if "missing" in str(conv.get("form", "")):
        sections.append({
            "section": "lead_form",
            "priority": "critical",
            "estimated_words": 50,
            "notes": "Contact form: name, email/phone, state selector, brief description, submit button"
        })
        seen.add("lead_form")

    # Footer with trust
    sections.append({
        "section": "footer",
        "priority": "medium",
        "estimated_words": 50,
        "notes": "Privacy policy link, copyright, contact info, security badges"
    })
    seen.add("footer")

    return sections


def _recommend_content_types(niche: str, dims: dict) -> list[str]:
    """Recommend supplementary content formats."""
    types = []

    # For legal niches
    if niche in ("camp_lejeune", "roundup", "paraquat", "afff",
                 "zantac", "ozempic", "3m_earplugs", "nec_formula",
                 "talcum_powder", "hernia_mesh", "philips_cpap",
                 "hair_relaxers"):
        types.extend([
            "settlement_calculator — interactive tool to estimate potential compensation",
            "timeline_infographic — visual timeline of lawsuit developments",
            "eligibility_checker — quiz-style qualification screener",
        ])

    # For service niches
    else:
        types.append("cost_calculator — transparent pricing estimator")
        types.append("service_area_map — interactive coverage area visualization")

    # Always recommend these
    types.append("testimonial_carousel — rotating client success stories")
    types.append("blog_section — linked articles for topical authority")

    return types


def _estimate_word_count(sections: list[dict]) -> int:
    """Estimate total word count for recommended sections."""
    return sum(s.get("estimated_words", 100) for s in sections)


def _suggest_key_phrases(niche: str) -> list[str]:
    """Suggest key phrases and semantic LSI terms for the niche."""
    PHRASES = {
        "camp_lejeune": ["Camp Lejeune lawsuit", "toxic water contamination",
                         "veterans compensation", "Camp Lejeune cancer",
                         "free case evaluation", "Marine Corps base water"],
        "roundup": ["Roundup cancer lawsuit", "glyphosate non-Hodgkin lymphoma",
                    "weed killer compensation", "Monsanto settlement",
                    "free claim review", "Roundup Parkinson's"],
        "paraquat": ["Paraquat Parkinson's lawsuit", "herbicide exposure",
                     "parkinson's disease claim", "Gramoxone lawsuit",
                     "agricultural chemical injury"],
        "afff": ["AFFF lawsuit", "firefighting foam cancer",
                 "PFAS water contamination", "firefighter lawsuit",
                 "military base water contamination"],
        "zantac": ["Zantac lawsuit", "ranitidine cancer claim",
                   "NDMA contamination", "heartburn medication lawsuit"],
        "ozempic": ["Ozempic lawsuit", "stomach paralysis claim",
                    "GLP-1 side effects", "weight loss drug injury"],
        "hvac": ["HVAC repair", "AC installation", "heating service",
                 "furnace replacement", "emergency HVAC"],
        "plumbing": ["emergency plumber", "pipe repair", "water heater",
                     "drain cleaning", "sewer line repair"],
        "electrical": ["licensed electrician", "electrical repair",
                       "panel upgrade", "wiring installation"],
        "roofing": ["roof repair", "roof replacement", "roofing contractor",
                    "shingle installation", "roof leak"],
        "pest_control": ["pest control near me", "exterminator",
                         "termite treatment", "bed bug removal"],
        "weight_loss": ["medical weight loss", "semaglutide",
                        "tirzepatide", "GLP-1 weight loss program"],
        "marketing": ["digital marketing agency", "SEO services",
                      "lead generation", "PPC management"],
        "web_dev": ["web development company", "custom website design",
                    "ecommerce development"],
        "cybersecurity": ["cybersecurity services", "penetration testing",
                          "security audit", "managed security"],
        "real_estate": ["real estate agent", "home buyer", "sell my house",
                        "property listing", "realtor near me"],
        "insurance": ["insurance agent", "life insurance quotes",
                      "home insurance", "auto insurance"],
    }

    # Return niche-specific phrases or generic fallback
    return PHRASES.get(niche, [
        f"{niche.replace('_', ' ')} services",
        f"best {niche.replace('_', ' ')} near me",
        f"professional {niche.replace('_', ' ')}",
        f"{niche.replace('_', ' ')} expert",
        "free consultation",
    ])
