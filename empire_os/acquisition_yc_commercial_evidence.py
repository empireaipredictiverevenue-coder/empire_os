"""Evidence-only deep review of YC acquisition shortlist with existing Jev.

Read-only detailed original job descriptions expose commercial needs to investigate,
not vendor procurement proof. Never auto-approve copy, contacts, or EmpireDB writes.
"""
from __future__ import annotations
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from empire_os.jev_client_pain_discovery import discover_client_pains
from empire_os.acquisition_yc_first_party_sweep import _ready_products

BASE = "https://www.ycombinator.com"
MAX_DETAIL = 600_000
MAX_JOB_PAGES = 3
HINTS: dict[str, tuple[str, ...]] = {
    "inbound_capacity_pressure": (
        r"far more enterprise inbound than we can handle",
        r"growing pile of inbound leads",
        r"can't keep up with.*(?:leads|demos|requests)",
    ),
    "sales_system_buildout": (
        r"repeatable sales process",
        r"sales engine from the ground up",
        r"build and test sales pipelines",
        r"outbound motion from zero",
    ),
    "vertical_gtm_expansion": (
        r"vertical GTM (?:playbooks|strategies)",
        r"competitive intelligence",
        r"top of funnel opportunities",
    ),
    "customer_expansion_operations": (
        r"renewals, expansions",
        r"customer success end.to.end",
        r"product impact & engagement",
    ),
}
COMPILED = {key: tuple(re.compile(p, re.I | re.S) for p in patterns)
            for key, patterns in HINTS.items()}


def _fetch_yc_detail(url: str) -> bytes:
    """Allowlisted GET without credentials or provider-circuit bypass."""
    p = urlsplit(url)
    if (p.scheme != "https" or p.hostname != "www.ycombinator.com"
            or not re.fullmatch(r"/companies/[a-z0-9-]+/jobs/[A-Za-z0-9-]{5,120}", p.path)
            or p.username or p.password or p.query or p.fragment):
        raise ValueError("only canonical YC role descriptions allowed")
    request = Request(url, headers={"User-Agent":"Mozilla/5.0 (compatible; EmpireOS-ReadOnly-Research/1.0)"})
    with urlopen(request, timeout=8) as response:
        if urlsplit(response.geturl()).hostname != "www.ycombinator.com":
            raise ValueError("role redirect must remain with source owner")
        payload = response.read(MAX_DETAIL + 1)
    if not payload or len(payload) > MAX_DETAIL:
        raise ValueError("bounded YC role page required")
    return payload


def _parse_role_links(jobs_html: bytes, *, company_slug: str, relevant_titles: list[str]) -> list[tuple[str, str]]:
    if not jobs_html or len(jobs_html) > 800_000:
        raise ValueError("bounded source listing required")
    soup = BeautifulSoup(jobs_html, "html.parser")
    selected = []
    seen = set()
    for a in soup.select("a[href]"):
        path = a.get("href", "").split("?", 1)[0]
        if not re.fullmatch(rf"/companies/{re.escape(company_slug)}/jobs/[A-Za-z0-9-]{{5,120}}", path):
            continue
        title = a.get_text(" ", strip=True)
        if title not in relevant_titles or path in seen:
            continue
        seen.add(path)
        selected.append((title, BASE + path))
        if len(selected) == MAX_JOB_PAGES:
            break
    return selected


def _extract_detail(html: bytes, *, company: str, title: str) -> tuple[str, str]:
    if not html or len(html) > MAX_DETAIL:
        raise ValueError("bounded source required")
    soup = BeautifulSoup(html, "html.parser")
    page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if page_title.casefold() != f"{title} at {company} | Y Combinator".casefold():
        raise ValueError("role description title identity mismatch")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    start = text.lower().find("about the role")
    if start < 0:
        raise ValueError("role section unavailable")
    text = text[start + len("about the role"):]
    # Bounded original description for Jev; not a purchasing/permission claim.
    end = text.lower().find("about " + company.lower(), 700)
    if end > 700:
        text = text[:end]
    return text[:7000], sha256(html).hexdigest()


def _evidence_hints(text: str) -> list[dict[str, str]]:
    claims = []
    for key, patterns in COMPILED.items():
        for expression in patterns:
            match = expression.search(text)
            if match:
                a, b = match.span()
                claims.append({
                    "topic": key,
                    "original_excerpt": " ".join(text[max(0,a-85):min(len(text),b+105)].split())[:280],
                    "classification": "JOB_DESCRIPTION_SIGNAL_NOT_PROCUREMENT",
                })
                break
    return claims


