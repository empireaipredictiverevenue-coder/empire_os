#!/usr/bin/env python3
"""
Data Normalizer — Empire OS v3
==============================
Cleans, validates, enriches, and deduplicates leads from ANY source.
Single source of truth for lead quality before hitting the pipeline.

Usage:
    from empire_os.data_normalizer import normalize_lead, normalize_batch
    
    clean = normalize_lead(raw_candidate)
    # clean is a dict with validated/normalized fields + quality_score
"""

import re, json, hashlib, phonenumbers, email_validator
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from urllib.parse import urlparse
import tldextract

# ──────────────────────────────────────────────────────────────────────
# Field Validators
# ──────────────────────────────────────────────────────────────────────

# Email
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
ROLE_EMAILS = {"info","sales","contact","hello","admin","office","support",
               "hello","team","hr","careers","jobs","billing","accounts"}

# Phone (US-focused, international capable)
PHONE_RE = re.compile(r"^\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$")

# Business name cleanup
BAD_NAME_TOKENS = {"llc","inc","inc.","corp","corp.","corporation","co","co.",
                   "ltd","ltd.","limited","lp","l.p.","pllc","pllc.",
                   "pc","p.c.","pa","p.a.","dba","d/b/a","&","and","the",
                   "services","service","solutions","group","associates",
                   "partners","enterprises","enterprise","company","co"}

# Niche taxonomy (canonical)
CANONICAL_NICHES = {
    "roofing": ["roofing","roofer","roof repair","shingle","gutter","skylight"],
    "hvac": ["hvac","air conditioning","ac repair","furnace","heating","cooling","heat pump"],
    "plumbing": ["plumbing","plumber","drain","sewer","pipe","water heater","leak"],
    "electrical": ["electrician","electrical","wiring","panel","outlet","circuit"],
    "solar": ["solar","pv","photovoltaic","solar panel","solar installation"],
    "landscaping": ["landscaping","landscape","lawn","irrigation","sprinkler","tree service","arborist"],
    "painting": ["painter","painting","interior paint","exterior paint","staining"],
    "fencing": ["fence","fencing","gate","vinyl fence","wood fence","chain link"],
    "windows": ["window","window replacement","window installation","double pane"],
    "flooring": ["flooring","floor","hardwood","tile","carpet","epoxy","laminate"],
    "concrete": ["concrete","cement","driveway","patio","foundation","masonry"],
    "excavation": ["excavation","excavating","grading","site prep","earthwork"],
    "tree": ["tree service","tree removal","arborist","stump grinding","tree trimming"],
    "pool": ["pool","pool service","pool repair","pool maintenance","spa"],
    "cleaning": ["cleaning","janitorial","commercial cleaning","office cleaning","pressure washing"],
    "pest_control": ["pest control","exterminator","termite","rodent","bed bug","wildlife removal"],
    "roofing": ["roofing","roofer","roof repair"],
    "masonry": ["masonry","brick","stone","chimney","tuckpointing"],
    "insulation": ["insulation","spray foam","attic insulation","weatherization"],
    "gutters": ["gutter","gutters","gutter cleaning","gutter guard","downspout"],
    "siding": ["siding","vinyl siding","fiber cement","hardie","hardie board"],
    "foundation": ["foundation","foundation repair","basement waterproofing","crawl space"],
    "waterproofing": ["waterproofing","basement waterproofing","french drain","sump pump"],
    "remodeling": ["remodeling","renovation","home addition","kitchen remodel","bath remodel"],
    "handyman": ["handyman","home repair","property maintenance"],
    "appliance": ["appliance repair","appliance installation","hvac appliance"],
    "garage_door": ["garage door","garage door repair","garage door opener"],
    "locksmith": ["locksmith","lock","rekey","access control"],
    "moving": ["moving","movers","relocation","long distance moving"],
    "storage": ["self storage","storage unit","warehouse storage"],
    "trucking": ["trucking","freight","logistics","transport","shipping"],
    "towing": ["towing","roadside assistance","vehicle recovery"],
    "auto_repair": ["auto repair","mechanic","car repair","brake","transmission"],
    "auto_body": ["auto body","collision repair","paintless dent","auto painting"],
    "tire": ["tire","tire shop","wheel alignment","tire rotation"],
    "glass": ["auto glass","windshield replacement","window tinting"],
    "detailing": ["auto detailing","car wash","ceramic coating","paint correction"],
}

