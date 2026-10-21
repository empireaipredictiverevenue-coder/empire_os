"""Read-only US/UK brokerage editorial evidence review.

Reuses independently authored Vane/OpenManus-inspired research profiles.
Only three previously sourced Chicago dental pages can be fetched by this
adapter; no arbitrary browsing or OpenManus tool execution is enabled.
A live page visit is NOT claim review, content licence, owner signature,
buyer intent or send authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Mapping
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit

from .research_profiles import ResearchProfile, research_with_profile

US_SOURCES = (
    ("Park Dental Specialists", "https://parkdentalspecialists.com/our-services/dental-implants"),
    ("Lincoln Park Cosmetic Dental Associates", "https://www.lincolnparkcosmeticdentists.com/implants"),
    ("Advanced Dental Care", "https://chicagogeneraldentistry.com/services/implant-dentistry/"),
)
VALID_URLS = frozenset(url for _, url in US_SOURCES)
SCHEMA = "empire.research.brokerage_us_uk_editorial_review.v1"
MAX_BYTES = 350_000


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _Headings(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.heading_level = 0
        self.suppressed = 0
        self.headings = []
        self.visible = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer"):
            self.suppressed += 1
        elif tag in ("h1", "h2") and not self.suppressed:
            self.heading_level += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer"):
            self.suppressed = max(self.suppressed - 1, 0)
        elif tag in ("h1", "h2"):
            self.heading_level = max(self.heading_level - 1, 0)

    def handle_data(self, data):
        if self.suppressed:
            return
        value = " ".join(data.split())
        if not value:
            return
        if self.heading_level and len(self.headings) < 5:
            self.headings.append(value[:180])
        if len(self.visible) < 40:
            self.visible.append(value[:110])


def inspect_known_source(url: str) -> dict:
    """Bounded GET of an exact, reviewed source URL. No redirects permitted."""
    if not isinstance(url, str) or url not in VALID_URLS:
        raise ValueError("SOURCE_NOT_IN_REVIEWED_US_EDITORIAL_ALLOWLIST")
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.username or parts.password or parts.port:
        raise ValueError("UNSAFE_REVIEWED_SOURCE_URL")
    try:
        request = Request(url, headers={"User-Agent": "EmpireOSBrokerageEditorialObserver/1.0"})
        with build_opener(_NoRedirect()).open(request, timeout=10) as response:
            if response.status != 200 or urlsplit(response.geturl()).hostname != parts.hostname:
                raise ValueError("UNEXPECTED_SOURCE_HTTP_OR_REDIRECT")
            content_type = str(response.headers.get("Content-Type", "")).lower()
            if "text/html" not in content_type:
                raise ValueError("EXPECTED_PUBLIC_HTML_SOURCE")
            body = response.read(MAX_BYTES + 1)
            if not body or len(body) > MAX_BYTES:
                raise ValueError("UNBOUNDED_SOURCE_BODY")
    except (OSError, TimeoutError, ValueError) as exc:
        return {"status": "ORIGINAL_PUBLIC_SOURCE_FETCH_HELD",
                "reason": type(exc).__name__}
    parsed = _Headings()
    parsed.feed(body.decode("utf-8", errors="replace"))
    if not parsed.headings:
        return {"status": "ORIGINAL_PUBLIC_SOURCE_HEADINGS_MISSING"}
    return {
        "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
        "content_sha256": sha256(body).hexdigest(),
        "document_headings": parsed.headings[:4],
        "visible_excerpt": " ".join(parsed.visible)[:850],
    }


def review_brokerage_editorial(
    country: str,
    *,
    inspect_fn: Callable[[str], Mapping] = inspect_known_source,
    original_sample: Path | None = None,
    observed_at: datetime | None = None,
) -> dict:
    """Evidence-only plan and review receipt. No signed editorial approval."""
    if country not in ("US", "GB"):
        raise ValueError("SUPPORTED_BROKERAGE_COUNTRY_REQUIRED")
    if observed_at is None:
        observed_at = datetime.now(timezone.utc)
    if not isinstance(observed_at, datetime) or observed_at.utcoffset() is None:
        raise ValueError("TRUSTED_REVIEW_CLOCK_REQUIRED")
    # Only the US lane has already researched source URLs. UK awaits
    # a separately verified original-source selection, never US reuse.
    question = ("Lincoln Park Chicago dental implant public offer comparison"
                if country == "US" else
                "UK dental practice expansion public market research")
    profile = ResearchProfile(
        mode="quality",
        lanes=("official", "company", "web"),
        country=country,
        sector="dental",
    )

    def curated_search(query: str, *, num: int):
        if country != "US":
            return {"organic": []}
        # Not a search API. This reproduces ONLY the original-source URLs
        # already identified by the existing Research team.
        return {"organic": [
            {"title": title, "url": url,
             "source_lane": "original_company_page",
             "discovery_engine": "CURATED_PRIOR_SOURCE_LEDGER"}
            for title, url in US_SOURCES[:num]
        ]}

    research = research_with_profile(
        question,
        profile=profile,
        search_fn=curated_search,
        inspect_fn=inspect_fn,
        synthesize_fn=None,
    )
    sources = research["evidence"]["source_observations"]
    inspected = sum(row.get("original_page_inspected") is True for row in sources)
    digest = None
    if original_sample is not None:
        path = Path(original_sample)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 30_000:
            raise ValueError("UNTRUSTED_ORIGINAL_SAMPLE_CUSTODY")
        digest = sha256(path.read_bytes()).hexdigest()
    return {
        "schema_version": SCHEMA,
        "status": ("ORIGINAL_SOURCE_PAGES_INSPECTED_EDITORIAL_PENDING"
                   if country == "US" and inspected == len(US_SOURCES)
                   else "SOURCE_DISCOVERY_AND_EDITORIAL_PENDING"),
        "market_country": country,
        "observed_at_utc": observed_at.astimezone(timezone.utc).isoformat(),
        "search_engine_live": False,
        "discovery_origin": "PREVIOUSLY_CURATED_FIRST_PARTY_SOURCE_URLS"
                            if country == "US" else "NOT_YET_RESEARCHED",
        "source_count": len(sources),
        "original_pages_inspected": inspected,
        "original_sample_sha256": digest,
        "source_observations": sources,
        "research_steps": research["steps"],
        "compute_health_is_model_quality_proof": False,
        "model_inference_performed": False,
        "factual_claims_independently_verified": False,
        "source_reuse_rights_cleared": False,
        "editorial_owner_signed_off": False,
        "customer_copy_approved": False,
        "sales_owner_approval": False,
        "buyer_interest_verified": False,
        "outbound_authorized": False,
        "payments_authorized": False,
        "database_writes": False,
        "agent_shell_or_browser_execution": False,
        "next_owner": "existing_search_and_market_intelligence",
        "next_action": (
            "CURRENT_ORIGINAL_SOURCE_CLAIM_AND_RIGHTS_QA_SIGNED_REVIEW"
            if inspected == len(US_SOURCES) and country == "US"
            else "RESEARCH_AND_INSPECT_ORIGINAL_PUBLIC_SOURCES"
        ),
    }



def triage_local_model_draft(text: str) -> dict:
    """Static QA of model suggestions; NEVER signs/approves factual claims.

    Identifies a common contradiction: ranking or booking performance inferred
    from a public service page without SERP or outcome observations.
    Lexical triggers are triage hints, not a factuality classifier.
    """
    if not isinstance(text, str) or not text.strip() or len(text) > 8000:
        return {
            "status": "HELD_NO_USABLE_MODEL_RESEARCH_DRAFT",
            "editorial_claims_verified": False,
            "customer_copy_authorized": False,
        }
    lowered = " ".join(text.casefold().split())
    unsupported_outcome = (
        any(term in lowered for term in (
            "may not be performing", "not performing well",
            "not attracting patients", "poor rankings",
            "poor search performance", "low rankings", "lack of patients",
        ))
    )
    return {
        "status": (
            "HELD_UNSUPPORTED_SEO_OR_PATIENT_OUTCOME_INFERENCE"
            if unsupported_outcome else
            "HELD_MODEL_SUGGESTIONS_REQUIRE_ORIGINAL_CLAIM_VERIFICATION"
        ),
        "model_draft_sha256": sha256(text.encode("utf8")).hexdigest(),
        "unsupported_outcome_inference_detected": unsupported_outcome,
        "lexical_triage_is_fact_verification": False,
        "independent_research_owner_review_required": True,
        "editorial_claims_verified": False,
        "customer_copy_authorized": False,
        "outbound_authorized": False,
    }
