"""Evidence-first client pain discovery for existing EmpireOS Jev + Intent Brain.

Reads bounded, already-collected public observations; no crawling, contact
enrichment, database reads/writes, outbound, or claims of verified identities.
Model-free fast lane uses the *existing* Intent Brain + Jev adjudicator.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

from empire_os.intent_brain_actor import run_intent_brain_actor
from empire_os.pain_solution_engine import SOLUTION_MAP
from empire_os.signal_intent_actor_router import observation_from_signal

SCHEMA_VERSION = "empire.jev.client_pain_discovery.v1"
MAX_OBSERVATIONS = 500
MAX_TEXT_CHARS = 8000

# Problems are evidence hypotheses until a buyer validates them. Each pattern
# requires a real difficulty/request, not just a generic marketing keyword.
# The original broad Empire pain categories remain available for theme review.
PAIN_PATTERNS: dict[str, tuple[str, tuple[str, ...]]] = {
    "inconsistent_lead_flow": ("lead_generation", (
        r"\bneed (?:more|qualified|consistent) (?:leads|customers|clients|appointments)\b",
        r"\b(?:empty|dry|unpredictable) (?:sales )?pipeline\b",
        r"\b(?:no new clients?|not getting (?:any )?(?:clients|customers)|no one is booking (?:sales )?calls)\b",
        r"\b(?:need|looking for) (?:one |another |a )?(?:more )?consistent (?:source|flow) of (?:leads|customers|clients)\b",
        r"\b(?:need|looking for) another [0-9]+(?:[-–][0-9]+)? qualified appointments\b",
        r"\b(?:enquiries|inquiries|leads|patient flow) (?:can be |are |is )?(?:unpredictable|inconsistent)\b",
        r"\b(?:haven.t|have not) (?:signed|landed|got) (?:a|any|one) (?:new )?client\b",
        r"\b(?:struggling|hard|difficult) (?:to |with )?(?:attract|getting|acquire|finding) (?:new )?(?:customers|clients|patients)\b",
        r"\bstruggl(?:e|ing) (?:to )?(?:get|generate|find) (?:leads|clients|customers)\b",
    )),
    "new_patient_schedule_gaps": ("lead_generation", (
        r"\b(?:schedule|calendar|appointment book) (?:is |was )?(?:only )?[0-9]{1,2}(?:[-–][0-9]{1,2})?% full\b",
        r"\b(?:not fully booked|schedule (?:not|isn.t) (?:full|booked))\b",
        r"\b(?:only see|seeing just) [0-9]+(?:[-–][0-9]+)? (?:new patients|nps) (?:per |a )?week\b",
    )),
    "no_initial_saas_users": ("lead_generation", (
        r"\b(?:struggling|hard|difficult) (?:to |with )?(?:get(?:ting)?|find(?:ing)?|attract(?:ing)?) (?:my |our )?first (?:users|customers|clients)\b",
        r"\b(?:no|zero|haven.t (?:got|gotten)|not getting) (?:meaningful )?(?:signups|users|installs|installations)\b",
        r"\b(?:no|zero) (?:paying )?(?:customers|users) after (?:launch|launching|months)\b",
    )),
    "saas_retention_loss": ("revenue_growth", (
        r"\b(?:churn|retention) (?:is |has been )?(?:killing us|too high|terrible|poor|a problem)\b",
        r"\b(?:customers|users|subscribers) (?:quietly )?(?:disappear|leave|churn|cancel) (?:after|within|before)\b",
        r"\b(?:struggling|failing|hard) to (?:retain|keep) (?:users|customers|subscribers)\b",
    )),
    "saas_activation_friction": ("sales_conversion", (
        r"\b(?:trial.to.paid|signup.to.paid|activation|onboarding) (?:conversion|rate|drop.?off) (?:is |are )?(?:low|poor|falling|terrible)\b",
        r"\b(?:users|customers|signups) (?:never|don.t|do not) (?:complete|finish|reach) (?:onboarding|activation|setup)\b",
    )),
    "low_quality_leads": ("lead_generation", (
        r"\b(?:junk|bad|low.quality|unqualified) leads\b",
        r"\b(?:leads|prospects) (?:are |feel )?(?:low.intent|junk|unqualified)\b",
        r"\bleads (?:are|aren.t) (?:unqualified|qualified|relevant)\b",
    )),
    "paid_acquisition_waste": ("revenue_growth", (
        r"\b(?:paid|google|search|facebook) (?:search )?ads?.{0,70}(?:poor roi|unprofitable|not profitable|not (?:consistently )?profitable|wast(?:e|ing)|too expensive)\b",
        r"\b(?:cac|cost per lead|ad spend) (?:is |are )?(?:too high|rising|unsustainable)\b",
    )),
    "organic_visibility_gap": ("search_visibility", (
        r"\b(?:not ranking|can.t rank|rankings? (?:dropped|fell)|organic traffic (?:down|dropped|falling))\b",
        r"\b(?:seo|google maps|search visibility).{0,35}(?:not working|struggling|invisible|down|poor)\b",
    )),
    "missed_inbound_calls": ("sales_conversion", (
        r"\bmiss(?:ed|ing) (?:customer |inbound |sales )?(?:calls|enquiries|inquiries)\b",
        r"\b(?:can.t|cannot) (?:answer|handle) (?:all )?(?:the |our )?(?:calls|inquiries|enquiries)\b",
    )),
    "slow_sales_follow_up": ("sales_conversion", (
        r"\b(?:slow|manual|late|delayed) follow[- ]?up\b",
        r"\b(?:leads|prospects) (?:are |keep )?(?:going cold|ghosting|not getting (?:called|followed up))\b",
        r"\b(?:follow[- ]?up|response time) (?:is |takes )?(?:too long|hours|days)\b",
    )),
    "poor_sales_conversion": ("sales_conversion", (
        r"\b(?:leads|appointments|enquiries) (?:are |aren.t |not )?(?:not converting|converting poorly|not closing)\b",
        r"\b(?:low|poor|falling) (?:close|conversion) rate\b",
    )),
    "manual_operations_overload": ("automation_ops", (
        r"\b(?:manual|repetitive|tedious) (?:data entry|process(?:es)?|admin|work|tasks|busywork)\b",
        r"\b(?:wasting|spending) (?:too much )?(?:time|hours) (?:on|copying|entering)\b",
    )),
    "disconnected_crm_workflows": ("automation_ops", (
        r"\b(?:crm|systems|tools) (?:do not|don.t|won.t) (?:sync|integrate|talk)\b",
        r"\b(?:scattered|fragmented|disconnected) (?:data|systems|workflows|tools)\b",
    )),
    "poor_contact_or_market_data": ("data_intelligence", (
        r"\b(?:outdated|inaccurate|duplicate|missing) (?:contact|lead|customer|prospect|market) data\b",
        r"\b(?:can.t|cannot) (?:find|identify) (?:the )?(?:decision makers?|right buyers?)\b",
    )),
    "unpredictable_marketing_return": ("revenue_growth", (
        r"\b(?:marketing|ads|ad spend).{0,65}(?:all (?:my|our) profit|uncertain|no return|no roi)\b",
        r"\b(?:cost per (?:patient|acquisition)|customer acquisition cost).{0,30}(?:too high|unpredictable|unsustainable)\b",
    )),
    "forecast_unreliability": ("revenue_growth", (
        r"\b(?:cannot|can.t|struggling to) forecast (?:sales|revenue|pipeline)\b",
        r"\b(?:revenue|pipeline) (?:is |has become )?(?:unpredictable|unreliable)\b",
    )),
    "capacity_or_coverage_gap": ("lead_generation", (
        r"\b(?:cannot|can.t|unable to) (?:handle|service|cover) (?:all |more |the )?(?:leads|demand|calls|jobs|areas)\b",
        r"\b(?:need|looking for) (?:more )?(?:capacity|coverage|qualified contractors|delivery partners)\b",
    )),
    "storm_response_demand": ("storm_demand", (
        r"\b(?:need|looking for|struggling with).{0,35}(?:hail|storm) (?:leads|jobs|claims|customers)\b",
        r"\b(?:storm|hail) (?:leads|claims).{0,20}(?:not converting|too expensive|poor quality)\b",
    )),
}
_COMPILED = {
    key: (theme, tuple(re.compile(p, re.I) for p in patterns))
    for key, (theme, patterns) in PAIN_PATTERNS.items()
}
ALLOWED_SOURCES = frozenset({
    "reddit", "linkedin", "quora", "company_site", "public_rfp",
    "public_review", "public_job_post", "public_forum", "first_party_intake",
})
SOCIAL_DOMAINS = {
    "reddit": ("reddit.com",),
    "linkedin": ("linkedin.com",),
    "quora": ("quora.com",),
}
EXCLUDED_ORIENTATIONS = {"employment_hiring", "seller_content", "third_party_referral"}
# Explicitly respect author requests and do not put them into a contact queue.
NO_SOLICITATION = re.compile(
    r"\b(?:no soliciting|do not (?:dm|message|contact)|don't (?:dm|message|contact)|"
    r"no dms|not looking for (?:a |any )?(?:service|provider|agency|solution)|"
    r"not looking for the solution)\b", re.I,
)
REVIEWABLE = {"RESOLVE_IDENTITY", "NEEDS_REVIEW"}


def _canonical_url(url: Any) -> str:
    if not isinstance(url, str) or len(url) > 2000:
        return ""
    try:
        p = urlsplit(url.strip())
    except ValueError:
        return ""
    if p.scheme.lower() not in {"https", "http"} or not p.hostname or p.username or p.password:
        return ""
    host = p.hostname.casefold().removeprefix("www.")
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        return ""
    # Deliberately retain substantive query IDs (e.g. RFP/ticket IDs).
    return urlunsplit((p.scheme.lower(), host, p.path.rstrip("/") or "/", p.query, ""))


def _safe_source(row: Mapping[str, Any], source_url: str) -> bool:
    source = row.get("source")
    if source not in ALLOWED_SOURCES:
        return False
    host = urlsplit(source_url).hostname or ""
    expected = SOCIAL_DOMAINS.get(source)
    return not expected or any(host == x or host.endswith("." + x) for x in expected)


def _freshness(row: Mapping[str, Any], now: datetime) -> tuple[str, bool]:
    stamp = row.get("observed_at")
    if not isinstance(stamp, str) or not stamp:
        return "unknown", False
    try:
        dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age = (now - dt.astimezone(timezone.utc)).total_seconds() / 86400
    except ValueError:
        return "unknown", False
    if age < 0:
        return "future_rejected", False
    if age <= 7:
        return "fresh", True
    if age <= 30:
        return "recent", True
    if age <= 90:
        return "aging", False
    return "stale", False


def discover_client_pains(
    observations: Iterable[Mapping[str, Any]], *,
    now: datetime | None = None,
    include_private_source_links: bool = False,
) -> dict[str, Any]:
    """Return a non-executable per-source review queue and evidence aggregates.

    Private links are only suitable for a gitignored, access-restricted founder
    review receipt. The default result is safe to place in a reviewed aggregate.
    """
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rows = list(observations)
    if len(rows) > MAX_OBSERVATIONS:
        raise ValueError("bounded observation batch required")
    items: list[dict[str, Any]] = []
    counters = Counter()
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            counters["invalid"] += 1
            continue
        url = _canonical_url(row.get("url"))
        if not url or not _safe_source(row, url):
            counters["invalid_or_untrusted_source"] += 1
            continue
        # Same source cannot inflate the number of pain-signal opportunities.
        ref = sha256(url.encode("utf-8")).hexdigest()
        if ref in seen:
            counters["duplicate_source"] += 1
            continue
        seen.add(ref)
        text = " ".join(str(row.get(k) or "") for k in ("title", "text"))
        if not text.strip() or len(text) > MAX_TEXT_CHARS:
            counters["empty_or_oversized"] += 1
            continue
        freshness, current_evidence = _freshness(row, current)
        # Ignore all external/row-injected identity, repeated-signal and buyer
        # proofs. They require a separate authenticated canonical owner.
        actor_input = {
            "source": row["source"], "url": url, "title": str(row.get("title") or ""),
            "text": str(row.get("text") or ""), "observed_at": row.get("observed_at"),
            "niche": str(row.get("niche") or ""),
            "first_party_verified": False, "canonical_identity_verified": False,
            "repeated_signal_count": 1,
            "evidence_urls": (),
        }
        envelope = run_intent_brain_actor(actor_input)
        state = envelope["output"]["intent_brain"]
        jev = envelope["output"]["jev"]
        if (envelope["governance"]["execution_authority"] != "none"
            or jev["execution_authority"] != "none"
            or jev["first_party_identity_verified"] is not False):
            raise ValueError("canonical authority violation")
        orientation = state["signal_orientation"]
        excluded = orientation in EXCLUDED_ORIENTATIONS or state["actor_type"] in {"job_seeker", "vendor"}
        concrete = [key for key, (_, patterns) in _COMPILED.items() if any(
            pattern.search(text) for pattern in patterns
        )]
        themes = set(state["pain_points"])
        for pain in row.get("pain_points") or ():
            if pain in SOLUTION_MAP:
                themes.add(pain)
        if not concrete and not themes:
            counters["no_problem_evidence"] += 1
            continue
        contact_opt_out = bool(NO_SOLICITATION.search(text))
        # A mention in informational content is research, not a client pain.
        lane = ("NO_SOLICITATION" if contact_opt_out else
                "EXCLUDE_NONBUYER" if excluded else
                "REVIEW_IDENTITY" if current_evidence and concrete and jev["recommendation"] in REVIEWABLE else
                "REVIEW_PAIN_HYPOTHESIS" if current_evidence and concrete
                    and state["actor_type"] in {"owner_operator", "decision_maker"}
                    and orientation == "neutral" else
                "MONITOR_UNVERIFIED")
        if lane == "EXCLUDE_NONBUYER":
            counters["excluded_nonbuyer"] += 1
        if not current_evidence:
            counters["stale_or_undated"] += 1
        confidence = int(round(100 * float(state["confidence"]["intent"])))
        priority = (
            min(75, 15 + min(35, confidence // 3) +
                (15 if orientation == "buyer_procurement" else 0) +
                (10 if state["actor_type"] in {"owner_operator", "decision_maker"} else 0) +
                (5 if state["urgency"] == "high" else 0))
            if lane == "REVIEW_IDENTITY" else
            min(40, 15 + min(20, confidence // 4)) if lane == "REVIEW_PAIN_HYPOTHESIS" else 0
        )
        detected_themes = set(themes)
        detected_themes.update(_COMPILED[key][0] for key in concrete)
        matching_offers = sorted({
            str(SOLUTION_MAP[theme]["offer_key"])
            for theme in detected_themes if theme in SOLUTION_MAP
        })
        item: dict[str, Any] = {
            "source_sha256": ref,
            "source": row["source"],
            "niche": state["niche"],
            "freshness": freshness,
            "pain_hypotheses": concrete,
            "broad_topic_mentions": sorted(themes),
            "matched_offers_to_validate": matching_offers,
            "orientation": orientation,
            "actor_claim": state["actor_type"],
            "buying_stage": state["buying_stage"],
            "urgency": state["urgency"],
            "jev_recommendation": jev["recommendation"],
            "evidence_priority": priority,
            "review_lane": lane,
            "next_owner": ("existing_research_and_buyer_scout" if lane == "REVIEW_IDENTITY"
                           else "source_intelligence_research"),
            "unverified_identity": True,
            "unverified_commercial_need": True,
            "outreach_authorized": False,
            "no_solicitation": contact_opt_out,
        }
        if include_private_source_links:
            item["private_evidence_url"] = url
        items.append(item)
    items.sort(key=lambda x: (-x["evidence_priority"], x["source_sha256"]))
    by_pain: dict[str, dict[str, Any]] = {}
    for pain in PAIN_PATTERNS:
        matching = [x for x in items if pain in x["pain_hypotheses"]]
        if matching:
            by_pain[pain] = {
                "observations": len(matching),
                "review_identity": sum(x["review_lane"] == "REVIEW_IDENTITY" for x in matching),
                "themes": PAIN_PATTERNS[pain][0],
                "matched_offer_to_validate": SOLUTION_MAP[PAIN_PATTERNS[pain][0]]["offer_key"],
            }
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "OBSERVE",
        "status": "CLIENT_PAIN_DISCOVERY_OWNER_REVIEW_ONLY",
        "observations_submitted": len(rows),
        "observations_with_pain_or_topic": len(items),
        "source_counts": dict(sorted(Counter(x["source"] for x in items).items())),
        "review_lane_counts": dict(sorted(Counter(x["review_lane"] for x in items).items())),
        "pain_counts": by_pain,
        "quality_counters": dict(sorted(counters.items())),
        "items": items,
        "prospects_verified": 0,
        "buyer_purchase_intent_verified": False,
        "source_rights_and_consent_verified": False,
        "crm_writes": False,
        "outbound_sent": 0,
        "execution_authority": "none",
    }



def observations_from_existing_canonical_inbox(
    signal_inbox: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Reuse the canonical signal adapter. Social intent only, never permits/courts.

    Does not copy trusted identity claims or authority from the raw event.
    """
    if not isinstance(signal_inbox, Mapping) or len(signal_inbox) > 25000:
        raise ValueError("bounded canonical signal inbox required")
    result = []
    for source_id, signal in signal_inbox.items():
        if not isinstance(source_id, str) or not isinstance(signal, Mapping):
            continue
        source = signal.get("source")
        if source not in {"reddit_intent", "linkedin_intent"}:
            continue
        if (signal.get("status") not in {"unresolved", "needs_review"}
            or signal.get("execution_authority") != "none"
            or signal.get("entity_id") is not None
            or signal.get("prospect_id") is not None):
            continue
        row = observation_from_signal(source_id, signal)
        if not isinstance(row, Mapping):
            continue
        result.append({
            "source": source.removesuffix("_intent"),
            "url": row.get("url"),
            "title": row.get("title"),
            "text": row.get("text"),
            "observed_at": row.get("observed_at"),
            "niche": row.get("niche"),
            # Deliberately drop source-provided identity/consent/prospect flags.
        })
    if len(result) > MAX_OBSERVATIONS:
        raise ValueError("too many canonical social observations")
    return result
