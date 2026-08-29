#!/usr/bin/env python3
"""Supabase-first data layer with SQLite read replica sync.
All writes go to Supabase first. SQLite is read-only replica.
"""
import os, urllib.request, json, sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

# Supabase config (hardcoded for reliability)
SUPABASE_URL = "https://owbeinlfcfdtwcwrttjy.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im93YmVpbmxmY2ZkdHdjd3J0dGp5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3Njc3NzA3MCwiZXhwIjoyMDkyMzUzMDcwfQ.0G7wLC4Cg5ewz7iQII23J2021hrf1PN99xUYddKDQAA"

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

class SupabaseClient:
    """Primary data store - all writes go here first."""
    
    def __init__(self):
        self.url = "https://owbeinlfcfdtwcwrttjy.supabase.co"
        self.key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im93YmVpbmxmY2ZkdHdjd3J0dGp5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3Njc3NzA3MCwiZXhwIjoyMDkyMzUzMDcwfQ.0G7wLC4Cg5ewz7iQII23J2021hrf1PN99xUYddKDQAA"
    
    def _headers(self, extra: dict = None) -> dict:
        h = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if extra:
            h.update(extra)
        return h
    
    def _url(self, table: str, query: str = "") -> str:
        return f"https://owbeinlfcfdtwcwrttjy.supabase.co/rest/v1/{table}{query}"
    
    def select(self, table: str, columns: str = "*", filters: dict = None, 
               order: str = None, limit: int = 1000, offset: int = 0) -> List[Dict]:
        """SELECT rows from Supabase."""
        q = f"?select={columns}"
        if filters:
            for k, v in filters.items():
                q += f"&{k}=eq.{v}"
        if order:
            q += f"&order={order}"
        q += f"&offset={offset}&limit={limit}"
        
        req = urllib.request.Request(self._url(table, q), headers=self._headers())
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    
    def insert(self, table: str, row: Dict, return_repr: bool = True) -> List[Dict]:
        """INSERT row into Supabase."""
        headers = self._headers({"Prefer": "return=representation" if return_repr else "return=minimal"})
        data = json.dumps(row).encode()
        req = urllib.request.Request(self._url(table), data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode()) if return_repr else []
    
    def upsert(self, table: str, rows: List[Dict], on_conflict: str = None) -> List[Dict]:
        """UPSERT rows into Supabase."""
        headers = self._headers({"Prefer": "return=representation", "Resolution": "merge-duplicates"})
        if on_conflict:
            headers["Resolution"] = "merge-duplicates"
            # PostgREST uses on_conflict query param
            table_with_conflict = f"{table}?on_conflict={on_conflict}"
        else:
            table_with_conflict = table
        data = json.dumps(rows).encode()
        req = urllib.request.Request(self._url(table_with_conflict), data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    
    def update(self, table: str, match: Dict, values: Dict) -> List[Dict]:
        """UPDATE rows in Supabase."""
        q = ""
        for k, v in match.items():
            q += f"&{k}=eq.{v}" if q else f"?{k}=eq.{v}"
        headers = self._headers({"Prefer": "return=representation"})
        data = json.dumps(values).encode()
        req = urllib.request.Request(self._url(table, q), data=data, headers=headers, method="PATCH")
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    
    def count(self, table: str, filters: dict = None) -> int:
        """Get exact count from Supabase."""
        q = "?select=count&limit=0"
        if filters:
            for k, v in filters.items():
                q += f"&{k}=eq.{v}"
        req = urllib.request.Request(f"{self.url}/rest/v1/{table}{q}", 
                                    headers={'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}', 'Prefer': 'count=exact'}, 
                                    method="HEAD")
        with urllib.request.urlopen(req) as r:
            cr = r.headers.get('content-range', '*/0')
            return int(cr.split('/')[-1]) if '/' in cr else 0

# Global instance
supabase = SupabaseClient()


class SQLiteReplica:
    """Local SQLite read replica - kept in sync by background sync."""
    
    def __init__(self, db_path: str = "/root/empire_os/empire_os.db"):
        self.db_path = db_path
        self._ensure_schema()
    
    def _ensure_schema(self):
        con = sqlite3.connect(self.db_path, timeout=30)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA busy_timeout=30000")
        
        # crm_leads
        con.execute("""
            CREATE TABLE IF NOT EXISTS crm_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_uid TEXT UNIQUE,
                source TEXT,
                business_name TEXT,
                contact_name TEXT,
                email TEXT,
                phone TEXT,
                metro TEXT,
                niche TEXT,
                sub_niche TEXT,
                street TEXT,
                city TEXT,
                state TEXT,
                zip TEXT,
                website TEXT,
                social_links TEXT,
                employee_count INTEGER,
                revenue_est REAL,
                year_founded INTEGER,
                bbb_rating TEXT,
                license_no TEXT,
                license_state TEXT,
                omega_score REAL,
                omega_tier TEXT,
                enrichment_score REAL,
                status TEXT,
                owner TEXT,
                notes TEXT,
                tags_json TEXT,
                created_at TEXT,
                updated_at TEXT,
                icp_fit_score REAL,
                icp_tier TEXT,
                icp_name TEXT,
                eval_grade TEXT,
                eval_omega REAL,
                scored_at TEXT,
                score_breakdown TEXT,
                outreach_attempted INTEGER,
                outreach_at TEXT,
                vapi_call_id TEXT,
                email_sent INTEGER,
                audit_generated INTEGER,
                audit_token TEXT,
                converted_at TEXT,
                fleet_size INTEGER,
                whale_tier TEXT,
                logistics_score REAL,
                satellite_json TEXT,
                enrich_logistics TEXT,
                campaign_sent INTEGER DEFAULT 0
            )
        """)
        
        # lane_leads
        con.execute("""
            CREATE TABLE IF NOT EXISTS lane_leads (
                lead_ref TEXT PRIMARY KEY,
                lane_id TEXT,
                prospect_id TEXT,
                status TEXT,
                omega_score REAL,
                omega_tier TEXT,
                notes TEXT,
                created_at TEXT,
                buyer_id TEXT,
                niche TEXT,
                metro TEXT
            )
        """)
        
        # si_products
        con.execute("""
            CREATE TABLE IF NOT EXISTS si_products (
                sku TEXT PRIMARY KEY,
                name TEXT,
                repo_url TEXT DEFAULT '',
                license TEXT DEFAULT '',
                description TEXT DEFAULT '',
                b2b_angle TEXT DEFAULT '',
                tier1_usdc REAL DEFAULT 0,
                tier2_usdc REAL DEFAULT 0,
                tier3_usdc REAL DEFAULT 0,
                tier4_usdc REAL DEFAULT 0,
                setup_fee_usdc REAL DEFAULT 0,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                features TEXT,
                benefits TEXT,
                deliverables TEXT
            )
        """)
        
        # si_buyer_outreach
        con.execute("""
            CREATE TABLE IF NOT EXISTS si_buyer_outreach (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prospect_id TEXT UNIQUE,
                business_name TEXT,
                contact_name TEXT,
                email TEXT,
                phone TEXT,
                metro TEXT,
                niche TEXT,
                street TEXT,
                city TEXT,
                state TEXT,
                zip TEXT,
                website TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT,
                omega_score REAL,
                omega_tier TEXT,
                enrichment_score REAL,
                outreach_attempted INTEGER,
                outreach_at TEXT,
                vapi_call_id TEXT,
                email_sent INTEGER,
                audit_generated INTEGER,
                audit_token TEXT,
                converted_at TEXT
            )
        """)
        
        # si_tenant
        con.execute("""
            CREATE TABLE IF NOT EXISTS si_tenant (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT UNIQUE,
                name TEXT,
                email TEXT,
                plan TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        
        # si_subscription
        con.execute("""
            CREATE TABLE IF NOT EXISTS si_subscription (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscription_id TEXT UNIQUE,
                tenant_id TEXT,
                product_sku TEXT,
                tier TEXT,
                status TEXT,
                price_usdc REAL,
                starts_at TEXT,
                ends_at TEXT,
                created_at TEXT
            )
        """)
        
        # si_tenant
        con.execute("CREATE INDEX IF NOT EXISTS idx_crm_leads_lead_uid ON crm_leads(lead_uid)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_crm_leads_email ON crm_leads(email)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_crm_leads_niche ON crm_leads(niche)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_lane_leads_lead_ref ON lane_leads(lead_ref)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_lane_leads_prospect ON lane_leads(prospect_id)")
        
        con.commit()
        con.close()
    
    def get_connection(self):
        con = sqlite3.connect(self.db_path, timeout=30)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA busy_timeout=30000")
        con.row_factory = sqlite3.Row
        return con
    
    # READ methods (local SQLite - fast)
    def get_crm_leads(self, limit: int = 100, offset: int = 0, filters: dict = None) -> List[Dict]:
        con = self.get_connection()
        try:
            where = " WHERE 1=1"
            params = []
            if filters:
                for k, v in filters.items():
                    where += f" AND {k} = ?"
                    params.append(v)
            params.extend([limit, offset])
            rows = con.execute(f"SELECT * FROM crm_leads{where} LIMIT ? OFFSET ?", params).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()
    
    def get_crm_lead_by_uid(self, lead_uid: str) -> Optional[Dict]:
        con = self.get_connection()
        try:
            row = con.execute("SELECT * FROM crm_leads WHERE lead_uid = ?", (lead_uid,)).fetchone()
            return dict(row) if row else None
        finally:
            con.close()
    
    def get_lane_leads(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        con = self.get_connection()
        try:
            rows = con.execute("SELECT * FROM lane_leads LIMIT ? OFFSET ?", (limit, offset)).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()
    
    def get_products(self, active_only: bool = True) -> List[Dict]:
        con = self.get_connection()
        try:
            if active_only:
                rows = con.execute("SELECT * FROM si_products WHERE active = 1 ORDER BY tier1_usdc DESC").fetchall()
            else:
                rows = con.execute("SELECT * FROM si_products ORDER BY tier1_usdc DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()
    
    def get_product_by_sku(self, sku: str) -> Optional[Dict]:
        con = self.get_connection()
        try:
            row = con.execute("SELECT * FROM si_products WHERE sku = ?", (sku,)).fetchone()
            return dict(row) if row else None
        finally:
            con.close()
    
    def get_buyer_outreach(self, limit: int = 100) -> List[Dict]:
        con = self.get_connection()
        try:
            rows = con.execute("SELECT * FROM si_buyer_outreach ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()


# Global instances
supabase_client = SupabaseClient()
sqlite_replica = SQLiteReplica()


def sync_supabase_to_sqlite(limit: int = 1000) -> dict:
    """Background sync: Supabase -> SQLite (read replica)."""
    results = {}
    
    # Sync crm_leads
    try:
        offset = 0
        limit = 1000
        total = 0
        while True:
            leads = supabase_client.select("crm_leads", limit=limit, offset=offset)
            if not leads:
                break
            
            con = sqlite3.connect("/root/empire_os/empire_os.db", timeout=30)
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA busy_timeout=30000")
            
            for lead in leads:
                lead_uid = lead.get('lead_uid')
                if not lead_uid:
                    continue
                
                existing = con.execute("SELECT id FROM crm_leads WHERE lead_uid = ?", (lead_uid,)).fetchone()
                
                if existing:
                    con.execute("""
                        UPDATE crm_leads SET
                            source = ?, business_name = ?, contact_name = ?, email = ?, phone = ?,
                            metro = ?, niche = ?, sub_niche = ?, street = ?, city = ?, state = ?, zip = ?,
                            website = ?, social_links = ?, employee_count = ?, revenue_est = ?,
                            year_founded = ?, bbb_rating = ?, license_no = ?, license_state = ?,
                            omega_score = ?, omega_tier = ?, enrichment_score = ?, status = ?,
                            owner = ?, notes = ?, tags_json = ?, updated_at = ?,
                            icp_fit_score = ?, icp_tier = ?, icp_name = ?, eval_grade = ?,
                            eval_omega = ?, omega_score = ?, correlation_id = ?,
                            fleet_size = ?, whale_tier = ?, logistics_score = ?,
                            satellite_json = ?, enrich_logistics = ?
                        WHERE lead_uid = ?
                    """, (
                        lead.get('source'), lead.get('business_name'), lead.get('contact_name'),
                        lead.get('email'), lead.get('phone'), lead.get('metro'), lead.get('niche'),
                        lead.get('sub_niche'), lead.get('street'), lead.get('city'), lead.get('state'),
                        lead.get('zip'), lead.get('website'), lead.get('social_links'),
                        lead.get('employee_count'), lead.get('revenue_est'), lead.get('year_founded'),
                        lead.get('bbb_rating'), lead.get('license_no'), lead.get('license_state'),
                        lead.get('omega_score'), lead.get('omega_tier'), lead.get('enrichment_score'),
                        lead.get('status'), lead.get('owner'), lead.get('notes'),
                        json.dumps(lead.get('tags')) if lead.get('tags') else None,
                        datetime.now().isoformat(),
                        lead.get('icp_fit_score'), lead.get('icp_tier'), lead.get('icp_name'),
                        lead.get('eval_grade'), lead.get('eval_omega'), lead.get('omega_score'),
                        lead.get('correlation_id'), lead.get('fleet_size'), lead.get('whale_tier'),
                        lead.get('logistics_score'), json.dumps(lead.get('satellite')) if lead.get('satellite') else None,
                        json.dumps(lead.get('enrich_logistics')) if lead.get('enrich_logistics') else None,
                        lead.get('lead_uid')
                    ))
                else:
                    con.execute("""
                        INSERT INTO crm_leads (
                            lead_uid, source, business_name, contact_name, email, phone,
                            metro, niche, sub_niche, street, city, state, zip,
                            website, social_links, employee_count, revenue_est,
                            year_founded, bbb_rating, license_no, license_state,
                            omega_score, omega_tier, enrichment_score, status,
                            owner, notes, tags_json, created_at, updated_at,
                            icp_fit_score, icp_tier, icp_name, eval_grade,
                            eval_omega, omega_score, correlation_id,
                            fleet_size, whale_tier, logistics_score,
                            satellite_json, enrich_logistics, campaign_sent
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """, (
                        lead.get('lead_uid'), lead.get('source'), lead.get('business_name'),
                        lead.get('contact_name'), lead.get('email'), lead.get('phone'),
                        lead.get('metro'), lead.get('niche'), lead.get('sub_niche'),
                        lead.get('street'), lead.get('city'), lead.get('state'), lead.get('zip'),
                        lead.get('website'), lead.get('social_links'),
                        lead.get('employee_count'), lead.get('revenue_est'),
                        lead.get('year_founded'), lead.get('bbb_rating'),
                        lead.get('license_no'), lead.get('license_state'),
                        lead.get('omega_score'), lead.get('omega_tier'), lead.get('enrichment_score'),
                        lead.get('status'), lead.get('owner'), lead.get('notes'),
                        json.dumps(lead.get('tags')) if lead.get('tags') else None,
                        lead.get('created_at'), datetime.now().isoformat(),
                        lead.get('icp_fit_score'), lead.get('icp_tier'), lead.get('icp_name'),
                        lead.get('eval_grade'), lead.get('eval_omega'), lead.get('omega_score'),
                        lead.get('correlation_id'), lead.get('fleet_size'), lead.get('whale_tier'),
                        lead.get('logistics_score'), json.dumps(lead.get('satellite')) if lead.get('satellite') else None,
                        json.dumps(lead.get('enrich_logistics')) if lead.get('enrich_logistics') else None
                    ))
                total += 1
            
            con.commit()
            con.close()
            
            if len(leads) < 1000:
                break
            offset += 1000
        
        results['crm_leads'] = total
    except Exception as e:
        results['crm_leads'] = {'error': str(e)}
    
    # Sync lane_leads
    try:
        offset = 0
        limit = 1000
        total = 0
        while True:
            leads = supabase_client.select("lane_leads", limit=limit, offset=offset)
            if not leads:
                break
            
            con = sqlite3.connect("/root/empire_os/empire_os.db", timeout=30)
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA busy_timeout=30000")
            
            for lead in leads:
                lead_ref = lead.get('lead_ref') or lead.get('prospect_id') or lead.get('id')
                if not lead_ref:
                    continue
                
                existing = con.execute("SELECT lead_ref FROM lane_leads WHERE lead_ref = ?", (lead_ref,)).fetchone()
                
                if existing:
                    con.execute("""
                        UPDATE lane_leads SET
                            lane_id = ?, prospect_id = ?, status = ?, omega_score = ?, omega_tier = ?,
                            notes = ?, created_at = ?, buyer_id = ?, niche = ?, metro = ?
                        WHERE lead_ref = ?
                    """, (
                        lead.get('lane_id'), lead.get('prospect_id'), lead.get('status'),
                        lead.get('omega_score'), lead.get('omega_tier'), lead.get('notes'),
                        lead.get('created_at'), lead.get('buyer_id'), lead.get('niche'),
                        lead.get('metro'), lead_ref
                    ))
                else:
                    con.execute("""
                        INSERT INTO lane_leads (
                            lead_ref, lane_id, prospect_id, status, omega_score, omega_tier,
                            notes, created_at, buyer_id, niche, metro
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        lead_ref,
                        lead.get('lane_id'), lead.get('prospect_id'), lead.get('status'),
                        lead.get('omega_score'), lead.get('omega_tier'), lead.get('notes'),
                        lead.get('created_at'), lead.get('buyer_id'), lead.get('niche'),
                        lead.get('metro')
                    ))
                total += 1
            
            con.commit()
            con.close()
            
            if len(leads) < 1000:
                break
            offset += 1000
        
        results['lane_leads'] = total
    except Exception as e:
        results['lane_leads'] = {'error': str(e)}
    
    return results


# Convenience functions for hub compatibility
def get_backend():
    """Return SQLite replica for reads, Supabase for writes."""
    return sqlite_replica


# Write operations go to Supabase
def sb_insert(table: str, row: dict) -> list:
    return supabase_client.insert(table, row)

def sb_select(table: str, columns: str = "*", filters: dict = None, limit: int = 100, offset: int = 0) -> list:
    return supabase_client.select(table, columns, filters, limit=limit, offset=offset)

def sb_update(table: str, match: dict, values: dict) -> list:
    return supabase_client.update(table, match, values)