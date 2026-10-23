"""Read-only 20-company research sweep through existing YC sources and Jev.

Uses the already-committed, prioritized company list and canonical product
catalog snapshot. Search Fabric health is observed, never bypassed or reset.
A live job listing is an observed hiring signal, not a dated purchase request.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from empire_os.acquisition_existing_pool_audit import read_only_current_snapshot
from empire_os.jev_client_pain_discovery import discover_client_pains
from empire_os.search_fabric.reliable_search import provider_health, search_reliable

MAX_BATCH = 20
MAX_RESPONSE_BYTES = 800_000
ROLE = re.compile(r"\b(sales|marketing|growth|revenue|business development|account executive|demand generation|gtm)\b", re.I)


def _get_yc(url: str) -> bytes:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "www.ycombinator.com" or not re.fullmatch(r"/companies/[a-z0-9-]+/jobs", parsed.path):
        raise ValueError("canonical YC company jobs URL required")
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; EmpireOS-ReadOnly-Research/1.0)"})
    with urlopen(req, timeout=9) as response:
        effective = urlsplit(response.geturl())
        if effective.hostname != "www.ycombinator.com":
            raise ValueError("redirect outside source owner blocked")
        return response.read(MAX_RESPONSE_BYTES + 1)


def _roles(page: bytes, *, company: str) -> tuple[list[str], str]:
    if not page or len(page) > MAX_RESPONSE_BYTES:
        raise ValueError("empty or oversized first-party page")
    soup = BeautifulSoup(page, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if not title.lower().startswith("jobs at ") or "| y combinator" not in title.lower():
        raise ValueError("first-party source page is not a company job listing")
    expected = company.casefold().strip()
    actual = title.lower().removeprefix("jobs at ").split("| y combinator", 1)[0].strip()
    if actual != expected:
        raise ValueError("company title mismatch")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    lines = [re.sub(r"\s+", " ", s).strip() for s in soup.get_text("\n").splitlines()]
    lines = [line for line in lines if line]
    try:
        begin = next(i for i, line in enumerate(lines) if line == "Jobs at")
        finish = next(i for i, line in enumerate(lines[begin + 2:], begin + 2) if line == "Why you should join")
    except StopIteration:
        begin = next((i for i, line in enumerate(lines) if line == "Jobs at"), -1)
        finish = len(lines)
    section = lines[max(begin + 2, 0):finish] if begin >= 0 else []
    if not section:
        raise ValueError("jobs section missing")
    positions = []
    for idx, line in enumerate(section):
        if not ROLE.search(line):
            continue
        if len(line) > 105 or len(line) < 6 or any(mark in line.lower() for mark in ("remote ", "company", "interested in", "why you")):
            continue
        if line not in positions:
            positions.append(line)
    return positions[:12], sha256(page).hexdigest()


def _ready_products(snapshot: Mapping, now: datetime) -> set[str]:
    try:
        created = datetime.fromisoformat(str(snapshot["generated_at"]).replace("Z", "+00:00"))
    except (KeyError, ValueError, TypeError):
        return set()
    age = now - created.astimezone(timezone.utc)
    if not timedelta(0) <= age <= timedelta(days=2):
        return set()
    return {str(p["product_code"]) for p in snapshot.get("products", ())
            if isinstance(p, Mapping) and p.get("active") is True
            and p.get("binding_terms_ready") is True
            and p.get("catalog_state") == "VERIFIED"
            and p.get("version_state") == "VERIFIED"}


def sweep_first_party(
    *,
    assignments: list[Mapping],
    catalog: Mapping,
    now: datetime,
    fetch: Callable[[str], bytes] = _get_yc,
    search_health: Mapping | None = None,
    search_lookup: Callable[..., Mapping] | None = None,
) -> dict:
    if now.utcoffset() is None or not isinstance(assignments, list) or not 0 < len(assignments) <= MAX_BATCH:
        raise ValueError("bounded timestamped research batch required")
    ready_products = _ready_products(catalog, now.astimezone(timezone.utc))
    rows = []
    observations = []
    seen = set()
    # Existing Search Fabric remains the sole search provider. Its protective
    # cooldown MUST NOT be bypassed by a new search implementation.
    health = search_health or {}
    search_available = (search_lookup is not None
        and health.get("circuit_open") is False
        and health.get("last_state") not in ("CIRCUIT_OPEN", "DEGRADED"))
    search_attempts = 0
    search_result_rows = 0
    for assignment in assignments:
        if assignment.get("status") != "RESEARCH_ONLY" or assignment.get("contact_authorized") is not False:
            raise ValueError("source research-only status required")
        ref = assignment.get("prospect_ref")
        src = assignment.get("source_url")
        if not isinstance(ref, str) or ref in seen or not isinstance(src, str) or not src.startswith("https://www.ycombinator.com/companies/"):
            raise ValueError("unique canonical assignment reference required")
        seen.add(ref)
        url = src.rstrip("/") + "/jobs"
        if search_available:
            # Research discovery only. Neither engine snippets nor cache entries
            # establish contact authority, current buying need, or company identity.
            search_attempts += 1
            try:
                discovery = search_lookup(
                    f'"{assignment["company"]}" marketing growth vendor procurement 2026',
                    num=5,
                )
                organic = discovery.get("organic") if isinstance(discovery, Mapping) else None
                if isinstance(organic, list):
                    search_result_rows += min(5, len(organic))
            except Exception:
                pass
        job_titles, page_digest = [], None
        reason = None
        try:
            job_titles, page_digest = _roles(fetch(url), company=str(assignment["company"]))
        except Exception as exc:
            reason = type(exc).__name__
        # Public first-party hiring evidence is real but is NOT a procurement signal.
        proposal = "search_growth_command" if job_titles and "search_growth_command" in ready_products else None
        state = "YC_LISTED_COMMERCIAL_HIRING_OBSERVED" if job_titles else (
            "YC_JOBS_PAGE_OBSERVED_NO_COMMERCIAL_ROLE" if page_digest else "YC_LISTING_FETCH_UNAVAILABLE")
        row = {
            "prospect_ref": ref,
            "company": str(assignment["company"])[:120],
            "niche": str(assignment.get("niche") or "unclassified")[:80],
            "research_status": state,
            "yc_original_listing_url": url,
            "yc_listing_sha256": page_digest,
            "observed_at": now.astimezone(timezone.utc).isoformat() if page_digest else None,
            "posting_date_verified": False,
            "relevant_job_titles": job_titles,
            "candidate_product_code": proposal,
            "product_catalog_ready": bool(proposal),
            "product_fit_verified": False,
            "independent_buying_trigger_verified": False,
            "buyer_purchase_intent_verified": False,
            "qualified_for_copy": False,
            "suppression_checked": False,
            "outbound_authorized": False,
            "hold_reason": "HIRING_NOT_PROCUREMENT" if job_titles else (
                "SOURCE_UNAVAILABLE" if not page_digest else "NO_RELEVANT_COMMERCIAL_EVIDENCE"),
        }
        if reason:
            row["source_error_class"] = reason
        rows.append(row)
        if page_digest:
            observations.append({
                "source": "public_job_post",
                "url": url,
                "title": "Public company hiring page",
                "text": "Company's public role listing: " + "; ".join(job_titles),
                "observed_at": now.astimezone(timezone.utc).isoformat(),
                "niche": str(assignment.get("niche") or ""),
            })
    jev = discover_client_pains(observations, now=now)
    return {
        "schema_version": "empire.acquisition_yc_first_party_sweep.v1",
        "mode": "OBSERVE",
        "search_fabric_state": str((search_health or {}).get("last_state") or "UNKNOWN"),
        "search_fabric_not_overridden": True,
        "search_queries_attempted": search_attempts,
        "unverified_search_results_observed": search_result_rows,
        "processed": len(rows),
        "source_pages_observed": sum(bool(r["yc_listing_sha256"]) for r in rows),
        "observed_commercial_hiring": sum(bool(r["relevant_job_titles"]) for r in rows),
        "independent_buying_triggers": 0,
        "product_hypotheses": sum(bool(r["candidate_product_code"]) for r in rows),
        "copy_briefs_generated": 0,
        "qualified_for_commercial_review": 0,
        "jev_observations_submitted": jev["observations_submitted"],
        "jev_pain_review_count": jev["observations_with_pain_or_topic"],
        "jev_review_lane_counts": jev["review_lane_counts"],
        "records": rows,
        "crm_writes": False,
        "outbound_authorized": False,
        "model_training_authorized": False,
        "verified_revenue": None,
    }


def run_current_sweep(repo: Path) -> dict:
    now = datetime.now(timezone.utc)
    pool = read_only_current_snapshot(repo, now=now)
    catalog = json.loads((repo / "runtime/commercial_catalog/latest.json").read_text())
    return sweep_first_party(
        assignments=pool["next_research_batch"], catalog=catalog,
        now=now, search_health=provider_health(),
        search_lookup=search_reliable,
    )


if __name__ == "__main__":
    print(json.dumps(run_current_sweep(Path(__file__).resolve().parents[1]), indent=2))
