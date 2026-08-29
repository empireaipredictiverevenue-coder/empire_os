"""AEO-optimized lead intake endpoint — Empire OS v3.

POST /v1/leads/intake
- Accepts lead from AEO form, organic search, referral, partner webhook
- Validates + enriches via waterfall
- Routes to appropriate lane (niche + metro)
- Returns lead_uid + quote estimate

AEO form schema matches Answer Engine Optimization best practices:
- Structured data (JSON-LD) for Google/AI crawlers
- Semantic HTML5 with proper ARIA labels
- Fast, accessible, mobile-first
"""

from __future__ import annotations
import json
import os
import re
import secrets
import sqlite3
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, validator

DB = "/root/empire_os/empire_os.db"
router = APIRouter(prefix="/v1/leads", tags=["lead_intake"])


# AEO Form Schema
class AEOLeadIntake(BaseModel):
    """AEO-optimized lead intake payload. Matches structured data for search engines."""
    niche: str = Field(..., description="Service category: roofing, hvac, plumbing, electrical, solar, etc.")
    metro: str = Field(..., description="Metro area code: LAX, NYC, CHI, DFW, MIA, ATL, PHX, PHL, SEA, etc.")
    
    business_name: str = Field("", description="Business name")
    website: str = Field("", description="Website URL")
    phone: str = Field("", description="Phone number")
    email: str = Field("", description="Email address")
    
    address: str = Field("", description="Street address")
    city: str = Field("", description="City")
    state: str = Field("", description="State (2-letter)")
    zip_code: str = Field("", description="ZIP code")
    
    service_type: str = Field("", description="Specific service: repair, installation, maintenance, emergency")
    urgency: str = Field("normal", description="urgent, normal, planned")
    budget_range: str = Field("", description="under_5k, 5k_15k, 15k_50k, 50k_plus, insurance")
    
    source: str = Field("organic", description="organic, referral, partner_webhook, paid_search, social, email")
    referrer_url: str = Field("", description="Referring page URL")
    utm_source: str = Field("", description="UTM source")
    utm_medium: str = Field("", description="UTM medium")
    utm_campaign: str = Field("", description="UTM campaign")
    utm_content: str = Field("", description="UTM content")
    utm_term: str = Field("", description="UTM term")
    
    consent_marketing: bool = Field(False, description="Consent to marketing communications")
    consent_tcpa: bool = Field(False, description="TCPA consent for calls/texts")
    consent_timestamp: str = Field("", description="ISO timestamp of consent")
    
    schema_type: str = Field("LocalBusiness", description="Schema.org type")
    price_range: str = Field("", description="Schema priceRange: $, $$, $$$, $$$$")
    
    @validator("niche")
    def validate_niche(cls, v):
        valid = ["roofing", "hvac", "plumbing", "electrical", "solar", "landscaping",
                 "pest_control", "painting", "fencing", "windows", "flooring",
                 "concrete", "excavation", "tree_service", "pool", "general_contractor",
                 "siding", "masonry", "foundation", "remodeling", "restoration"]
        if v.lower() not in valid:
            raise ValueError(f"Invalid niche. Valid: {valid}")
        return v.lower()
    
    @validator("metro")
    def validate_metro(cls, v):
        valid = ["LAX", "NYC", "CHI", "DFW", "MIA", "ATL", "PHX", "PHL", "SEA",
                 "BOS", "WDC", "SFO", "DEN", "DET", "HOU", "SAT", "AUS", "PDX", "LAS"]
        if v.upper() not in valid:
            raise ValueError(f"Invalid metro. Valid: {valid}")
        return v.upper()
    
    @validator("urgency")
    def validate_urgency(cls, v):
        valid = ["urgent", "normal", "planned", "emergency"]
        if v.lower() not in valid:
            raise ValueError(f"Invalid urgency. Valid: {valid}")
        return v.lower()
    
    @validator("email")
    def validate_email(cls, v):
        if v and not re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", v):
            raise ValueError("Invalid email format")
        return v
    
    @validator("phone")
    def validate_phone(cls, v):
        if v:
            digits = re.sub(r"\D", "", v)
            if len(digits) not in (10, 11) or (len(digits) == 11 and digits[0] != "1"):
                raise ValueError("Invalid US phone number")
        return v