# ──────────────────────────────────────────────────────────────────────
# Data Classes
# ──────────────────────────────────────────────────────────────────────

@dataclass
class NormalizedLead:
    # Core identity
    name: str
    email: str
    phone: str
    website: str
    
    # Location
    street: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    metro: str = ""
    country: str = "US"
    
    # Classification
    niche: str = ""
    sub_niche: str = ""
    niche_confidence: float = 0.0
    
    # Source tracking
    source: str = ""
    source_url: str = ""
    raw_source: str = ""
    
    # Quality metrics
    quality_score: int = 0          # 0-100
    email_quality: str = ""         # role/personal/invalid
    phone_quality: str = ""         # valid/invalid/mobile/landline
    name_quality: str = ""          # clean/generic/suspicious
    
    # Dedupe
    dedupe_key: str = ""            # hash for dedupe
    
    # Enrichment hooks
    cortex_score: int = 0
    synthetic_intent: str = ""
    synthetic_fit: float = 0.0
    omega_tier: str = "D"
    aeo_priority: int = 0
    
    # Raw preservation
    raw: dict = None
    
    def to_dict(self) -> dict:
        d = asdict(self)
        if self.raw:
            d["raw"] = self.raw
        return d

# ──────────────────────────────────────────────────────────────────────
# Normalization Functions
# ──────────────────────────────────────────────────────────────────────

def clean_name(raw: str) -> Tuple[str, str]:
    """Clean business name, return (clean_name, quality_flag)."""
    if not raw:
        return "", "empty"
    
    # Remove common suffixes
    words = raw.strip().split()
    cleaned = []
    for w in words:
        lw = w.lower().strip(".,")
        if lw not in BAD_NAME_TOKENS:
            cleaned.append(w)
    
    clean = " ".join(cleaned).strip()
    
    # Quality assessment
    if not clean:
        return raw, "empty"
    if len(clean) < 3:
        return clean, "too_short"
    if clean.lower() in ("business","company","services","solutions","group"):
        return clean, "generic"
    if any(c.isdigit() for c in clean[:3]):
        return clean, "starts_with_number"
    return clean, "clean"

def normalize_email(raw: str) -> Tuple[str, str]:
    """Validate and normalize email. Returns (normalized, quality)."""
    if not raw:
        return "", "missing"
    
    raw = raw.strip().lower()
    if not EMAIL_RE.match(raw):
        return raw, "invalid_format"
    
    local, domain = raw.split("@", 1)
    
    # Check if role email
    if local in ROLE_EMAILS:
        return raw, "role"
    
    # Check for disposable/temporary domains
    disposable = {"mailinator.com","guerrillamail.com","10minutemail.com",
                  "tempmail.com","throwawaymail.com","fakeinbox.com"}
    if domain in disposable:
        return raw, "disposable"
    
    # Check for free providers
    free_providers = {"gmail.com","yahoo.com","hotmail.com","outlook.com",
                      "aol.com","icloud.com","protonmail.com","proton.me"}
    if domain in free_providers:
        return raw, "free"
    
    return raw, "business"

def normalize_phone(raw: str, country: str = "US") -> Tuple[str, str]:
    """Parse and format phone. Returns (e164_format, quality)."""
    if not raw:
        return "", "missing"
    
    try:
        parsed = phonenumbers.parse(raw, country)
        if not phonenumbers.is_valid_number(parsed):
            return raw, "invalid"
        
        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        num_type = phonenumbers.number_type(parsed)
        
        type_map = {
            phonenumbers.PhoneNumberType.MOBILE: "mobile",
            phonenumbers.PhoneNumberType.FIXED_LINE: "landline",
            phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "fixed_or_mobile",
            phonenumbers.PhoneNumberType.TOLL_FREE: "toll_free",
            phonenumbers.PhoneNumberType.PREMIUM_RATE: "premium",
            phonenumbers.PhoneNumberType.SHARED_COST: "shared_cost",
            phonenumbers.PhoneNumberType.VOIP: "voip",
            phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "personal",
            phonenumbers.PhoneNumberType.PAGER: "pager",
            phonenumbers.PhoneNumberType.UAN: "uan",
            phonenumbers.PhoneNumberType.VOICEMAIL: "voicemail",
        }
        quality = type_map.get(num_type, "unknown")
        return e164, quality
    except Exception:
        return raw, "parse_error"

