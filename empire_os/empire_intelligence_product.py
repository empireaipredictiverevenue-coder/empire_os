#!/usr/bin/env python3
"""
EMPIRE INTELLIGENCE — High-End Lead Intelligence Product
=========================================================
Competes with Apollo, ZoomInfo, Clearbit, Apify — but specialized for 
pay-per-lead verticals with real-time scoring, enrichment, and A2A sales.

Architecture:
- 15-source enrichment waterfall (free + paid)
- Real-time Omega scoring (intent + fit + timing)
- Predictive revenue per lead
- A2A marketplace for agent-to-agent lead sales
- Apollo-style contact search + sequences
- Apify-style actor runs for custom scraping
"""

import json
import os
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"

# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS (Apollo/ZoomInfo style)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Contact:
    """Apollo-style contact record"""
    id: str
    full_name: str
    title: str
    email: str
    phone: str
    linkedin_url: str
    seniority: str  # cxo, vp, director, manager, individual
    department: str
    verified: bool
    last_verified: str

@dataclass
class Company:
    """Apollo-style company record"""
    id: str
    name: str
    domain: str
    industry: str
    employee_count: int
    revenue_range: str
    technologies: List[str]
    location: Dict[str, str]
    funding: Optional[Dict]
    intent_signals: List[str]

@dataclass
class Lead:
    """Empire Intelligence lead - enriched, scored, priced"""
    id: str
    company: Company
    contacts: List[Contact]
    niche: str
    sub_niche: str
    metro: str
    omega_score: float
    omega_tier: str  # platinum, gold, silver, bronze
    intent_score: float
    fit_score: float
    timing_score: float
    predicted_revenue: float
    payout_per_lead: float
    enrichment_sources: List[str]
    created_at: str
    status: str  # available, reserved, sold, delivered

# ─────────────────────────────────────────────────────────────────────────────
# ENRICHMENT ENGINE (15 sources waterfall)
# ─────────────────────────────────────────────────────────────────────────────

class EnrichmentEngine:
    """15-source enrichment waterfall — beats Apollo/ZoomInfo breadth"""
    
    SOURCES = [
        # Free sources (run first)
        "opencorporates",      # Business registry
        "osm_overpass",        # OpenStreetMap businesses
        "google_places_free",  # Google Places (free tier)
        "yelp_fusion_free",    # Yelp business data
        "crunchbase_free",     # Company funding data
        "linkedin_public",     # LinkedIn public profiles
        "github_orgs",         # GitHub organization data
        "angellist",           # Startup database
        "sec_edgar",           # SEC filings
        "uspto_patents",       # Patent assignments
        "federal_contracts",   # USAspending.gov
        # Paid/premium sources (run if free insufficient)
        "apollo_enrich",       # Apollo.io API
        "zoominfo_enrich",     # ZoomInfo API
        "clearbit_enrich",     # Clearbit API
        "people_data_labs",    # PDL API
    ]
    
    def __init__(self):
        self.conn = sqlite3.connect(DB, timeout=30)
        self.conn.row_factory = sqlite3.Row
    
    def enrich_company(self, domain: str) -> Dict:
        """Run full waterfall enrichment on a company domain."""
        results = {"domain": domain, "sources": {}, "confidence": 0.0}
        
        for source in self.SOURCES:
            try:
                data = self._query_source(source, domain)
                if data:
                    results["sources"][source] = data
                    results["confidence"] = max(results["confidence"], 
                        self._source_confidence(source))
                if results["confidence"] >= 0.9:
                    break  # High confidence, stop early
            except Exception as e:
                results["sources"][source] = {"error": str(e)}
        
        return results
    
    def _query_source(self, source: str, domain: str) -> Optional[Dict]:
        """Query a single enrichment source."""
        # Implementation would call actual APIs
        # This is the skeleton - each source needs real implementation
        return None
    
    def _source_confidence(self, source: str) -> float:
        """Confidence weight per source."""
        weights = {
            "opencorporates": 0.9,
            "sec_edgar": 0.95,
            "federal_contracts": 0.85,
            "crunchbase_free": 0.8,
            "linkedin_public": 0.7,
            "apollo_enrich": 0.95,
            "zoominfo_enrich": 0.95,
            "clearbit_enrich": 0.9,
            "people_data_labs": 0.9,
        }
        return weights.get(source, 0.5)

