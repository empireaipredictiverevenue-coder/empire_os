"""Ad-Gen Scanner Module — probes competitor AEO pages & landing pages.

For each tort type, discovers competitors and scrapes their content for
analysis by the Judge and Architect modules.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("adgen-scanner")

# ── Known competitor domains ─────────────────────────────────────────

COMPETITOR_DOMAINS = {
    # Mass Torts
    "camp_lejeune": [
        "camplejeunejustice.com",
        "camp-lejeune-lawsuit.com",
        "drugwatch.com/camp-lejeune",
        "tor-hoerman.com/camp-lejeune",
        "levinlaw.com/camp-lejeune",
    ],
    "roundup": [
        "rounduplegals.com",
        "rounduplawsuit.com",
        "drugwatch.com/roundup",
        "tor-hoerman.com/roundup",
        "consumernotice.org/roundup",
    ],
    "paraquat": [
        "paraquat-lawyer.com",
        "paraquatlawsuit.net",
        "drugwatch.com/paraquat",
        "tor-hoerman.com/paraquat",
    ],
    "afff": [
        "afff-firefighting-foam-lawsuit.com",
        "affflawsuit.com",
        "drugwatch.com/afff",
        "pfaswaterlawsuit.com",
    ],
    "zantac": [
        "zantac-lawsuits.com",
        "zantaclawsuit.com",
        "drugwatch.com/zantac",
        "zantacclaimscenter.com",
    ],
    "ozempic": [
        "ozempiclawsuits.com",
        "ozempic-gastroparesis-lawsuit.com",
        "drugwatch.com/ozempic",
    ],
    # Home Services
    "electrical": [
        "angi.com/electrical",
        "thumbtack.com/electrical",
        "hometownelectricians.com",
        "mrelectric.com",
    ],
    "hvac": [
        "angi.com/hvac",
        "thumbtack.com/hvac",
        "hvac.com",
        "carrier.com/residential",
        "trane.com/residential",
    ],
    "plumbing": [
        "angi.com/plumbing",
        "thumbtack.com/plumbing",
        "rooter.com",
        "rotorooter.com",
        "misterplumber.com",
    ],
    "roofing": [
        "angi.com/roofing",
        "thumbtack.com/roofing",
        "roofingcalc.com",
        "certainteed.com/residential",
    ],
    "pest_control": [
        "orkin.com",
        "terminix.com",
        "pestworld.org",
        "angi.com/pest-control",
    ],
    "landscaping": [
        "angi.com/landscaping",
        "thumbtack.com/landscaping",
        "lawnstarter.com",
        "trugreen.com",
    ],
    # Medical & Health
    "weight_loss": [
        "himshormones.com/weight-loss",
        "sequence.com",
        "foundhealth.com",
        "joinmochi.com",
        "ro.co/weight-loss",
    ],
    "hormone_therapy": [
        "himshormones.com",
        "getbiote.com",
        "hormonehealth.com",
        "defymedical.com",
    ],
    "dental": [
        "aspendental.com",
        "gentledental.com",
        "smilerx.com",
        "clearchoice.com",
        "companyofdentists.com",
    ],
    "vision": [
        "lasikplus.com",
        "visionsource.com",
        "warbyparker.com",
        "lenscrafters.com",
    ],
    "pt_rehab": [
        "atpt.com",
        "selectmedical.com",
        "novacare.com",
        "physio-pedia.com",
    ],
    "addiction": [
        "americanaddictioncenters.org",
        "recovery.org",
        "addictioncenter.com",
        "hazeldenbettyford.org",
    ],
    # Business Services
    "marketing": [
        "webfx.com",
        "neilpatel.com",
        "hubspot.com/agencies",
        "searchenginejournal.com",
    ],
    "web_dev": [
        "clutch.co/web-developers",
        "toptal.com",
        "upwork.com",
        "goodfirms.co",
    ],
    "accounting": [
        "bench.co",
        "accountingtoday.com",
        "cpa.com",
        "quickbooks.com",
    ],
    "consulting": [
        "mckinsey.com",
        "bain.com",
        "deloitte.com",
        "clutch.co/consulting",
    ],
    "staffing": [
        "roberthalf.com",
        "kellyservices.com",
        "adecco.com",
        "indeed.com/hiring",
    ],
    "legal_services": [
        "legalzoom.com",
        "rocketlawyer.com",
        "avvo.com",
        "nolo.com",
    ],
    # Financial
    "real_estate": [
        "zillow.com",
        "realtor.com",
        "redfin.com",
        "compass.com",
        "realestate.com",
    ],
    "mortgage": [
        "rocketmortgage.com",
        "better.com",
        "lendingtree.com",
        "bankrate.com/mortgages",
    ],
    "insurance": [
        "policygenius.com",
        "progressive.com",
        "statefarm.com",
        "geico.com",
    ],
    "investing": [
        "schwab.com",
        "fidelity.com",
        "vanguard.com",
        "robinhood.com",
        "nerdwallet.com/investing",
    ],
    "debt_relief": [
        "nationaldebtrelief.com",
        "bills.com",
        "credit.org",
        "moneymanagement.org",
    ],
    "tax_prep": [
        "turbotax.com",
        "hrblock.com",
        "taxslayer.com",
        "jacksonhewitt.com",
    ],
    # Technology
    "managed_it": [
        "connectwise.com",
        "datto.com",
        "kaseya.com",
        "mspservices.com",
    ],
    "cybersecurity": [
        "crowdstrike.com",
        "paloaltonetworks.com",
        "fortinet.com",
        "cybersecurityventures.com",
    ],
    "software_dev": [
        "clutch.co/software-developers",
        "toptal.com",
        "upwork.com",
        "gitlab.com",
    ],
    "cloud": [
        "aws.amazon.com",
        "cloud.google.com",
        "azure.microsoft.com",
        "digitalocean.com",
    ],
    "ai_automation": [
        "openai.com",
        "aitimejournal.com",
        "automationanywhere.com",
        "uipath.com",
    ],
    "data_analytics": [
        "tableau.com",
        "powerbi.microsoft.com",
        "databricks.com",
        "looker.com",
    ],
}

# ── Content scrape result ───────────────────────────────────────────

@dataclass
class PageScan:
    """Result of scanning a single competitor page."""
    tort_key: str
    url: str
    title: str = ""
    h1: str = ""
    h2s: list[str] = field(default_factory=list)
    meta_description: str = ""
    word_count: int = 0
    keyword_density: dict[str, float] = field(default_factory=dict)
    has_cta: bool = False
    cta_text: str = ""
    has_faq: bool = False
    faq_count: int = 0
    has_media_mentions: bool = False
    has_condition_list: bool = False
    has_qualify_section: bool = False
    has_testimonials: bool = False
    has_form: bool = False
    estimated_score: int = 0
    scraped_at: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ── Scanner ─────────────────────────────────────────────────────────

class Scanner:
    """Competitor page scanner for mass tort AEO content."""

    def __init__(self):
        self.competitors = COMPETITOR_DOMAINS

    def scan_all(self) -> list[PageScan]:
        """Scan all competitor pages for all tort types.

        Uses curl via subprocess for HTTP probing since we need
        to run inside the incus container without Playwright/headless.
        """
        import subprocess
        results = []

        for tort_key, domains in self.competitors.items():
            for domain in domains:
                url = f"https://{domain}" if not domain.startswith("http") else domain
                result = self._probe_page(url, tort_key, subprocess)
                results.append(result)

        return results

    def scan_for_tort(self, tort_key: str) -> list[PageScan]:
        """Scan competitors for a single tort type."""
        if tort_key not in self.competitors:
            return []
        import subprocess
        results = []
        for domain in self.competitors[tort_key]:
            url = f"https://{domain}" if not domain.startswith("http") else domain
            result = self._probe_page(url, tort_key, subprocess)
            results.append(result)
        return results

    def _probe_page(self, url: str, tort_key: str, sp) -> PageScan:
        """Scrape a single competitor page with simple HTTP probes."""
        import urllib.request, urllib.error

        scan = PageScan(
            tort_key=tort_key,
            url=url,
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            scan.error = str(e)[:200]
            return scan

        # Parse with simple regex (no BeautifulSoup dependency needed)
        # Title
        m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        if m:
            scan.title = m.group(1).strip()[:200]

        # Meta description
        m = re.search(r'<meta\s+name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
        if not m:
            m = re.search(r'<meta\s+property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
        if m:
            scan.meta_description = m.group(1).strip()[:300]

        # H1
        m = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.I)
        if m:
            scan.h1 = m.group(1).strip()[:200]

        # H2s
        scan.h2s = re.findall(r"<h2[^>]*>([^<]+)</h2>", html, re.I)
        scan.h2s = [h.strip()[:150] for h in scan.h2s]

        # Word count (strip HTML tags)
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        scan.word_count = len(text.split())

        # CTA detection
        cta_patterns = [
            r'class=["\'][^"\']*(?:cta|btn|button|cta-btn)[^"\']*["\']',
            r'free\s+(?:case|consult|eval|review)',
            r'get\s+(?:help|started|compensation)',
            r'apply\s+(?:now|today)',
            r'claim\s+(?:now|your|today)',
        ]
        for pat in cta_patterns:
            m = re.search(pat, html, re.I)
            if m:
                scan.has_cta = True
                # Extract nearby text
                ctx_start = max(0, m.start() - 40)
                ctx_end = min(len(html), m.end() + 40)
                scan.cta_text = html[ctx_start:ctx_end][:100]
                break

        # FAQ section
        faq_sections = re.findall(
            r'(?:faq|frequently\s+asked\s+questions|common\s+questions)',
            html, re.I
        )
        scan.has_faq = len(faq_sections) > 0
        scan.faq_count = len(re.findall(r'<h3[^>]*>[^<]*[?]', html, re.I))

        # Media mentions (news, verdicts, FDA)
        media_patterns = [
            "million", "verdict", "settlement", "FDA", "recall",
            "study", "research", "journal", "NIH", "WHO",
        ]
        for mp in media_patterns:
            if re.search(mp, html, re.I):
                scan.has_media_mentions = True
                break

        # Condition list
        scan.has_condition_list = bool(
            re.search(r'(?:conditions|cancers|injuries|side\s*effects)', html, re.I)
        ) and ("<li>" in html or "<ul>" in html)

        # Qualification section
        scan.has_qualify_section = bool(
            re.search(r'(?:qualify|eligible|do i|who (?:can|qualif))', html, re.I)
        )

        # Testimonials / reviews
        scan.has_testimonials = bool(
            re.search(r'(?:testimonial|review|star|client\s+story)', html, re.I)
        )

        # Form detection
        scan.has_form = bool(re.search(r'<form', html, re.I))

        # Estimate a raw score 0-100
        score = 0
        if scan.title: score += 5
        if scan.meta_description: score += 5
        if scan.h1: score += 5
        if scan.has_cta: score += 15
        if scan.has_faq: score += 15
        if scan.has_media_mentions: score += 10
        if scan.has_condition_list: score += 10
        if scan.has_qualify_section: score += 10
        if scan.has_testimonials: score += 10
        if scan.has_form: score += 10
        if 500 < scan.word_count < 3000: score += 5
        scan.estimated_score = min(score, 100)

        return scan


def scan_niche(niche_key: str) -> list[dict]:
    """Scan competitors for a specific niche (alias for scan_tort).

    Returns list of scan results with competitor page data.
    """
    return scan_tort(niche_key)


# ── Convenience ─────────────────────────────────────────────────────

def scan_all_pages() -> list[dict]:
    """Scan all known competitors and return dict results."""
    s = Scanner()
    results = s.scan_all()
    return [r.to_dict() for r in results]


def scan_tort(tort_key: str) -> list[dict]:
    """Scan competitors for one tort type."""
    s = Scanner()
    results = s.scan_for_tort(tort_key)
    return [r.to_dict() for r in results]