def normalize_website(raw: str) -> str:
    """Extract clean domain from URL."""
    if not raw:
        return ""
    if not raw.startswith(("http://","https://")):
        raw = "https://" + raw
    try:
        parsed = urlparse(raw)
        domain = parsed.netloc.lower().replace("www.", "")
        # Remove port
        if ":" in domain:
            domain = domain.split(":")[0]
        return domain
    except Exception:
        return ""

def extract_address_components(raw: str) -> Dict[str, str]:
    """Best-effort address parsing. Returns dict with street, city, state, zip."""
    out = {"street": "", "city": "", "state": "", "zip": ""}
    if not raw:
        return out
    
    # Try to extract ZIP
    zip_match = re.search(r"\b\d{5}(?:-\d{4})?\b", raw)
    if zip_match:
        out["zip"] = zip_match.group()
    
    # Try to extract state (2-letter)
    state_match = re.search(r"\b([A-Z]{2})\b", raw)
    if state_match:
        out["state"] = state_match.group(1)
    
    # The rest is street/city - best effort
    cleaned = raw
    if out["zip"]:
        cleaned = cleaned.replace(out["zip"], "")
    if out["state"]:
        cleaned = cleaned.replace(out["state"], "")
    
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    if len(parts) >= 2:
        out["city"] = parts[-2].strip()
        out["street"] = ", ".join(parts[:-2]).strip() if len(parts) > 2 else parts[0].strip()
    elif len(parts) == 1:
        out["street"] = parts[0].strip()
    
    return out

def infer_niche(text: str) -> Tuple[str, str, float]:
    """Infer niche from text. Returns (canonical_niche, sub_niche, confidence)."""
    if not text:
        return "", "", 0.0
    
    text_l = text.lower()
    best_niche, best_sub, best_score = "", "", 0.0
    
    for niche, keywords in CANONICAL_NICHES.items():
        for kw in keywords:
            if kw in text_l:
                score = len(kw) / len(text_l) * 100  # simple heuristic
                if score > best_score:
                    best_score = score
                    best_niche = niche
                    best_sub = kw
    
    return best_niche, best_sub, min(1.0, best_score / 50.0)

def generate_dedupe_key(lead: NormalizedLead) -> str:
    """Generate stable hash for deduplication."""
    parts = [
        lead.name.lower().strip(),
        lead.email.lower().strip(),
        lead.phone.strip(),
        lead.website.lower().strip(),
        lead.city.lower().strip(),
        lead.state.upper().strip(),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]

# ──────────────────────────────────────────────────────────────────────
# Main Normalizer
# ──────────────────────────────────────────────────────────────────────

