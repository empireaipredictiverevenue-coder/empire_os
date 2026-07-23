"""
Empire OS v3 — Lead Source Utilities
====================================
Shared utilities for lead sources: niche inference, keywords, etc.
No circular imports - pure utilities.
"""

import re
from typing import Tuple

# ──────────────────────────────────────────────────────────────────────
# Niche Keywords & Inference
# ──────────────────────────────────────────────────────────────────────

NICHE_KEYWORDS = {
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

def infer_niche(text: str) -> Tuple[str, str, float]:
    """
    Infer niche from text.
    Returns: (canonical_niche, sub_niche, confidence)
    """
    if not text:
        return "", "", 0.0
    
    text_l = text.lower()
    best_niche, best_sub, best_score = "", "", 0.0
    
    for niche, keywords in NICHE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_l:
                # Score based on keyword length and position
                score = len(kw) / max(len(text), 1) * 100
                if score > best_score:
                    best_score = score
                    best_niche = niche
                    best_sub = kw
    
    confidence = min(1.0, best_score / 50.0)
    return best_niche, best_sub, confidence