def review_six(
    *,
    source: Mapping, catalog: Mapping, now: datetime,
    listing_fetch: Callable[[str], bytes],
    detail_fetch: Callable[[str], bytes],
) -> dict:
    if now.tzinfo is None or source.get("schema_version") != "empire.acquisition_yc_first_party_sweep.v1":
        raise ValueError("canonical prior research receipt required")
    if source.get("mode") != "OBSERVE" or source.get("outbound_authorized") is not False or source.get("crm_writes") is not False:
        raise ValueError("non-executing source required")
    original = source.get("records")
    if not isinstance(original, list) or len(original) != 20:
        raise ValueError("full previous YC twenty research batch required")
    if not isinstance(catalog, Mapping):
        raise ValueError("verified commercial product owner snapshot required")
    catalog_codes = _ready_products(catalog, now.astimezone(timezone.utc))
    results = []
    observations = []
    seen = set()
    for row in original:
        if not isinstance(row, Mapping) or not row.get("relevant_job_titles"):
            continue
        if (row.get("qualified_for_copy") is not False
            or row.get("outbound_authorized") is not False
            or row.get("independent_buying_trigger_verified") is not False):
            raise ValueError("unverified company selection required")
        company = row.get("company")
        src = row.get("yc_original_listing_url")
        slug = urlsplit(str(src)).path.split("/")
        if (not isinstance(company, str) or len(slug) != 4
            or slug[:2] != ["", "companies"] or slug[-1] != "jobs"
            or urlsplit(str(src)).hostname != "www.ycombinator.com"):
            raise ValueError("canonical YC source required")
        ref = row.get("prospect_ref")
        if not isinstance(ref, str) or ref in seen:
            raise ValueError("unique canonical prospect ref required")
        seen.add(ref)
        details = []
        failures = 0
        try:
            listing = listing_fetch(str(src))
            links = _parse_role_links(listing, company_slug=slug[2],
                                      relevant_titles=row["relevant_job_titles"])
        except Exception:
            links = []
            failures += 1
        for title, url in links:
            try:
                text, digest = _extract_detail(detail_fetch(url), company=company, title=title)
                hints = _evidence_hints(text)
                details.append({
                    "job_title": title, "original_source_url": url,
                    "original_content_sha256": digest,
                    "observed_at": now.astimezone(timezone.utc).isoformat(),
                    "posting_date_verified": False, "commercial_clues": hints,
                    "buyer_purchase_request_verified": False,
                })
                observations.append({"source": "public_job_post", "url": url,
                     "title": title, "text": text,
                     "observed_at": now.astimezone(timezone.utc).isoformat(),
                     "niche": str(row.get("niche") or "")})
            except Exception:
                failures += 1
        # Do not re-use the prior sweep's generic Search Growth suggestion:
        # role hiring is not sufficient evidence that a search product fits.
        # Only a specific described function can produce a product hypothesis.
        topics = {c["topic"] for d in details for c in d["commercial_clues"]}
        candidate = "competitor_search_gap" if "vertical_gtm_expansion" in topics else None
        product = candidate if candidate in catalog_codes else None
        if "inbound_capacity_pressure" in topics:
            owner = "Founder or Head of Sales (identity and authority unverified)"
            next_evidence = "Obtain an authorised statement that outside help is wanted for existing inbound capacity and conversion; verify service fit, scope and commercial terms."
        elif "vertical_gtm_expansion" in topics:
            owner = "Head of Product Marketing or GTM (identity and authority unverified)"
            next_evidence = "Confirm a need for third-party competitor search-gap intelligence, target verticals, use rights, scope and purchasing authority."
        elif "sales_system_buildout" in topics:
            owner = "Founder or Sales Leadership (identity and authority unverified)"
            next_evidence = "Confirm whether the sales buildout needs approved outside research rather than only an internal employee."
        elif "customer_expansion_operations" in topics:
            owner = "Customer Success or Revenue Leadership (identity and authority unverified)"
            next_evidence = "Verify a customer retention or expansion problem and external vendor appetite independently of staffing responsibilities."
        else:
            owner = "Commercial decision maker to establish"
            next_evidence = "Find a dated, company-owned problem or procurement statement and verify external purchase interest before product mapping."
        results.append({
            "prospect_ref": ref, "company": company,
            "niche": row.get("niche"),
            "job_details": details,
            "detail_fetch_failures": failures,
            "commercial_clue_count": sum(len(d["commercial_clues"]) for d in details),
            "potential_product_code": product,
            "product_catalog_readiness_observed": product is not None,
            "product_match_reason": (
                "VERTICAL_GTM_COMPETITOR_RESEARCH_HYPOTHESIS"
                if product else "NO_DEFENSIBLE_PRODUCT_MATCH_YET"),
            "independently_verified_buyer_need": False,
            "buyer_procurement_request_verified": False,
            "authorized_decision_maker_identified": False,
            "decision_maker_role_to_verify": owner,
            "product_fit_verified": False,
            "copy_review_eligible": False,
            "suppression_verified": False,
            "crm_write_authorized": False,
            "outbound_authorized": False,
            "status": "RESEARCH_HYPOTHESIS_ONLY",
            "next_evidence": next_evidence,
        })
    jev = discover_client_pains(observations, now=now)
    return {
        "schema_version":"empire.acquisition_yc_commercial_evidence.v1",
        "mode":"OBSERVE",
        "companies_reviewed":len(results),
        "original_role_pages_reviewed":sum(len(r["job_details"]) for r in results),
        "companies_with_commercial_clues":sum(r["commercial_clue_count"]>0 for r in results),
        "companies_with_catalog_product_hypotheses":sum(r["potential_product_code"] is not None for r in results),
        "jev_observations":jev["observations_submitted"],
        "jev_review_lanes":jev["review_lane_counts"],
        "confirmed_procurement_signals":0,
        "authorized_decision_makers":0,
        "copy_review_eligible":0,
        "records":results,
        "crm_writes":False,"outbound_authorized":False,
        "model_training_authorized":False,"verified_revenue":None,
    }


def run_current_review(repo: Path) -> dict:
    from empire_os.acquisition_yc_first_party_sweep import _get_yc
    source = json.loads((repo / "runtime/acquisition_research/yc_20_review_20261023.json").read_text())
    catalog = json.loads((repo / "runtime/commercial_catalog/latest.json").read_text())
    return review_six(source=source,catalog=catalog, now=datetime.now(timezone.utc),
                      listing_fetch=_get_yc, detail_fetch=_fetch_yc_detail)


if __name__ == "__main__":
    print(json.dumps(run_current_review(Path(__file__).resolve().parents[1]), indent=2))
