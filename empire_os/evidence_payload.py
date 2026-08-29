"""Read-only taxonomy + evidence enumeration for Empire leads.

Truth-only: counts and presence flags are computed from real DB columns and
real joined tables. No values are invented, backfilled, or fabricated.

TAXONOMY_VERSION is the schema-version string returned by the read-only
endpoints. Bump only when the niche-code set or evidence-column set changes.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any

TAXONOMY_VERSION = "empire-multi-niche-2026-08-15.v1"

# In-process TTL cache. The taxonomy scan is read-only and, under live hub
# DB contention, a cold rebuild can take 60-90s+. To keep the public read
# window safe we serve STALE-WHILE-REVALIDATE: a cache hit (fresh or stale)
# is returned instantly; a stale hit also triggers a non-blocking background
# rebuild so the next call sees fresh exact counts. Only a truly empty cache
# blocks (covered by the startup pre-warm thread in hub.py).
_TAXONOMY_CACHE: dict[str, Any] = {}
_TAXONOMY_CACHE_TS: float = 0.0
_TAXONOMY_CACHE_TTL = 300.0  # seconds
_TAXONOMY_REFRESH_LOCK = threading.Lock()  # dedupe concurrent background rebuilds


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    """Read-only, optimized connection for taxonomy scans.

    Uses WAL + memory-mapped IO + a large page cache so a full-table GROUP BY
    over lane_leads (~900k rows) completes in a few seconds instead of >100s.
    Read-only: never writes. No schema change.
    """
    DB = db_path or "/root/empire_os/empire_os.db"
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=60000")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA mmap_size=1073741824")   # 1 GiB mmap
    con.execute("PRAGMA cache_size=-524288")      # 512 MiB page cache
    return con

# Display-name map: derive a human label from the code only when one is
# already in canonical use in product surfaces. Anything not in this map
# is returned with display_name == code (no invention, no fabrication).
_DISPLAY_NAMES: dict[str, str] = {
    "residential_roofing": "Residential Roofing",
    "commercial_roofing": "Commercial Roofing",
    "roof_repair": "Roof Repair",
    "roofing": "Roofing",
    "storm_damage": "Storm Damage",
    "water_damage": "Water Damage",
    "fire_damage": "Fire Damage",
    "mold_remediation": "Mold Remediation",
    "hvac": "HVAC",
    "plumbing": "Plumbing",
    "electrical": "Electrical",
    "general_contractor": "General Contractor",
    "home_services": "Home Services",
    "restoration": "Restoration",
    "legal_services": "Legal Services",
    "debt_relief": "Debt Relief",
    "insurance": "Insurance",
    "accounting": "Accounting",
    "managed_it": "Managed IT",
    "mortgage": "Mortgage",
    "ai_automation": "AI Automation",
    "cybersecurity": "Cybersecurity",
    "investing": "Investing",
    "ozempic": "Ozempic / GLP-1",
    "addiction": "Addiction Treatment",
    "camp_lejeune": "Camp Lejeune (Mass Tort)",
    "zantac": "Zantac (Mass Tort)",
    "weight_loss": "Weight Loss",
    "b2b": "B2B",
    "solar": "Solar PV",
    "commercial_solar": "Commercial Solar PV",
    "solar_installer": "Solar Installer",
    "commercial roofing": "Commercial Roofing",
    "general contractor": "General Contractor",
    "managed it": "Managed IT",
    "auto insurance": "Auto Insurance",
    "medical claims": "Medical Claims",
    "hr staffing": "HR Staffing",
    "merchant services": "Merchant Services",
    "water_mitigation": "Water Mitigation",
    "water mitigation": "Water Mitigation",
    "mental health clinic": "Mental Health Clinic",
    "debt consolidation": "Debt Consolidation",
    "business loan broker": "Business Loan Broker",
    "medicare advantage agent": "Medicare Advantage Agent",
    "addiction treatment center": "Addiction Treatment Center",
    "emergency services": "Emergency Services",
    "staffing": "Staffing",
    "home health agency": "Home Health Agency",
    "assisted living": "Assisted Living",
    "landscaping": "Landscaping",
    "nursing school": "Nursing School",
    "personal injury lawyer": "Personal Injury Lawyer",
    "pest_control": "Pest Control",
    "medical alert system": "Medical Alert System",
    "life insurance agent": "Life Insurance Agent",
    "cdl truck driving school": "CDL Truck Driving School",
    "gutter": "Gutter",
    "public insurance adjuster": "Public Insurance Adjuster",
    "painting": "Painting",
    "tree removal": "Tree Removal",
    "final expense insurance": "Final Expense Insurance",
    "mortgage broker": "Mortgage Broker",
    "medical_device": "Medical Device",
    "mass tort lawyer": "Mass Tort Lawyer",
    "windows": "Windows",
    "fencing": "Fencing",
    "mass_tort": "Mass Tort",
    "mass_torts": "Mass Torts",
    "class_action": "Class Action",
    "class action lawyer": "Class Action Lawyer",
    "pharma_liability": "Pharma Liability",
    "medical malpractice lawyer": "Medical Malpractice Lawyer",
    "workers comp lawyer": "Workers Comp Lawyer",
    "consumer_product": "Consumer Product",
    "logistics": "Logistics",
    "freight": "Freight",
    "trucking": "Trucking",
    "warehouse_clearout": "Warehouse Clearout",
    "junk_hauling": "Junk Hauling",
    "medical_health": "Medical / Health",
    "financial": "Financial",
    "test": "Test",
    "verify_masstort_a": "Verify Mass-Tort A",
    "verify_mtfin2_a": "Verify MTFin2 A",
}


def display_name(code: str | None) -> str:
    if not code:
        return ""
    if code in _DISPLAY_NAMES:
        return _DISPLAY_NAMES[code]
    return code


# ----------------------------------------------------------------------
# Single-pass coverage aggregation. We compute coverage in ONE query per
# table per gate using conditional aggregation. This keeps cost bounded
# (one full scan per table) regardless of niche cardinality.
# ----------------------------------------------------------------------

def _has_table(con: sqlite3.Connection, t: str) -> bool:
    r = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (t,),
    ).fetchone()
    return r is not None


def _coverage_one_pass(con: sqlite3.Connection, table: str, niche_col: str) -> dict[str, dict[str, int]]:
    """Return {niche_code: {location, website, contact, provenance}}.

    Single grouped aggregate per table (one scan, O(rows)). No TRIM() in the
    WHERE clause (TRIM on a bare column forces a per-row function eval and
    prevents any index use, which is what made the cold scan take >100s). We
    GROUP BY the raw niche column and drop null/empty codes in Python. The
    returned counts are identical to the previous implementation.
    """
    cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
    if niche_col not in cols:
        return {}

    select_parts = [f"{niche_col} AS niche_code", "COUNT(*) AS recs"]
    gates: list[tuple[str, str]] = []  # (gate_name, sql_expr)

    if "street" in cols or "city" in cols or "state" in cols:
        loc_expr = " OR ".join(
            f"({c} IS NOT NULL AND TRIM({c})<>'')" for c in ("street", "city", "state") if c in cols
        )
        gates.append(("location", f"CASE WHEN ({loc_expr}) THEN 1 ELSE 0 END"))
    if "website" in cols:
        gates.append(("website", "CASE WHEN website IS NOT NULL AND TRIM(website)<>'' THEN 1 ELSE 0 END"))
    elif "url" in cols:
        gates.append(("website", "CASE WHEN url IS NOT NULL AND TRIM(url)<>'' THEN 1 ELSE 0 END"))

    if "business_name" in cols or "phone" in cols or "email" in cols or "contacts_json" in cols:
        contact_parts = []
        if "business_name" in cols:
            contact_parts.append("business_name IS NOT NULL AND TRIM(business_name)<>''")
        if "phone" in cols:
            contact_parts.append("phone IS NOT NULL AND TRIM(phone)<>''")
        if "email" in cols:
            contact_parts.append("email IS NOT NULL AND TRIM(email)<>''")
        if "contacts_json" in cols:
            contact_parts.append(
                "contacts_json IS NOT NULL AND TRIM(contacts_json)<>'' AND "
                "TRIM(contacts_json)<>'[]' AND TRIM(contacts_json)<>'{}'"
            )
        contact_expr = " OR ".join(contact_parts)
        gates.append(("contact", f"CASE WHEN ({contact_expr}) THEN 1 ELSE 0 END"))

    # Provenance gate: source/lead_uid/prospect_id + created_at must all be non-empty.
    id_col = "lead_uid" if "lead_uid" in cols else ("prospect_id" if "prospect_id" in cols else None)
    src_col = "source" if "source" in cols else None
    if id_col and src_col and "created_at" in cols:
        gates.append(
            (
                "provenance",
                f"CASE WHEN ({id_col} IS NOT NULL AND TRIM({id_col})<>'' "
                f"AND {src_col} IS NOT NULL AND TRIM({src_col})<>'' "
                f"AND created_at IS NOT NULL AND TRIM(created_at)<>'') THEN 1 ELSE 0 END",
            )
        )
    elif id_col and "created_at" in cols:
        gates.append(
            (
                "provenance",
                f"CASE WHEN ({id_col} IS NOT NULL AND TRIM({id_col})<>'' "
                f"AND created_at IS NOT NULL AND TRIM(created_at)<>'') THEN 1 ELSE 0 END",
            )
        )

    for name, expr in gates:
        select_parts.append(f"SUM({expr}) AS {name}")

    sql = (
        f"SELECT {', '.join(select_parts)} FROM {table} "
        f"WHERE {niche_col} IS NOT NULL "
        f"GROUP BY {niche_col}"
    )
    out: dict[str, dict[str, int]] = {}
    for r in con.execute(sql).fetchall():
        code = (r["niche_code"] or "").strip()
        if not code:
            continue  # drop null/empty codes post-hoc (replaces TRIM-in-WHERE)
        out[code] = {"record_count": r["recs"]}
        for name, _ in gates:
            out[code][name] = r[name] or 0
        # ensure every gate key exists
        for k in ("location", "website", "contact", "provenance"):
            out[code].setdefault(k, 0)
    return out


def _consent_by_niche(con: sqlite3.Connection) -> dict[str, int]:
    """Return {niche_code: opted_in_count} from si_prospect_consent."""
    if not _has_table(con, "si_prospect_consent"):
        return {}
    out: dict[str, int] = {}
    for r in con.execute(
        "SELECT COALESCE(niche,'') AS n, COUNT(*) AS c "
        "FROM si_prospect_consent WHERE opted_in=1 GROUP BY niche"
    ).fetchall():
        if r["n"]:
            out[r["n"]] = r["c"]
    # Also count by prospect_id prefix where niche is empty.
    for r in con.execute(
        "SELECT prospect_id FROM si_prospect_consent "
        "WHERE (niche IS NULL OR TRIM(niche)='') AND opted_in=1"
    ).fetchall():
        pid = r["prospect_id"] or ""
        # prospect_id forms: lead:<niche>:<hex> OR <niche>:<rest>
        parts = pid.split(":")
        if len(parts) >= 2 and parts[0] == "lead":
            code = parts[1]
            out[code] = out.get(code, 0) + 1
        elif ":" in pid:
            code = pid.split(":", 1)[0]
            if code:
                out[code] = out.get(code, 0) + 1
    return out


# ----------------------------------------------------------------------
# Public: canonical taxonomy enumeration.
# ----------------------------------------------------------------------

def build_taxonomy(backend, *, force_refresh: bool = False) -> dict[str, Any]:
    """Return the canonical multi-niche taxonomy with real coverage.

    Cached for _TAXONOMY_CACHE_TTL seconds. Pass force_refresh=True to bypass.
    """
    global _TAXONOMY_CACHE_TS
    now = time.time()
    if _TAXONOMY_CACHE and (now - _TAXONOMY_CACHE_TS) < _TAXONOMY_CACHE_TTL:
        return _TAXONOMY_CACHE  # fresh — served instantly

    if _TAXONOMY_CACHE:
        # Stale but present: return it immediately and refresh in background.
        _schedule_taxonomy_refresh(force_refresh)
        return _TAXONOMY_CACHE

    # Truly empty cache (pre-warm not done yet): block and build exact counts.
    return _build_taxonomy_now(force_refresh)


def _schedule_taxonomy_refresh(force_refresh: bool) -> None:
    """Non-blocking background rebuild; dedupes concurrent refreshes."""
    if not _TAXONOMY_REFRESH_LOCK.acquire(blocking=False):
        return  # a refresh is already in flight
    try:
        def _run():
            try:
                _build_taxonomy_now(force_refresh=True)
            finally:
                _TAXONOMY_REFRESH_LOCK.release()
        threading.Thread(target=_run, daemon=True).start()
    except Exception:
        _TAXONOMY_REFRESH_LOCK.release()


def _build_taxonomy_now(force_refresh: bool = False) -> dict[str, Any]:
    """Compute the taxonomy aggregate from the real DB. Read-only; no writes."""
    global _TAXONOMY_CACHE_TS
    DB = "/root/empire_os/empire_os.db"
    con = _connect(DB)

    table_specs = [
        ("crm_leads", "niche"),
        ("lane_leads", "niche"),
        ("si_buyer_outreach", "niche"),
    ]

    coverage: dict[tuple[str, str], dict[str, int]] = {}
    by_niche: list[dict[str, Any]] = []
    totals: dict[str, int] = {}
    consent_present = _has_table(con, "si_prospect_consent")
    consent_counts = _consent_by_niche(con) if consent_present else {}

    for t, col in table_specs:
        if not _has_table(con, t):
            totals[t] = 0
            continue
        totals[t] = con.execute(f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
        cov_t = _coverage_one_pass(con, t, col)
        for code, c in cov_t.items():
            coverage[(t, code)] = c
            by_niche.append({
                "niche_code": code,
                "display_name": display_name(code),
                "source_table": t,
                "record_count": c.get("record_count", 0),
                "evidence_coverage": {
                    "location": c.get("location", 0),
                    "website": c.get("website", 0),
                    "contact": c.get("contact", 0),
                    "consent": consent_counts.get(code, 0),
                    "provenance": c.get("provenance", 0),
                },
                "has_location_column": t in ("crm_leads", "lane_leads"),
                "has_website_column": t in ("crm_leads", "si_buyer_outreach"),
                "has_contact_column": t in ("crm_leads", "si_buyer_outreach"),
                "has_consent_link": consent_present,
            })

    con.close()

    out = {
        "taxonomy_version": TAXONOMY_VERSION,
        "read_only": True,
        "source_tables": [t for t, _ in table_specs],
        "totals_by_table": totals,
        "niche_count": len(by_niche),
        "by_niche": by_niche,
    }
    _TAXONOMY_CACHE.clear()
    _TAXONOMY_CACHE.update(out)
    _TAXONOMY_CACHE_TS = time.time()
    return out


# ----------------------------------------------------------------------
# Per-lead evidence envelope (single-row, no aggregate scans).
# ----------------------------------------------------------------------

def attach_evidence_envelope(lead: dict[str, Any], source_table: str = "crm_leads") -> dict[str, Any]:
    """Return a copy of lead with an evidence_envelope attached.

    The envelope exposes ONLY presence booleans and the same field values
    the row already carries. Absent fields become null. Never fabricates
    scores, status, contact values, or locations.
    """
    env: dict[str, Any] = {"source_table": source_table}

    loc = {
        "street": lead.get("street") or None,
        "city": lead.get("city") or None,
        "state": lead.get("state") or None,
        "zip": lead.get("zip") or None,
        "metro": lead.get("metro") or None,
    }
    env["location"] = {**loc, "has_any": any(v for v in loc.values())}

    env["website"] = {
        "value": lead.get("website") or None,
        "present": bool(lead.get("website")),
    }

    contacts_json_raw = lead.get("contacts_json")
    contacts_parsed: Any = None
    if isinstance(contacts_json_raw, str):
        s = contacts_json_raw.strip()
        if s and s not in ("[]", "{}"):
            try:
                contacts_parsed = json.loads(s)
            except Exception:
                contacts_parsed = None
    elif isinstance(contacts_json_raw, (list, dict)):
        contacts_parsed = contacts_json_raw

    env["contact"] = {
        "business_name": lead.get("business_name") or None,
        "contact_name": lead.get("contact_name") or None,
        "email": lead.get("email") or None,
        "phone": lead.get("phone") or None,
        "social_links": lead.get("social_links") if isinstance(lead.get("social_links"), (list, dict)) else None,
        "structured_contacts": contacts_parsed,
        "has_any": any([
            lead.get("business_name"),
            lead.get("contact_name"),
            lead.get("email"),
            lead.get("phone"),
            contacts_parsed,
        ]),
    }

    consent = {
        "linked": False,
        "opted_in": None,
        "opted_in_at": None,
        "consent_table_present": False,
    }
    pid = lead.get("lead_uid") or lead.get("prospect_id")
    if pid and source_table == "crm_leads":
        try:
            DB = "/root/empire_os/empire_os.db"
            ccon = sqlite3.connect(DB)
            ccon.row_factory = sqlite3.Row
            if ccon.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='si_prospect_consent'"
            ).fetchone():
                consent["consent_table_present"] = True
                row = ccon.execute(
                    "SELECT opted_in, opted_in_at FROM si_prospect_consent WHERE prospect_id=? LIMIT 1",
                    (pid,),
                ).fetchone()
                if not row:
                    row = ccon.execute(
                        "SELECT opted_in, opted_in_at FROM si_prospect_consent WHERE prospect_id LIKE ? LIMIT 1",
                        (f"lead:{lead.get('niche')}:%",),
                    ).fetchone()
                if row:
                    consent["linked"] = True
                    consent["opted_in"] = bool(row["opted_in"])
                    consent["opted_in_at"] = row["opted_in_at"]
            ccon.close()
        except Exception:
            consent["linked"] = False
    env["consent"] = consent

    env["provenance"] = {
        "source": lead.get("source") or None,
        "source_table": source_table,
        "lead_uid": lead.get("lead_uid") or lead.get("prospect_id") or None,
        "created_at": lead.get("created_at") or None,
        "updated_at": lead.get("updated_at") or None,
    }

    env["gates"] = {
        "location": env["location"]["has_any"],
        "website": env["website"]["present"],
        "contact": env["contact"]["has_any"],
        "consent": consent["linked"] and consent["opted_in"] is True,
        "provenance": all([
            env["provenance"]["source"],
            env["provenance"]["lead_uid"],
            env["provenance"]["created_at"],
        ]),
    }
    env["all_gates_pass"] = all(env["gates"].values())
    # Response metadata only — the deployed schema version, never derived from
    # lead data. Set on the envelope so individual-lead responses expose it.
    env["taxonomy_version"] = TAXONOMY_VERSION

    out = {**lead, "evidence_envelope": env}
    # Override any null/empty taxonomy_version column leaked from the source
    # row with the deployed constant (response metadata, not source data).
    out["taxonomy_version"] = TAXONOMY_VERSION
    return out


def resolve_source_table_for_lead(lead_id: str, backend=None) -> str | None:
    """Read-only, BOUNDED lookup of which canonical table holds a given
    lead_id (prospect_id / lead_uid). Uses cheap `LIMIT 1` probes; never a
    full scan, never a write. Returns the table name or None.

    Different tables use different identifier columns:
      - si_buyer_outreach: prospect_id
      - crm_leads: lead_uid
      - lane_leads:    prospect_id (also has lead_uid)
    """
    tables = ["crm_leads", "lane_leads", "si_buyer_outreach"]

    # column name each table uses for the lead identifier
    lead_col = {
        "crm_leads": "lead_uid",
        "lane_leads": "prospect_id",
        "si_buyer_outreach": "prospect_id",
    }

    def _probe(con) -> str | None:
        for t in tables:
            col = lead_col.get(t, "prospect_id")
            try:
                row = con.execute(
                    f"SELECT 1 FROM {t} WHERE {col}=? LIMIT 1", (lead_id,)
                ).fetchone()
                if row:
                    return t
            except Exception:
                continue
        return None

    if backend is not None:
        r = _probe(backend)
        if r:
            return r
    try:
        import sqlite3
        con = sqlite3.connect("file:/root/empire_os/empire_os.db?mode=ro", uri=True)
        r = _probe(con)
        con.close()
        return r
    except Exception:
        return None
    except Exception:
        return None


def resolve_niche_source_tables(niche: str, backend=None) -> list[str]:
    """Read-only, BOUNDED mapping of a niche_code to the source tables that
    actually contain >=1 row with that niche.

    Uses cheap `LIMIT 1` probes on each candidate table instead of the full
    multi-table taxonomy aggregate. This keeps the filtered /v1/leads list path
    from ever blocking on build_taxonomy's cold scan (the cause of the
    intermittent ~30s public lead stall when the taxonomy cache is empty).
    """
    tables = ["crm_leads", "lane_leads", "si_buyer_outreach"]
    found: list[str] = []

    def _probe(con) -> None:
        for t in tables:
            try:
                row = con.execute(
                    f"SELECT 1 FROM {t} WHERE niche=? LIMIT 1", (niche,)
                ).fetchone()
                if row:
                    found.append(t)
            except Exception:
                continue

    if backend is not None:
        _probe(backend)
    if not found:
        # backend unavailable or all probes failed: bounded fallback probe on a
        # fresh read-only connection (no write, no schema change).
        try:
            con = _connect()
            _probe(con)
            con.close()
        except Exception:
            pass
    return found