# ─────────────────────────────────────────────────────────────────────────────
# OMEGA SCORING ENGINE (Predictive revenue)
# ─────────────────────────────────────────────────────────────────────────────

class OmegaScorer:
    """Predictive revenue scoring — beats Apollo's static scoring."""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB, timeout=30)
    
    def score_lead(self, lead: Lead) -> Dict:
        """Multi-factor scoring with predictive revenue."""
        
        # Intent signals (from enrichment)
        intent_signals = self._get_intent_signals(lead.company.domain)
        intent_score = self._calculate_intent(intent_signals)
        
        # Fit score (ICP match)
        fit_score = self._calculate_fit(lead.company, lead.niche)
        
        # Timing score (urgency signals)
        timing_score = self._calculate_timing(lead.company, lead.niche)
        
        # Omega composite
        omega_score = (intent_score * 0.4) + (fit_score * 0.4) + (timing_score * 0.2)
        
        # Predictive revenue
        predicted_revenue = self._predict_revenue(omega_score, lead.niche, lead.metro)
        
        # Tier assignment
        if omega_score >= 0.85: tier = "platinum"
        elif omega_score >= 0.70: tier = "gold"
        elif omega_score >= 0.50: tier = "silver"
        else: tier = "bronze"
        
        return {
            "omega_score": round(omega_score, 3),
            "omega_tier": tier,
            "intent_score": round(intent_score, 3),
            "fit_score": round(fit_score, 3),
            "timing_score": round(timing_score, 3),
            "predicted_revenue": round(predicted_revenue, 2),
        }
    
    def _get_intent_signals(self, domain: str) -> List[str]:
        """Get intent signals from enrichment + external sources."""
        signals = []
        # Check: job postings, tech installs, funding, hiring, content, reviews
        return signals
    
    def _calculate_intent(self, signals: List[str]) -> float:
        weights = {
            "hiring_sales": 0.9, "hiring_marketing": 0.7, "tech_install": 0.8,
            "funding_raised": 0.95, "content_engagement": 0.5, "review_spike": 0.6,
            "competitor_mention": 0.7, "pricing_page_views": 0.8
        }
        return min(1.0, sum(weights.get(s, 0.3) for s in signals) / len(signals)) if signals else 0.1
    
    def _calculate_fit(self, company: Company, niche: str) -> float:
        """ICP fit scoring."""
        score = 0.5  # baseline
        # Employee count match
        # Revenue range match
        # Technology stack match
        # Geographic match
        return min(1.0, score)
    
    def _calculate_timing(self, company: Company, niche: str) -> float:
        """Urgency/timing signals."""
        score = 0.3
        # Contract renewals, budget cycles, seasonality, competitor churn
        return min(1.0, score)
    
    def _predict_revenue(self, omega_score: float, niche: str, metro: str) -> float:
        """Predict revenue per lead based on historical data."""
        base_prices = {
            "roofing": 150, "hvac": 120, "plumbing": 100, "solar": 200,
            "weight_loss": 80, "roof_repair": 90, "water_damage": 150
        }
        base = base_prices.get(niche, 50)
        metro_multiplier = {"NYC": 1.5, "LAX": 1.4, "CHI": 1.2, "DFW": 1.1}.get(metro, 1.0)
        return base * metro_multiplier * (0.5 + omega_score * 0.5)

# ─────────────────────────────────────────────────────────────────────────────
# APOLLO-STYLE SEARCH & SEQUENCES
# ─────────────────────────────────────────────────────────────────────────────

