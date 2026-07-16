"""Ad-Gen Judge Module — scores content quality, SEO, and conversion factors.

Evaluates AEO landing pages against a rubric of quality dimensions.
Returns a structured scorecard with actionable recommendations.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger("adgen-judge")

# Scoring weights
WEIGHTS = {
    "seo_optimization": 0.20,
    "conversion_quality": 0.25,
    "content_depth": 0.20,
    "readability": 0.10,
    "mobile_responsiveness": 0.10,
    "trust_signals": 0.15,
}


def judge_page(html: str, niche: str = "", url: str = "") -> dict:
    """Score an HTML page against the quality rubric.

    Args:
        html: Raw HTML content of the page
        niche: Sub-niche key (for context-aware scoring)
        url: Page URL (for reference)

    Returns:
        Scorecard dict with dimension scores, total, and recommendations.
    """
    scores = {}
    details = {}

    # 1. SEO Optimization (0-100)
    seo_score, seo_detail = _score_seo(html, niche)
    scores["seo_optimization"] = seo_score
    details["seo_optimization"] = seo_detail

    # 2. Conversion Quality (0-100)
    conv_score, conv_detail = _score_conversion(html)
    scores["conversion_quality"] = conv_score
    details["conversion_quality"] = conv_detail

    # 3. Content Depth (0-100)
    depth_score, depth_detail = _score_content_depth(html)
    scores["content_depth"] = depth_score
    details["content_depth"] = depth_detail

    # 4. Readability (0-100)
    read_score, read_detail = _score_readability(html)
    scores["readability"] = read_score
    details["readability"] = read_detail

    # 5. Mobile Responsiveness (0-100)
    mob_score, mob_detail = _score_mobile(html)
    scores["mobile_responsiveness"] = mob_score
    details["mobile_responsiveness"] = mob_detail

    # 6. Trust Signals (0-100)
    trust_score, trust_detail = _score_trust(html)
    scores["trust_signals"] = trust_score
    details["trust_signals"] = trust_detail

    # Weighted total
    total = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
    total = round(total, 1)

    # Generate recommendations
    recs = _generate_recommendations(scores, details)

    return {
        "url": url or "",
        "niche": niche,
        "total_score": total,
        "dimensions": {k: round(scores[k], 1) for k in WEIGHTS},
        "breakdown": details,
        "recommendations": recs,
        "tier": _tier_for(total),
    }


def _score_seo(html: str, niche: str) -> tuple[float, dict]:
    """SEO scoring: title tag, meta description, headings, keywords."""
    score = 50.0  # baseline
    points = {}

    # Title tag
    title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""
    if 30 <= len(title) <= 60:
        score += 15
        points["title_length"] = "optimal"
    elif title:
        score += 5
        points["title_length"] = f"{len(title)} chars (target 30-60)"
    else:
        score -= 20
        points["title_length"] = "missing"

    # Title has niche keyword
    if niche and niche.replace("_", " ") in title.lower():
        score += 10
        points["title_keyword"] = "present"
    else:
        score -= 5
        points["title_keyword"] = "missing niche keyword"

    # Meta description
    meta_match = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
        html, re.IGNORECASE | re.DOTALL
    )
    if meta_match and 120 <= len(meta_match.group(1)) <= 160:
        score += 15
        points["meta_desc"] = "optimal"
    elif meta_match:
        score += 5
        points["meta_desc"] = f"{len(meta_match.group(1))} chars"
    else:
        score -= 15
        points["meta_desc"] = "missing"

    # Canonical tag
    if re.search(r'<link\s+rel=["\']canonical["\']', html, re.IGNORECASE):
        score += 5
        points["canonical"] = "present"
    else:
        points["canonical"] = "missing"

    # H1 tag
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    if h1_match and len(h1_match.group(1).strip()) > 10:
        score += 10
        points["h1"] = "present"
    else:
        score -= 10
        points["h1"] = "missing or too short"

    # H2 headings
    h2_count = len(re.findall(r"<h2[^>]*>", html, re.IGNORECASE))
    if h2_count >= 3:
        score += 5
        points["h2_count"] = h2_count
    elif h2_count > 0:
        points["h2_count"] = f"{h2_count} (recommend 3+)"

    # Open Graph tags
    if re.search(r'<meta\s+property=["\']og:', html, re.IGNORECASE):
        score += 5
        points["og_tags"] = "present"

    return min(max(score, 0), 100), points


def _score_conversion(html: str) -> tuple[float, dict]:
    """Conversion scoring: CTAs, forms, action paths."""
    score = 40.0
    points = {}

    # Visible CTA buttons
    cta_patterns = [
        r'class=["\'][^"\']*cta[^"\']*["\']',
        r'class=["\'][^"\']*btn[^"\']*["\']',
        r'class=["\'][^"\']*button[^"\']*["\']',
        r'class=["\'][^"\']*submit[^"\']*["\']',
    ]
    cta_count = sum(
        len(re.findall(p, html, re.IGNORECASE)) for p in cta_patterns
    )
    if cta_count >= 3:
        score += 20
        points["cta_count"] = cta_count
    elif cta_count >= 1:
        score += 10
        points["cta_count"] = cta_count
    else:
        score -= 15
        points["cta_count"] = "none found"

    # Form
    if re.search(r"<form[^>]*>", html, re.IGNORECASE):
        score += 15
        points["form"] = "present"

        # Check for key fields
        fields = []
        if re.search(r'<input[^>]*name=["\'].*name', html, re.IGNORECASE):
            fields.append("name")
        if re.search(r'<input[^>]*type=["\']?(?:email|tel|phone)', html, re.IGNORECASE):
            fields.append("contact")
        if re.search(r'<textarea|<input[^>]*type=["\']?text', html, re.IGNORECASE):
            fields.append("description")
        points["form_fields"] = fields
        if len(fields) >= 3:
            score += 10
        elif len(fields) >= 1:
            score += 5
    else:
        score -= 20
        points["form"] = "missing — critical for lead capture"

    # Phone number
    phone_patterns = [
        r'<a[^>]*href=["\']tel:', r'\(\d{3}\)\s*\d{3}', r'\+\d{1,2}\s*\d{3}'
    ]
    if any(re.search(p, html) for p in phone_patterns):
        score += 10
        points["phone"] = "present"

    # Urgency/language
    urgency_words = ["now", "today", "limited", "free", "instant", "immediately"]
    urgency_count = sum(
        1 for w in urgency_words if re.search(rf"\b{w}\b", html, re.IGNORECASE)
    )
    if urgency_count >= 3:
        score += 5
        points["urgency"] = urgency_count

    return min(max(score, 0), 100), points


def _score_content_depth(html: str) -> tuple[float, dict]:
    """Content depth scoring: word count, paragraph structure, info density."""
    score = 50.0
    points = {}

    # Strip HTML for text analysis
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    words = len(text.split())

    if words >= 1500:
        score += 20
        points["word_count"] = f"{words} (extensive)"
    elif words >= 800:
        score += 10
        points["word_count"] = f"{words} (adequate)"
    elif words >= 400:
        points["word_count"] = f"{words} (thin — target 800+)"
    else:
        score -= 20
        points["word_count"] = f"{words} (very thin)"

    # Paragraph breaks
    para_count = len(re.findall(r"<p[^>]*>", html, re.IGNORECASE))
    if para_count >= 5:
        score += 10
        points["paragraphs"] = para_count
    else:
        points["paragraphs"] = f"{para_count} (recommend 5+)"

    # Sections with headings
    section_count = len(re.findall(r"<(h[1-6]|section)[^>]*>", html, re.IGNORECASE))
    if section_count >= 5:
        score += 10
        points["sections"] = section_count
    else:
        points["sections"] = f"{section_count} (recommend 5+)"

    # Lists
    list_count = len(re.findall(r"<(ul|ol)[^>]*>", html, re.IGNORECASE))
    if list_count >= 1:
        score += 5
        points["lists"] = list_count

    # Benefits/cards section
    if re.search(r"benefit|card|feature|why choose|reason", html, re.IGNORECASE):
        score += 5
        points["structured_benefits"] = "present"

    return min(max(score, 0), 100), points


def _score_readability(html: str) -> tuple[float, dict]:
    """Readability: sentence length, complexity indicators."""
    score = 60.0
    points = {}

    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()

    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    if not sentences:
        return 0, {"error": "no readable text"}

    avg_sentence_words = sum(len(s.split()) for s in sentences) / len(sentences)

    if 12 <= avg_sentence_words <= 22:
        score += 15
        points["avg_sentence"] = f"{avg_sentence_words:.0f} words (good)"
    elif avg_sentence_words < 12:
        score += 5
        points["avg_sentence"] = f"{avg_sentence_words:.0f} words (short)"
    else:
        score -= 5
        points["avg_sentence"] = f"{avg_sentence_words:.0f} words (too long)"

    # Short paragraphs (good for web)
    short_paras = len(re.findall(r"<p[^>]*>[^<]{10,200}</p>", html, re.IGNORECASE))
    if short_paras >= 3:
        score += 10
        points["short_paragraphs"] = short_paras
    else:
        points["short_paragraphs"] = f"{short_paras} (recommend 3+)"

    # Font sizing
    if re.search(r"font-size\s*:\s*(?:1[6789]|2[0-4])", html, re.IGNORECASE):
        score += 5
        points["font_size"] = "adequate"

    return min(max(score, 0), 100), points


def _score_mobile(html: str) -> tuple[float, dict]:
    """Mobile responsiveness: viewport meta, media queries."""
    score = 50.0
    points = {}

    if re.search(r'<meta\s+name=["\']viewport["\']', html, re.IGNORECASE):
        score += 25
        points["viewport_meta"] = "present"
    else:
        score -= 20
        points["viewport_meta"] = "MISSING — critical for mobile"

    if re.search(r"@media\s*(?:only\s+)?(?:screen\s+)?and", html, re.IGNORECASE):
        score += 15
        points["media_queries"] = "present"
    else:
        points["media_queries"] = "missing (add responsive breakpoints)"

    if re.search(r"grid-template-columns|flex-wrap|grid-template", html):
        score += 10
        points["responsive_layout"] = "present"

    return min(max(score, 0), 100), points


def _score_trust(html: str) -> tuple[float, dict]:
    """Trust signals: testimonials, guarantees, credentials."""
    score = 30.0
    points = {}

    trust_patterns = [
        (r"testimonial|review|rating|star", "testimonials"),
        (r"guarantee|warranty|money.back", "guarantee"),
        (r"licensed|insured|certified|accredited|bbb", "credentials"),
        (r"years.*experience|since\s+19\d{2}|since\s+20\d{2}", "experience"),
        (r"privacy|secure|ssl|encrypted", "security"),
        (r"award|recognized|featured|as.seen.on", "social_proof"),
        (r"contact.*us|phone|email|address", "contact_info"),
    ]

    found_signals = []
    for pattern, signal_name in trust_patterns:
        if re.search(pattern, html, re.IGNORECASE):
            score += 10
            found_signals.append(signal_name)

    points["signals_found"] = found_signals
    if len(found_signals) >= 5:
        score += 10
    elif len(found_signals) >= 3:
        score += 5

    return min(max(score, 0), 100), points


def _generate_recommendations(scores: dict, details: dict) -> list[str]:
    """Generate actionable recommendations from scorecard."""
    recs = []

    seo = details.get("seo_optimization", {})
    if seo.get("title_length") and "missing" in str(seo.get("title_length")):
        recs.append("Add a descriptive title tag (30-60 chars with target keyword)")
    if seo.get("meta_desc") and "missing" in str(seo.get("meta_desc")):
        recs.append("Add meta description (120-160 chars with CTA)")
    if seo.get("h1") and "missing" in str(seo.get("h1")):
        recs.append("Add a clear H1 heading that includes the target keyword")
    if "missing niche keyword" in str(seo.get("title_keyword", "")):
        recs.append("Include niche keyword in the title tag for SEO relevance")

    conv = details.get("conversion_quality", {})
    if "none found" in str(conv.get("cta_count", "")):
        recs.append("Add visible CTA buttons — primary, secondary, and floating")
    if "missing" in str(conv.get("form", "")):
        recs.append("Add a lead capture form with at minimum name, email/phone, and message fields")
    if conv.get("form_fields") and len(conv.get("form_fields", [])) < 3:
        recs.append("Expand form fields: add name, contact method, and description")

    depth = details.get("content_depth", {})
    wc = str(depth.get("word_count", ""))
    if "very thin" in wc or "thin" in wc:
        recs.append("Expand content — aim for 800+ words with detailed sections")

    mob = details.get("mobile_responsiveness", {})
    if "MISSING" in str(mob.get("viewport_meta", "")):
        recs.append("CRITICAL: Add viewport meta tag for mobile responsiveness")
    if "missing" in str(mob.get("media_queries", "")):
        recs.append("Add CSS media queries for responsive mobile layout")

    trust = details.get("trust_signals", {})
    signals = trust.get("signals_found", [])
    if len(signals) < 3:
        missing = [s for s in ["testimonials", "guarantee", "credentials", "social_proof"]
                   if s not in signals]
        if missing:
            recs.append(f"Add trust signals: {', '.join(missing[:3])}")

    return recs


def _tier_for(score: float) -> dict:
    """Convert numerical score to tier."""
    if score >= 80:
        return {"tier": "platinum", "label": "Production-ready — minor polish only"}
    elif score >= 65:
        return {"tier": "gold", "label": "Strong — address recommendations for A+"}
    elif score >= 50:
        return {"tier": "silver", "label": "Adequate — needs content & conversion work"}
    elif score >= 35:
        return {"tier": "bronze", "label": "Needs significant improvement before launch"}
    else:
        return {"tier": "lead", "label": "Early draft — fundamental rework required"}
