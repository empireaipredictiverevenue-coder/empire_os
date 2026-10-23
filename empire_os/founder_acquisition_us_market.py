"""Original-source USA account opportunity evidence, not buyer qualification.

One extension of EmpireOS Founder Acquisition. Four existing prospect customers,
20 curated US company-event hypotheses, 17 distinct source URLs. On each native
Buyer Acquisition Team cycle, recheck at most two ORIGINAL URLs, deduplicated
across product-fit hypotheses. Never create leads, contact people or send mail.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from html import unescape
from pathlib import Path
import re
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from empire_os.workspace_solar_reply_tracking import EvidenceHeld

SCHEMA = "empire.founder_acquisition_us_evidence.v1"
INPUT = Path("research_reviews/data/FOUNDER_US_MULTIVERTICAL_EVIDENCE_SEEDS_20261023.csv")
MAX_BYTES = 400_000
ALLOWED_HOSTS = frozenset({
    "investors.tutorperini.com", "www.prnewswire.com", "www.jacobs.com",
    "investors.cardinalinfrastructuregroup.com", "www.pcl.com",
    "matrixrenewables.com", "www.mortenson.com", "www.umpartners.com",
    "mn-dermatology-partners.com", "hughston.com", "borlandgroover.com",
})
ALLOWED_CLIENTS = frozenset({"Alloovium", "Libra Robotics", "Andco", "Plena Health"})
SOURCE_ROLES = frozenset({"COMPANY_WEBSITE", "COMPANY_DISTRIBUTED_WIRE", "PDF_PRIMARY_REPORT"})

# Exact, reviewed provenance correction: original April 9 PDF remains in
# historic evidence as HELD; same publisher's HTML release is independently
# readable and matches the real Cardinal data-center event.
REVIEWED_SOURCE_REPLACEMENTS = {
    "https://investors.cardinalinfrastructuregroup.com/node/6631/pdf":
    "https://investors.cardinalinfrastructuregroup.com/news-releases/news-release-details/cardinal-infrastructure-group-awarded-contract-large-scale-data",
}


def safe_original_url(url: Any) -> bool:
    if not isinstance(url, str) or not 22 <= len(url) <= 450:
        return False
    try:
        u = urlsplit(url)
    except (TypeError, ValueError):
        return False
    return (
        u.scheme == "https" and u.hostname in ALLOWED_HOSTS
        and u.netloc == u.hostname and not (u.username or u.password)
        and not u.query and not u.fragment and u.path.startswith("/")
        and u.path != "/" and chr(92) not in u.path
    )


def load_us_inputs(root: Path) -> list[dict[str, str]]:
    path = Path(root).resolve() / INPUT
    if (path.is_symlink() or not path.is_file() or path.stat().st_size > 80_000):
        raise EvidenceHeld("US_RESEARCH_SEED_MISSING_OR_UNSAFE")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not 4 <= len(rows) <= 100:
        raise EvidenceHeld("US_RESEARCH_SEED_ROW_BUDGET")
    seen = set()
    required = (
        "country", "startup", "account", "market", "event_date", "date_precision",
        "source_url", "source_role", "anchor_a", "anchor_b", "hypothesis", "gap",
    )
    for r in rows:
        if any(not r.get(k) or len(r[k]) > (450 if k == "source_url" else 450) for k in required):
            raise EvidenceHeld("US_SEED_INCOMPLETE")
        if r["country"] != "US" or r["startup"] not in ALLOWED_CLIENTS:
            raise EvidenceHeld("US_SEGMENT_SCOPE_MISMATCH")
        if (not safe_original_url(r["source_url"])
                or r["source_role"] not in SOURCE_ROLES):
            raise EvidenceHeld("US_RESEARCH_SOURCE_UNTRUSTED")
        url = r["source_url"]
        if r["source_role"] == "COMPANY_DISTRIBUTED_WIRE" and urlsplit(url).hostname != "www.prnewswire.com":
            raise EvidenceHeld("US_WIRE_PROVENANCE_MISMATCH")
        if r["source_role"] == "PDF_PRIMARY_REPORT" and not url.endswith("/pdf"):
            raise EvidenceHeld("US_PDF_SOURCE_UNEXPECTED")
        if r["date_precision"] not in {"DAY", "MONTH", "OBSERVATION_ONLY"}:
            raise EvidenceHeld("US_RESEARCH_DATE_PRECISION_INVALID")
        if r["date_precision"] == "MONTH" and not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])",r["event_date"]):
            raise EvidenceHeld("US_RESEARCH_EVENT_MONTH_INVALID")
        if r["date_precision"] != "MONTH" and not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])-[0-3]\d",r["event_date"]):
            raise EvidenceHeld("US_RESEARCH_EVENT_DAY_INVALID")
        try:
            date.fromisoformat(r["event_date"] + "-01" if r["date_precision"] == "MONTH" else r["event_date"])
        except ValueError:
            raise EvidenceHeld("US_RESEARCH_DATE_INVALID") from None
        if (not all(2 <= len(r[f]) <= 80 and re.fullmatch(r"[a-zA-Z0-9 .&/-]+", r[f]) for f in ("anchor_a","anchor_b"))):
            raise EvidenceHeld("US_RESEARCH_ANCHORS_INVALID")
        key = (r["startup"].casefold(),r["account"].casefold(),url)
        if key in seen:raise EvidenceHeld("US_RESEARCH_DUPLICATE_ASSOCIATION")
        seen.add(key)
    return rows


def fetch_source(url: str) -> Mapping[str, Any]:
    if not safe_original_url(url):
        raise EvidenceHeld("UNTRUSTED_US_SOURCE_URL")
    import requests
    try:
        response = requests.get(
            url, timeout=(2, 5), stream=True, allow_redirects=False,
            headers={"User-Agent": "EmpireAI-OriginalSourceResearch/1.0",
                     "Accept": "text/html,application/pdf"},
        )
        try:
            raw = response.raw.read(MAX_BYTES + 1, decode_content=True)
        finally:
            response.close()
        return {
            "status_code": response.status_code,
            "final_url": response.url,
            "content_type": str(response.headers.get("Content-Type") or "").split(";")[0].strip().lower(),
            "body": raw,
        }
    except (requests.RequestException, OSError, ValueError):
        raise EvidenceHeld("US_PUBLIC_SOURCE_UNAVAILABLE") from None


def assess_source(url: str, anchors: list[tuple[str, str]], *, response: Mapping[str, Any],
                  now: datetime, source_role: str) -> dict[str, Any]:
    if not safe_original_url(url) or len(anchors) < 1 or source_role not in SOURCE_ROLES:
        raise EvidenceHeld("US_SOURCE_IDENTITY_INVALID")
    body = response.get("body")
    expected_type = "application/pdf" if source_role == "PDF_PRIMARY_REPORT" else "text/html"
    if (response.get("status_code") != 200 or response.get("final_url") != url
            or response.get("content_type") != expected_type
            or not isinstance(body, bytes) or not 120 <= len(body) <= MAX_BYTES):
        raise EvidenceHeld("US_ORIGINAL_SOURCE_HTTP_HELD")
    if source_role != "PDF_PRIMARY_REPORT":
        content = unescape(body.decode("utf-8",errors="replace"))
        content = re.sub(r"<[^>]*>", " ", content).casefold()
        # The original company/project publisher must corroborate BOTH event
        # anchors for each product-fit association sharing this URL.
        for a,b in anchors:
            if not (re.search(r"(?<![a-z0-9])"+re.escape(a.casefold())+r"(?![a-z0-9])", content)
                    and re.search(r"(?<![a-z0-9])"+re.escape(b.casefold())+r"(?![a-z0-9])", content)):
                raise EvidenceHeld("US_CLAIM_ANCHORS_NOT_CORROBORATED")
    else:
        # PDF byte presence alone is NOT substantive corroboration; hold until
        # the existing PDF original-document verifier can authenticate it.
        raise EvidenceHeld("US_PDF_CONTENT_REQUIRES_OWNER_VERIFICATION")
    return {
        "source_url": url, "source_role": source_role,
        "source_sha256": sha256(body).hexdigest(),
        "observed_at_utc": now.astimezone(timezone.utc).isoformat(),
        "source_status": "PUBLISHED_EVENT_CLAIM_OBSERVED_NOT_BUYER_VERIFIED",
        "actual_customer_demand": False, "outbound_authorized": False,
    }


def refresh_us_evidence(rows: list[Mapping[str,str]], *,
                        previous: Mapping[str,Any] | None, now: datetime,
                        fetch: Callable[[str], Mapping[str, Any]] = fetch_source,
                        max_fetch: int = 2) -> dict[str,Any]:
    if (now.tzinfo is None or now.utcoffset() is None
            or type(max_fetch) is not int or not 1 <= max_fetch <= 2):
        raise EvidenceHeld("US_TRUSTED_CLOCK_OR_BUDGET_MISSING")
    at = now.astimezone(timezone.utc)
    urls: dict[str,dict[str,Any]] = {}
    for r in rows:
        url=r["source_url"]
        if url not in urls:
            urls[url]={"source_url":url,"source_role":r["source_role"],"anchors":[]}
        if urls[url]["source_role"] != r["source_role"]:
            raise EvidenceHeld("US_DUPLICATE_SOURCE_ROLE_CONFLICT")
        urls[url]["anchors"].append((r["anchor_a"],r["anchor_b"]))
    if not 2 <= len(urls) <= 100:
        raise EvidenceHeld("US_UNIQUE_SOURCE_COUNT_INVALID")
    prior={}
    retired_history: list[dict[str, str]] = []
    if previous is not None:
        if (previous.get("schema_version") != SCHEMA
                or previous.get("status") != "US_PUBLIC_EVENT_EVIDENCE_REVIEW_ONLY"):
            raise EvidenceHeld("US_PREVIOUS_SNAPSHOT_UNTRUSTED")
        for item in previous.get("sources",[]):
            if not isinstance(item,dict) or item.get("source_url") in prior:
                raise EvidenceHeld("US_DUPLICATE_PREVIOUS_SOURCE")
            prior[item["source_url"]]=item
        existing_history = previous.get("retired_held_source_history", [])
        if not isinstance(existing_history, list) or len(existing_history) > 4:
            raise EvidenceHeld("US_PREVIOUS_SOURCE_HISTORY_INVALID")
        for item in existing_history:
            if (not isinstance(item, dict)
                    or item.get("retired_url") not in REVIEWED_SOURCE_REPLACEMENTS
                    or item.get("replacement_url") != REVIEWED_SOURCE_REPLACEMENTS[item["retired_url"]]
                    or item.get("prior_source_status") != "HELD_SOURCE_NOT_CORROBORATED"
                    or item.get("reason") != "OWNER_HTML_SOURCE_REPLACES_HELD_PDF"):
                raise EvidenceHeld("US_UNAUTHORISED_SOURCE_HISTORY")
            retired_history.append(dict(item))
        removed=set(prior)-set(urls)
        for legacy_url in removed:
            if (REVIEWED_SOURCE_REPLACEMENTS.get(legacy_url) not in urls
                    or prior[legacy_url].get("source_status") != "HELD_SOURCE_NOT_CORROBORATED"
                    or any(x["retired_url"] == legacy_url for x in retired_history)):
                raise EvidenceHeld("US_PREVIOUS_EVENT_REMOVED")
            retired_history.append({
                "retired_url": legacy_url,
                "replacement_url": REVIEWED_SOURCE_REPLACEMENTS[legacy_url],
                "prior_source_status": "HELD_SOURCE_NOT_CORROBORATED",
                "prior_observed_at_utc": prior[legacy_url].get("observed_at_utc"),
                "reason": "OWNER_HTML_SOURCE_REPLACES_HELD_PDF",
            })
            del prior[legacy_url]
    updated=[]
    calls=0
    for url,info in urls.items():
        before=prior.get(url)
        eligible=True
        if before:
            try:
                observed=datetime.fromisoformat(before["observed_at_utc"])
                if observed.tzinfo is None or observed > at:
                    raise ValueError("future_timestamp")
                ttl=timedelta(days=7 if before["source_status"].startswith("PUBLISHED_EVENT") else 1)
                eligible=at-observed >= ttl
            except (KeyError,TypeError,ValueError):
                raise EvidenceHeld("US_INVALID_PRIOR_SOURCE_TIME") from None
        if eligible and calls < max_fetch:
            calls+=1
            try:
                item=assess_source(url,info["anchors"],response=fetch(url),
                                   now=at,source_role=info["source_role"])
            except Exception:
                item={
                    "source_url":url,"source_role":info["source_role"],
                    "source_status":"HELD_SOURCE_NOT_CORROBORATED",
                    "observed_at_utc":at.isoformat(),
                    "actual_customer_demand":False,"outbound_authorized":False,
                }
            updated.append(item)
        elif before:
            updated.append(before)
    verified={item["source_url"] for item in updated if item["source_status"].startswith("PUBLISHED_EVENT")}
    by_client={}
    for client in ALLOWED_CLIENTS:
        tagged=[r for r in rows if r["startup"]==client]
        by_client[client]={
            "market":"US", "curated_account_hypotheses":len(tagged),
            "source_observed_hypotheses":sum(r["source_url"] in verified for r in tagged),
            "verified_buyers":0, "outbound_authorized":False,
        }
    return {
        "schema_version":SCHEMA,"status":"US_PUBLIC_EVENT_EVIDENCE_REVIEW_ONLY",
        "market":"US", "observed_at_utc":at.isoformat(),
        "distinct_original_source_count":len(urls),
        "distinct_observed_source_count":len(verified),
        "curated_opportunity_hypotheses":len(rows),
        "observed_account_hypotheses":sum(r["source_url"] in verified for r in rows),
        "http_checks_this_cycle":calls,
        "sources_awaiting_review":len(urls)-len(updated),
        "sources":updated,
        "retired_held_source_history": retired_history,
        "founder_customer_segments":by_client,
        "actual_buyers_verified":0,"revenue_verified":False,
        "crm_writes":False,"outbound_sent":False,
        "automatic_send_authorized":False,"approved_price":False,
        "execution_authority":"none",
    }