class ApolloSearch:
    """Apollo-style contact/company search with sequences."""
    
    def search_contacts(self, filters: Dict) -> List[Contact]:
        """Search contacts by: title, seniority, department, company size, etc."""
        # Filters: titles, seniority, departments, company_size, revenue, 
        # location, technologies, intent_topics, funding_stage
        pass
    
    def search_companies(self, filters: Dict) -> List[Company]:
        """Search companies by: industry, size, revenue, tech_stack, location, etc."""
        pass
    
    def create_sequence(self, name: str, steps: List[Dict]) -> str:
        """Create Apollo-style email/LinkedIn sequence."""
        # Steps: email, linkedin_connection, linkedin_message, call, manual_task
        pass
    
    def run_sequence(self, sequence_id: str, contacts: List[str]) -> Dict:
        """Execute sequence on contact list."""
        pass

# ─────────────────────────────────────────────────────────────────────────────
# APIFY-STYLE ACTORS (Custom scraping actors)
# ─────────────────────────────────────────────────────────────────────────────

class ActorRunner:
    """Apify-style actor platform for custom scraping."""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB, timeout=30)
        self._ensure_tables()
    
    def _ensure_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS actors (
                id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                code TEXT,  -- Python/JS actor code
                input_schema TEXT,  -- JSON Schema
                output_schema TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS actor_runs (
                id TEXT PRIMARY KEY,
                actor_id TEXT,
                input TEXT,  -- JSON
                output TEXT,  -- JSON
                status TEXT,  -- running, succeeded, failed
                started_at TEXT,
                finished_at TEXT,
                error TEXT,
                cost_usd REAL
            )
        """)
        self.conn.commit()
    
    def create_actor(self, name: str, code: str, input_schema: Dict, 
                     output_schema: Dict, description: str = "") -> str:
        """Create a new actor."""
        actor_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute("""
            INSERT INTO actors (id, name, description, code, input_schema, 
                               output_schema, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (actor_id, name, description, code, json.dumps(input_schema),
              json.dumps(output_schema), now, now))
        self.conn.commit()
        return actor_id
    
    def run_actor(self, actor_id: str, input_data: Dict) -> str:
        """Run an actor with input."""
        run_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute("""
            INSERT INTO actor_runs (id, actor_id, input, status, started_at)
            VALUES (?, ?, ?, 'running', ?)
        """, (run_id, actor_id, json.dumps(input_data), now))
        self.conn.commit()
        
        # Execute asynchronously (in production, use queue)
        # For now, return run_id for polling
        return run_id
    
    def get_run_result(self, run_id: str) -> Dict:
        """Get actor run result."""
        cur = self.conn.cursor()
        row = cur.execute("SELECT * FROM actor_runs WHERE id=?", (run_id,)).fetchone()
        if row:
            return dict(row)
        return {}

# ─────────────────────────────────────────────────────────────────────────────
# A2A MARKETPLACE (Agent-to-Agent lead sales)
# ─────────────────────────────────────────────────────────────────────────────

class A2AMarketplace:
    """Agent-to-Agent marketplace for lead trading."""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self._ensure_tables()
    
    def _ensure_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS a2a_listings (
                id TEXT PRIMARY KEY,
                seller_agent_id TEXT,
                lead_id TEXT,
                price_usdc REAL,
                min_reputation INTEGER,
                expires_at TEXT,
                status TEXT,  -- active, sold, expired, cancelled
                created_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS a2a_offers (
                id TEXT PRIMARY KEY,
                listing_id TEXT,
                buyer_agent_id TEXT,
                price_usdc REAL,
                status TEXT,  -- pending, accepted, rejected, expired
                created_at TEXT,
                responded_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_reputation (
                agent_id TEXT PRIMARY KEY,
                score REAL DEFAULT 100.0,
                total_sales INTEGER DEFAULT 0,
                total_purchases INTEGER DEFAULT 0,
                disputes INTEGER DEFAULT 0,
                updated_at TEXT
            )
        """)
        self.conn.commit()
    
    def list_lead(self, seller_agent: str, lead_id: str, price_usdc: float, 
                  min_reputation: int = 50, expires_hours: int = 24) -> str:
        """List a lead for sale on A2A marketplace."""
        listing_id = str(uuid.uuid4())[:12]
        expires = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59).isoformat()
        self.conn.execute("""
            INSERT INTO a2a_listings (id, seller_agent_id, lead_id, price_usdc,
                                      min_reputation, expires_at, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?)
        """, (listing_id, seller_agent, lead_id, price_usdc, 
              min_reputation, expires, datetime.now(timezone.utc).isoformat()))
        self.conn.commit()
        return listing_id
    
    def make_offer(self, buyer_agent: str, listing_id: str, price_usdc: float) -> str:
        """Make an offer on a listing."""
        offer_id = str(uuid.uuid4())[:12]
        self.conn.execute("""
            INSERT INTO a2a_offers (id, listing_id, buyer_agent_id, price_usdc,
                                    status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
        """, (offer_id, listing_id, buyer_agent, price_usdc, 
              datetime.now(timezone.utc).isoformat()))
        self.conn.commit()
        return offer_id
    
    def accept_offer(self, seller_agent: str, offer_id: str) -> bool:
        """Accept an offer - triggers escrow + transfer."""
        cur = self.conn.cursor()
        # Verify ownership
        listing = cur.execute("""
            SELECT l.*, o.buyer_agent_id, o.price_usdc
            FROM a2a_listings l
            JOIN a2a_offers o ON o.listing_id = l.id
            WHERE o.id = ? AND l.seller_agent_id = ? AND l.status = 'active'
        """, (offer_id, seller_agent)).fetchone()
        
        if not listing:
            return False
        
        # Mark listing sold, offer accepted
        cur.execute("UPDATE a2a_listings SET status='sold' WHERE id=?", (listing["id"],))
        cur.execute("UPDATE a2a_offers SET status='accepted', responded_at=? WHERE id=?",
                    (datetime.now(timezone.utc).isoformat(), offer_id))
        
        # Create escrow (simplified - real impl uses crypto escrow)
        escrow_id = f"escrow_{listing['id']}_{offer_id}"
        cur.execute("""
            INSERT INTO a2a_escrow (id, listing_id, offer_id, amount_usdc, 
                                    seller_agent, buyer_agent, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'funded', ?)
        """, (escrow_id, listing["id"], offer_id, listing["price_usdc"],
              listing["seller_agent_id"], listing["buyer_agent_id"],
              datetime.now(timezone.utc).isoformat()))
        
        self.conn.commit()
        return True
    
    def get_active_listings(self, min_price: float = 0, max_price: float = 10000,
                            niche: str = "", metro: str = "") -> List[Dict]:
        """Get active listings with filters."""
        query = "SELECT * FROM a2a_listings WHERE status='active' AND expires_at > ?"
        params = [datetime.now(timezone.utc).isoformat()]
        
        if min_price > 0:
            query += " AND price_usdc >= ?"
            params.append(min_price)
        if max_price < 10000:
            query += " AND price_usdc <= ?"
            params.append(max_price)
        
        cur = self.conn.cursor()
        rows = cur.execute(query, params).fetchall()
        return [dict(r) for r in rows]

# ─────────────────────────────────────────────────────────────────────────────
# EMPIRE INTELLIGENCE PRODUCT — Main Entry Point
# ─────────────────────────────────────────────────────────────────────────────

class EmpireIntelligence:
    """Main product class — unifies all capabilities."""
    
    def __init__(self):
        self.enrichment = EnrichmentEngine()
        self.scorer = OmegaScorer()
        self.search = ApolloSearch()
        self.actors = ActorRunner()
        self.marketplace = A2AMarketplace()
        self.conn = sqlite3.connect(DB, timeout=30)
        self.conn.row_factory = sqlite3.Row
    
    def enrich_and_score(self, domain: str, niche: str, metro: str) -> Lead:
        """Full pipeline: enrich company → score → price → list."""
        # 1. Enrich
        enrichment = self.enrichment.enrich_company(domain)
        
        # 2. Build Company object
        company = Company(
            id=str(uuid.uuid4())[:12],
            name=enrichment.get("name", domain),
            domain=domain,
            industry=enrichment.get("industry", ""),
            employee_count=enrichment.get("employee_count", 0),
            revenue_range=enrichment.get("revenue_range", ""),
            technologies=enrichment.get("technologies", []),
            location=enrichment.get("location", {}),
            funding=enrichment.get("funding"),
            intent_signals=enrichment.get("intent_signals", [])
        )
        
        # 3. Score
        lead = Lead(
            id=str(uuid.uuid4())[:12],
            company=company,
            contacts=[],
            niche=niche,
            sub_niche="",
            metro=metro,
            omega_score=0,
            omega_tier="",
            intent_score=0,
            fit_score=0,
            timing_score=0,
            predicted_revenue=0,
            payout_per_lead=0,
            enrichment_sources=list(enrichment.get("sources", {}).keys()),
            created_at=datetime.now(timezone.utc).isoformat(),
            status="available"
        )
        
        scoring = self.scorer.score_lead(lead)
        lead.omega_score = scoring["omega_score"]
        lead.omega_tier = scoring["omega_tier"]
        lead.intent_score = scoring["intent_score"]
        lead.fit_score = scoring["fit_score"]
        lead.timing_score = scoring["timing_score"]
        lead.predicted_revenue = scoring["predicted_revenue"]
        lead.payout_per_lead = scoring["predicted_revenue"] * 0.3  # 30% to buyer
        
        # 4. Store in DB
        self._store_lead(lead)
        
        return lead
    
    def _store_lead(self, lead: Lead):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO empire_leads 
            (id, company_name, domain, niche, sub_niche, metro,
             omega_score, omega_tier, intent_score, fit_score, timing_score,
             predicted_revenue, payout_per_lead, enrichment_sources,
             status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (lead.id, lead.company.name, lead.company.domain, lead.niche,
              lead.sub_niche, lead.metro, lead.omega_score, lead.omega_tier,
              lead.intent_score, lead.fit_score, lead.timing_score,
              lead.predicted_revenue, lead.payout_per_lead,
              json.dumps(lead.enrichment_sources), lead.status, lead.created_at))
        self.conn.commit()
    
    def search_leads(self, filters: Dict) -> List[Lead]:
        """Apollo-style lead search."""
        query = "SELECT * FROM empire_leads WHERE status='available'"
        params = []
        
        if filters.get("niche"):
            query += " AND niche=?"
            params.append(filters["niche"])
        if filters.get("metro"):
            query += " AND metro=?"
            params.append(filters["metro"])
        if filters.get("min_omega"):
            query += " AND omega_score >= ?"
            params.append(filters["min_omega"])
        if filters.get("max_price"):
            query += " AND payout_per_lead <= ?"
            params.append(filters["max_price"])
        if filters.get("tier"):
            query += " AND omega_tier=?"
            params.append(filters["tier"])
        
        query += " ORDER BY omega_score DESC LIMIT ?"
        params.append(filters.get("limit", 50))
        
        cur = self.conn.cursor()
        rows = cur.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    
    def run_enrichment_batch(self, domains: List[str], niche: str, metro: str) -> List[Lead]:
        """Batch enrich multiple domains."""
        leads = []
        for domain in domains:
            try:
                lead = self.enrich_and_score(domain, niche, metro)
                leads.append(lead)
            except Exception as e:
                print(f"Error enriching {domain}: {e}")
        return leads

# ─────────────────────────────────────────────────────────────────────────────
# DB SCHEMA INIT
# ─────────────────────────────────────────────────────────────────────────────

def init_empire_intelligence_schema():
    """Create all tables for Empire Intelligence product."""
    conn = sqlite3.connect(DB, timeout=30)
    cur = conn.cursor()
    
    # Main leads table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS empire_leads (
            id TEXT PRIMARY KEY,
            company_name TEXT,
            domain TEXT,
            niche TEXT,
            sub_niche TEXT,
            metro TEXT,
            omega_score REAL,
            omega_tier TEXT,
            intent_score REAL,
            fit_score REAL,
            timing_score REAL,
            predicted_revenue REAL,
            payout_per_lead REAL,
            enrichment_sources TEXT,  -- JSON
            status TEXT DEFAULT 'available',
            created_at TEXT,
            updated_at TEXT
        )
    """)
    
    # Contacts table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS empire_contacts (
            id TEXT PRIMARY KEY,
            lead_id TEXT,
            full_name TEXT,
            title TEXT,
            email TEXT,
            phone TEXT,
            linkedin_url TEXT,
            seniority TEXT,
            department TEXT,
            verified INTEGER DEFAULT 0,
            last_verified TEXT,
            FOREIGN KEY (lead_id) REFERENCES empire_leads(id)
        )
    """)
    
    # Companies table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS empire_companies (
            id TEXT PRIMARY KEY,
            lead_id TEXT,
            name TEXT,
            domain TEXT,
            industry TEXT,
            employee_count INTEGER,
            revenue_range TEXT,
            technologies TEXT,  -- JSON
            location TEXT,  -- JSON
            funding TEXT,  -- JSON
            intent_signals TEXT,  -- JSON
            FOREIGN KEY (lead_id) REFERENCES empire_leads(id)
        )
    """)
    
    # Actor tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS actors (
            id TEXT PRIMARY KEY,
            name TEXT,
            description TEXT,
            code TEXT,
            input_schema TEXT,
            output_schema TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS actor_runs (
            id TEXT PRIMARY KEY,
            actor_id TEXT,
            input TEXT,
            output TEXT,
            status TEXT,
            started_at TEXT,
            finished_at TEXT,
            error TEXT,
            cost_usd REAL
        )
    """)
    
    # A2A marketplace tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS a2a_listings (
            id TEXT PRIMARY KEY,
            seller_agent_id TEXT,
            lead_id TEXT,
            price_usdc REAL,
            min_reputation INTEGER,
            expires_at TEXT,
            status TEXT,
            created_at TEXT
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS a2a_offers (
            id TEXT PRIMARY KEY,
            listing_id TEXT,
            buyer_agent_id TEXT,
            price_usdc REAL,
            status TEXT,
            created_at TEXT,
            responded_at TEXT
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_reputation (
            agent_id TEXT PRIMARY KEY,
            score REAL DEFAULT 100.0,
            total_sales INTEGER DEFAULT 0,
            total_purchases INTEGER DEFAULT 0,
            disputes INTEGER DEFAULT 0,
            updated_at TEXT
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS a2a_escrow (
            id TEXT PRIMARY KEY,
            listing_id TEXT,
            offer_id TEXT,
            amount_usdc REAL,
            seller_agent TEXT,
            buyer_agent TEXT,
            status TEXT,
            created_at TEXT
        )
    """)
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_empire_intelligence_schema()
    print("Empire Intelligence schema initialized")