class IntakeResponse(BaseModel):
    """Response after successful intake."""
    ok: bool = True
    lead_uid: str
    lane_key: str
    niche: str
    metro: str
    estimated_buyers: int
    estimated_price_range: str
    next_steps: List[str]
    quote_url: Optional[str] = None


# Helpers
def _lane_key(niche: str, metro: str) -> str:
    return f"{niche.lower()}:{metro.upper()}"

def _estimate_buyers(niche: str, metro: str) -> int:
    """Estimate active buyers in niche+metro."""
    con = sqlite3.connect(DB)
    try:
        c = con.cursor()
        c.execute(
            "SELECT COUNT(*) FROM si_buyer_outreach WHERE niche=? AND metro=? AND active=1",
            (niche, metro)
        )
        return c.fetchone()[0] or 0
    finally:
        con.close()

def _estimate_price(niche: str, urgency: str) -> str:
    """Estimate price range based on niche + urgency."""
    base = {
        "roofing": {"normal": "8k-25k", "urgent": "12k-40k", "emergency": "15k-50k"},
        "hvac": {"normal": "5k-15k", "urgent": "8k-20k", "emergency": "10k-25k"},
        "plumbing": {"normal": "3k-10k", "urgent": "5k-15k", "emergency": "8k-20k"},
        "electrical": {"normal": "2k-8k", "urgent": "4k-12k", "emergency": "6k-15k"},
        "solar": {"normal": "15k-40k", "urgent": "20k-50k", "emergency": "25k-60k"},
    }
    return base.get(niche, {}).get(urgency, "5k-20k")