def normalize_lead(raw: Any) -> NormalizedLead:
    """
    Normalize a raw lead candidate (dict, LeadCandidate, or object with attrs).
    Returns NormalizedLead with all fields cleaned, validated, enriched.
    """
    # Extract fields from various input types
    if isinstance(raw, dict):
        d = raw
    else:
        d = {}
        for attr in ["name","email","phone","website","street","city","state",
                     "zip","metro","niche","sub_niche","source","source_url",
                     "details","lead_score","url","raw"]:
            if hasattr(raw, attr):
                d[attr] = getattr(raw, attr)
    
    # Normalize core fields
    name, name_qual = clean_name(d.get("name", ""))
    email, email_qual = normalize_email(d.get("email", ""))
    phone, phone_qual = normalize_phone(d.get("phone", ""), d.get("country", "US"))
    website = normalize_website(d.get("website", d.get("url", "")))
    
    # Address
    addr_raw = " ".join(filter(None, [
        d.get("street",""), d.get("city",""), d.get("state",""), d.get("zip","")
    ]))
    addr = extract_address_components(addr_raw)
    
    # Niche inference
    niche_text = " ".join(filter(None, [
        d.get("niche",""), d.get("sub_niche",""), d.get("details",""),
        d.get("source",""), website
    ]))
    niche, sub_niche, niche_conf = infer_niche(niche_text)
    
    # Build normalized lead
    lead = NormalizedLead(
        name=name,
        email=email,
        phone=phone,
        website=website,
        street=addr["street"],
        city=addr["city"],
        state=addr["state"],
        zip_code=addr["zip"],
        metro=d.get("metro", ""),
        niche=niche,
        sub_niche=sub_niche,
        niche_confidence=niche_conf,
        source=d.get("source", ""),
        source_url=d.get("source_url", d.get("url", "")),
        raw_source=d.get("raw_source", ""),
        name_quality=name_qual,
        email_quality=email_qual,
        phone_quality=phone_qual,
        raw=d.get("raw", d),
    )
    
    # Dedupe key
    lead.dedupe_key = generate_dedupe_key(lead)
    
    # Quality score (0-100)
    lead.quality_score = calculate_quality_score(lead)
    
    return lead

def calculate_quality_score(lead: NormalizedLead) -> int:
    """Composite quality score 0-100."""
    score = 0
    
    # Email (30 pts)
    if lead.email_quality == "business": score += 30
    elif lead.email_quality == "free": score += 20
    elif lead.email_quality == "role": score += 10
    
    # Phone (20 pts)
    if lead.phone_quality in ("mobile","landline"): score += 20
    elif lead.phone_quality == "fixed_or_mobile": score += 15
    elif lead.phone_quality == "voip": score += 10
    
    # Name (15 pts)
    if lead.name_quality == "clean": score += 15
    elif lead.name_quality == "generic": score += 5
    
    # Website (15 pts)
    if lead.website: score += 15
    
    # Address completeness (10 pts)
    addr_parts = sum(1 for x in [lead.street, lead.city, lead.state, lead.zip_code] if x)
    score += min(10, addr_parts * 3)
    
    # Niche confidence (10 pts)
    score += int(lead.niche_confidence * 10)
    
    return min(100, max(0, score))

def normalize_batch(leads: List[Any]) -> List[NormalizedLead]:
    """Normalize a batch, deduplicate by dedupe_key."""
    seen = {}
    for raw in leads:
        norm = normalize_lead(raw)
        key = norm.dedupe_key
        if key not in seen or seen[key].quality_score < norm.quality_score:
            seen[key] = norm
    return list(seen.values())

# ──────────────────────────────────────────────────────────────────────
# Pipeline Integration
# ──────────────────────────────────────────────────────────────────────

def pipeline_normalize(candidates: List[Any]) -> List[NormalizedLead]:
    """
    Full pipeline: normalize → dedupe → quality filter → enrich.
    Returns leads ready for /v1/leads/direct intake.
    """
    # 1. Normalize all
    normalized = normalize_batch(candidates)
    
    # 2. Filter by quality threshold
    qualified = [l for l in normalized if l.quality_score >= 40]
    
    # 3. Sort by quality (highest first)
    qualified.sort(key=lambda x: x.quality_score, reverse=True)
    
    return qualified

# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_leads = [
            {"name": "ABC Roofing LLC", "email": "info@abcroof.com", "phone": "555-123-4567",
             "website": "abcroof.com", "niche": "roofing", "metro": "DFW", "source": "universal_scraper"},
            {"name": "John's HVAC", "email": "john@gmail.com", "phone": "+1 214 555 0199",
             "website": "", "niche": "hvac", "metro": "DFW", "source": "searxng"},
            {"name": "  Plumbing Solutions Inc.  ", "email": "sales@plumbco.com", "phone": "invalid",
             "website": "http://plumbco.com", "niche": "plumbing", "metro": "LAX", "source": "reddit"},
        ]
        
        results = pipeline_normalize(test_leads)
        for r in results:
            print(json.dumps(r.to_dict(), indent=2))