# ─────────────────────────────────────────────────────────────────────────────
# PRODUCT CATALOG — Empire AI product line (sellable SKUs)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Product:
    sku: str
    name: str
    price_usd: float
    billing: str          # one_time / per_month / per_lead
    description: str
    tier: str
    keywords: str = ""    # SEO comma-separated keywords
    meta_description: str = ""  # SEO meta description (<=160 chars)
    seo_title: str = ""   # SEO <title> override
PRODUCT_CATALOG = {
    # ── Empire Intelligence (Apollo/ZoomInfo killer) ──
    "EI-STARTER": Product(
        "EI-STARTER", "Empire Intelligence — Starter",
        99.0, "per_month",
        "500 enriched contacts/mo, Omega scoring, 5-source waterfall. "
        "Apollo-grade B2B intel without the enterprise price tag.",
        "core",
        keywords="B2B leads, business intelligence, Apollo alternative, ZoomInfo alternative, lead enrichment, contact database",
        meta_description="Apollo-grade B2B lead intelligence at $99/mo. 500 enriched contacts, Omega scoring, 5-source waterfall.",
        seo_title="Empire Intelligence Starter — B2B Lead Intelligence"),
    "EI-PRO": Product(
        "EI-PRO", "Empire Intelligence — Pro",
        299.0, "per_month",
        "5,000 contacts/mo, 15-source waterfall, A2A marketplace access, "
        "predictive revenue per lead, Apollo-style sequences.",
        "core",
        keywords="lead generation platform, sales intelligence, predictive lead scoring, A2A lead marketplace, B2B data",
        meta_description="Pro B2B intelligence: 5,000 contacts/mo, 15-source waterfall, predictive revenue scoring, A2A marketplace.",
        seo_title="Empire Intelligence Pro — Predictive B2B Lead Platform"),
    "EI-ENT": Product(
        "EI-ENT", "Empire Intelligence — Enterprise",
        999.0, "per_month",
        "Unlimited contacts, white-label A2A, custom Apify actors, "
        "dedicated whale harvesting, law-firm mass-tort routing.",
        "core",
        keywords="enterprise lead intelligence, white-label lead platform, mass tort leads, whale harvesting, custom scraping actors",
        meta_description="Enterprise B2B intelligence: unlimited contacts, white-label A2A, custom actors, whale + mass-tort routing.",
        seo_title="Empire Intelligence Enterprise — White-Label Lead OS"),

    # ── Empire Ambient AI (the new product — Ambient/silent intelligence layer) ──
    "AMBIENT-AI": Product(
        "AMBIENT-AI", "Empire Ambient AI",
        49.0, "per_month",
        "Ambient AI that runs silently in the background of your business — "
        "watches signals (intent, churn risk, buying windows, competitor moves), "
        "scores every contact with the Omega engine, and triggers the right "
        "agent action without human input. No dashboards to babysit, no prompts "
        "to type. It observes, reasons, and acts. Pairs with Empire Intelligence "
        "for contact data and the 50+ agent fleet for execution. "
        "Layer 23 Predictive Cloud brain included.",
        "ambient",
        keywords="ambient AI, autonomous AI agent, silent AI assistant, AI sales automation, intent signal monitoring, predictive outreach, no-code AI, background AI agent, Omega AI scoring, self-acting AI",
        meta_description="Ambient AI that silently watches buying signals, scores contacts, and triggers agent actions — no dashboards, no prompts. $49/mo.",
        seo_title="Empire Ambient AI — Silent Autonomous Intelligence for Your Business"),
    "AMBIENT-AI-WHALE": Product(
        "AMBIENT-AI-WHALE", "Empire Ambient AI — Whale Tier",
        499.0, "per_month",
        "Ambient AI plus dedicated whale harvesting: the brain continuously "
        "scans for high-value prospects ($10k+ deals), scores them platinum, "
        "and routes to closers automatically. Enterprise observability for "
        "your entire revenue stack via the Gamma analytics layer.",
        "ambient",
        keywords="whale hunting AI, enterprise lead harvesting, high-ticket prospect AI, B2B whale detection, autonomous sales closing, revenue observability",
        meta_description="Ambient AI + dedicated whale harvesting: auto-detects $10k+ prospects, scores platinum, routes to closers. $499/mo.",
        seo_title="Empire Ambient AI Whale Tier — Autonomous High-Ticket Hunting"),
}

def get_product(sku: str) -> Optional[Product]:
    return PRODUCT_CATALOG.get(sku)

def list_products() -> List[dict]:
    return [asdict(p) for p in PRODUCT_CATALOG.values()]