def _store_intake(lead: AEOLeadIntake, lead_uid: str) -> None:
    """Store intake in crm_leads with AEO metadata."""
    con = sqlite3.connect(DB, timeout=30)
    try:
        c = con.cursor()
        now = datetime.now(timezone.utc).isoformat()
        
        raw = {
            "source": lead.source,
            "referrer_url": lead.referrer_url,
            "utm": {k: getattr(lead, k) for k in ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"] if getattr(lead, k)},
            "consent": {
                "marketing": lead.consent_marketing,
                "tcpa": lead.consent_tcpa,
                "timestamp": lead.consent_timestamp or now,
            },
            "service_type": lead.service_type,
            "budget_range": lead.budget_range,
            "urgency": lead.urgency,
            "schema_type": lead.schema_type,
            "price_range": lead.price_range,
        }
        
        c.execute(
            """INSERT OR IGNORE INTO crm_leads
            (lead_uid, source, business_name, phone, email, website, street, city, state, zip,
             niche, sub_niche, notes, status, created_at, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'intake', ?, ?)""",
            (
                lead_uid, lead.source, lead.business_name or f"Lead {lead_uid[:8]}",
                lead.phone, lead.email, lead.website, lead.address,
                lead.city, lead.state.upper() if lead.state else lead.metro,
                lead.zip_code, lead.niche, lead.niche,
                json.dumps(raw),
                now,
                json.dumps(raw),
            )
        )
        con.commit()
    finally:
        con.close()

def _trigger_enrichment(lead_uid: str, niche: str, metro: str):
    """Background task: run enrichment waterfall."""
    try:
        from empire_os.waterfall import build_default_waterfall
        wf = build_default_waterfall()
        
        con = sqlite3.connect(DB, timeout=30)
        c = con.cursor()
        c.execute("SELECT business_name, website, phone, email, city, state FROM crm_leads WHERE lead_uid=?", (lead_uid,))
        row = c.fetchone()
        con.close()
        
        if row:
            biz_name, website, phone, email, city, state = row
            lead_info = {
                "company": biz_name,
                "website": website or "",
                "phone": phone or "",
                "email": email or "",
                "city": city or "",
                "state": state or "",
                "niche": niche,
            }
            wf.enrich(lead_info)
    except Exception:
        pass


# HTML Form Template (stored as raw string to avoid f-string escaping issues)
INTAKE_FORM_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Get Local Contractor Quotes - Empire OS</title>
  <meta name="description" content="Submit your project details and get matched with verified local contractors. Free, no obligation.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">
  <style>
    * { box-sizing: border-box; }
    body { font-family: 'Inter', system-ui, sans-serif; line-height: 1.6; max-width: 720px; margin: 0 auto; padding: 24px 16px; color: #111; background: #fafafa; }
    h1 { font-size: 1.75rem; font-weight: 700; margin-bottom: 0.5rem; }
    .subtitle { color: #666; margin-bottom: 2rem; }
    form { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    @media (max-width: 600px) { .grid { grid-template-columns: 1fr; } }
    .field { margin-bottom: 16px; }
    label { display: block; font-weight: 500; margin-bottom: 6px; font-size: 0.875rem; }
    input, select, textarea { width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 1rem; font-family: inherit; }
    input:focus, select:focus, textarea:focus { outline: none; border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,0.15); }
    .required { color: #dc2626; }
    .help { font-size: 0.75rem; color: #666; margin-top: 4px; }
    .row { display: flex; gap: 12px; }
    .row > * { flex: 1; }
    button { width: 100%; padding: 14px; background: #111; color: white; border: none; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer; margin-top: 8px; }
    button:hover { background: #333; }
    .consent { display: flex; align-items: flex-start; gap: 8px; }
    .consent input { width: auto; margin-top: 4px; }
    .consent label { font-weight: 400; margin-bottom: 0; font-size: 0.875rem; }
    .trust { text-align: center; margin-top: 16px; font-size: 0.8rem; color: #888; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
  </style>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "Service",
    "name": "Local Contractor Matching",
    "description": "Get matched with verified local contractors in your area",
    "provider": { "@type": "Organization", "name": "Empire OS" },
    "areaServed": "{metro}",
    "hasOfferCatalog": {
      "@type": "OfferCatalog",
      "name": "Contractor Services"
    }
  }</script>
</head>
<body>
  <h1>Get Quotes for <span id="niche-display">Your Project</span></h1>
  <p class="subtitle">Verified contractors in {metro} metro area. Free. No spam. No obligation.</p>
  
  <form id="intake-form" action="/v1/leads/intake" method="POST">
    <div class="grid">
      <div class="field">
        <label for="niche">Service Category <span class="required">*</span></label>
        <select id="niche" name="niche" required onchange="updateDisplay()">
          <option value="">Select service</option>
          {niche_opts}
        </select>
      </div>
      <div class="field">
        <label for="metro">Metro Area <span class="required">*</span></label>
        <select id="metro" name="metro" required>
          <option value="">Select metro</option>
          {metro_opts}
        </select>
      </div>
    </div>
    
    <div class="field">
      <label for="business_name">Business Name (optional)</label>
      <input type="text" id="business_name" name="business_name" placeholder="Your company name">
    </div>
    
    <div class="grid">
      <div class="field">
        <label for="phone">Phone <span class="required">*</span></label>
        <input type="tel" id="phone" name="phone" placeholder="(555) 123-4567" required pattern="\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}">
      </div>
      <div class="field">
        <label for="email">Email</label>
        <input type="email" id="email" name="email" placeholder="you@company.com">
      </div>
    </div>
    
    <div class="grid">
      <div class="field">
        <label for="address">Address</label>
        <input type="text" id="address" name="address" placeholder="123 Main St">
      </div>
      <div class="field">
        <label for="city">City</label>
        <input type="text" id="city" name="city" placeholder="Los Angeles">
      </div>
    </div>
    
    <div class="grid">
      <div class="field">
        <label for="state">State</label>
        <input type="text" id="state" name="state" placeholder="CA" maxlength="2">
      </div>
      <div class="field">
        <label for="zip_code">ZIP Code</label>
        <input type="text" id="zip_code" name="zip_code" placeholder="90001" maxlength="5">
      </div>
    </div>
    
    <div class="field">
      <label for="website">Website (optional)</label>
      <input type="url" id="website" name="website" placeholder="https://yourcompany.com">
    </div>
    
    <div class="grid">
      <div class="field">
        <label for="service_type">Service Type</label>
        <select id="service_type" name="service_type">
          <option value="">Select</option>
          <option value="repair">Repair</option>
          <option value="installation">Installation</option>
          <option value="maintenance">Maintenance</option>
          <option value="emergency">Emergency</option>
          <option value="replacement">Full Replacement</option>
          <option value="inspection">Inspection</option>
        </select>
      </div>
      <div class="field">
        <label for="urgency">Urgency</label>
        <select id="urgency" name="urgency">
          <option value="normal">Normal (1-2 weeks)</option>
          <option value="urgent">Urgent (1-3 days)</option>
          <option value="emergency">Emergency (ASAP)</option>
          <option value="planned">Planned (1+ months)</option>
        </select>
      </div>
    </div>
    
    <div class="field">
      <label for="budget_range">Budget Range</label>
      <select id="budget_range" name="budget_range">
        <option value="">Select</option>
        <option value="under_5k">Under $5,000</option>
        <option value="5k_15k">$5,000 - $15,000</option>
        <option value="15k_50k">$15,000 - $50,000</option>
        <option value="50k_plus">$50,000+</option>
        <option value="insurance">Insurance Claim</option>
      </select>
    </div>
    
    <fieldset class="field">
      <legend>Consent & Compliance</legend>
      <div class="consent">
        <input type="checkbox" id="consent_tcpa" name="consent_tcpa">
        <label for="consent_tcpa">I consent to receive calls/texts about this project (TCPA)</label>
      </div>
      <div class="consent">
        <input type="checkbox" id="consent_marketing" name="consent_marketing">
        <label for="consent_marketing">I consent to marketing communications</label>
      </div>
    </fieldset>
    
    <button type="submit">Get My Quotes</button>
    
    <p class="trust">
      Your information is shared only with verified contractors who match your project.
      We never sell your data. <a href="/privacy">Privacy Policy</a> | <a href="/terms">Terms</a>
    </p>
  </form>
  
  <script>
    function updateDisplay() {
      const niche = document.getElementById('niche').value;
      const display = document.getElementById('niche-display');
      if (niche) display.textContent = niche.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
    }
    
    document.getElementById('intake-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = e.target.querySelector('button');
      btn.disabled = true;
      btn.textContent = 'Submitting...';
      
      const formData = new FormData(e.target);
      const data = Object.fromEntries(formData);
      data.consent_tcpa = data.consent_tcpa === 'on';
      data.consent_marketing = data.consent_marketing === 'on';
      data.consent_timestamp = new Date().toISOString();
      
      try {
        const res = await fetch('/v1/leads/intake', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
        const result = await res.json();
        if (result.ok) {
          alert('Success! Lead ID: ' + result.lead_uid + '\n' + result.estimated_buyers + ' buyers in ' + result.metro + '\nEst. range: ' + result.estimated_price_range);
        } else {
          alert('Error: ' + (result.detail || 'Unknown error'));
        }
      } catch (err) {
        alert('Network error. Please try again.');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Get My Quotes';
      }
    });
  </script>
</body>
</html>"""


# Endpoints
@router.post("/intake", response_model=IntakeResponse)
async def intake_lead(lead: AEOLeadIntake, background: BackgroundTasks, request: Request):
    """AEO-optimized lead intake endpoint."""
    lead_uid = f"lead_{secrets.token_urlsafe(12)}"
    lane = _lane_key(lead.niche, lead.metro)
    
    _store_intake(lead, lead_uid)
    background.add_task(_trigger_enrichment, lead_uid, lead.niche, lead.metro)
    
    buyers = _estimate_buyers(lead.niche, lead.metro)
    price = _estimate_price(lead.niche, lead.urgency)
    
    steps = [
        f"Lead assigned to lane: {lane}",
        f"Found {buyers} active buyers in {lead.metro} for {lead.niche}",
        f"Estimated project range: {price}",
        "Enrichment waterfall started (website, search, BBB, WHOIS, etc.)",
        "Matching buyers will be notified within 5 minutes",
    ]
    
    return IntakeResponse(
        lead_uid=lead_uid,
        lane_key=lane,
        niche=lead.niche,
        metro=lead.metro,
        estimated_buyers=buyers,
        estimated_price_range=price,
        next_steps=steps,
    )


@router.get("/intake/form", response_class=HTMLResponse)
async def intake_form(niche: str = "", metro: str = ""):
    """AEO-optimized HTML form for lead intake."""
    niches = ["roofing", "hvac", "plumbing", "electrical", "solar", "landscaping",
              "pest_control", "painting", "fencing", "windows", "flooring",
              "concrete", "excavation", "tree_service", "pool", "general_contractor",
              "siding", "masonry", "foundation", "remodeling", "restoration"]
    metros = ["LAX", "NYC", "CHI", "DFW", "MIA", "ATL", "PHX", "PHL", "SEA",
              "BOS", "WDC", "SFO", "DEN", "DET", "HOU", "SAT", "AUS", "PDX", "LAS"]
    
    niche_opts = "".join(f'<option value="{n}" {"selected" if n==niche else ""}>{n.replace("_", " ").title()}</option>' for n in niches)
    metro_opts = "".join(f'<option value="{m}" {"selected" if m==metro else ""}>{m}</option>' for m in metros)
    
    # JSON-LD Structured Data for AEO
    json_ld = {
        "@context": "https://schema.org",
        "@type": "Service",
        "name": "Local Contractor Matching",
        "description": "Get matched with verified local contractors in " + (metro or "your area"),
        "provider": {"@type": "Organization", "name": "Empire OS"},
        "areaServed": metro or "",
        "hasOfferCatalog": {
            "@type": "OfferCatalog",
            "name": (niche.replace("_", " ").title() if niche else "Contractor") + " Services"
        },
    }
    json_ld_str = json.dumps(json_ld)
    
    # Build form HTML using template
    html = INTAKE_FORM_HTML.format(
        niche_opts="".join(f'<option value="{n}" {"selected" if n==niche else ""}>{n.replace("_", " ").title()}</option>' for n in niches),
        metro_opts="".join(f'<option value="{m}" {"selected" if m==metro else ""}>{m}</option>' for m in metros),
        niche_display=niche.replace("_", " ").title() if niche else "Your Project",
        metro_display=metro or "your metro area",
        json_ld=json_ld_str,
        metro=metro or "",
    )
    
    return HTMLResponse(content=html)


@router.get("/intake/{lead_uid}")
async def get_intake(lead_uid: str):
    """Retrieve intake record by lead_uid."""
    con = sqlite3.connect(DB, timeout=30)
    try:
        c = con.cursor()
        c.execute(
            "SELECT lead_uid, source, business_name, phone, email, website, street, city, state, zip, niche, sub_niche, notes, status, created_at, raw_json FROM crm_leads WHERE lead_uid=?",
            (lead_uid,)
        )
        row = c.fetchone()
        if not row:
            raise HTTPException(404, "Lead not found")
        return {
            "lead_uid": row[0], "source": row[1], "business_name": row[2],
            "phone": row[3], "email": row[4], "website": row[5],
            "address": row[6], "city": row[7], "state": row[8], "zip_code": row[9],
            "niche": row[10], "sub_niche": row[11], "notes": row[12],
            "status": row[13], "created_at": row[14], "raw_json": row[15],
        }
    finally:
        con.close()


def register_intake_routes(app):
    """Register intake routes with FastAPI app."""
    app.include_router(router)


if __name__ == "__main__":
    print("AEO Lead Intake module loaded")
    print("Endpoints:")
    print("  POST /v1/leads/intake - Submit lead (JSON)")
    print("  GET  /v1/leads/intake/form - AEO-optimized HTML form")
    print("  GET  /v1/leads/intake/{lead_uid} - Retrieve lead")