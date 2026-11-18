"""Original Data Brokerage named-buyer scouting from current first-party web pages.

Reuses Search Fabric site_probe, Buyer Discovery personhood, existing buyer
contact-history guard, and the original SEC Search Fabric evidence owner.
Research-only; no email guessing, CRM promotion, form submissions or outreach.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from typing import Any, Callable, Mapping
import json
import re

from empire_os.buyer_discovery import looks_like_person_name
from empire_os.search_fabric.site_probe import probe_site
from empire_os.buyer_network_contact_history_gate import load_context, review
from empire_os.search_fabric.sec_formd_source_quality_v1 import atomic_private, digest

SCHEMA = "empire.data_brokerage.named_buyer_research.v1"
STATE = "named_buyer_contact_research_latest.json"
REFRESH_GAP = timedelta(hours=12)
# Product-specific seed ORGS only: names/roles must be discovered fresh from
# their first-party sites. Extend this original-owner scope from qualified
# research organisations, not from arbitrary search results.
TARGET_ORGS = (
    ("Neudata", "neudata.co", "https://www.neudata.co/about", "DATA_PROVIDER_DISCOVERY"),
    ("Capital & Liquidity", "capitalandliquidity.com", "https://capitalandliquidity.com/about", "PRIVATE_MARKET_RESEARCH"),
    ("Quanted", "quanted.com", "https://www.quanted.com/", "DATA_VENDOR_PARTNER"),
    ("Final", "final.co.il", "https://www.final.co.il/about/", "BUY_SIDE_DATA_TEAM"),
)
# First-party data-vendor programmes recovered from current vendor pages.
# Each candidate must be re-probed and verified; a seed is NOT a buyer, a
# verified employee, or contact authority. Extra accounts rotate under the
# existing owner's 12-hour refresh rather than adding a second scheduler.
PROGRAM_SOURCES = (
    ("Eagle Alpha", "eaglealpha.com",
     "https://www.eaglealpha.com/about-eagle-alpha/", "DATA_VENDOR_PARTNER",
     "https://www.eaglealpha.com/solutions/data-vendors/"),
    ("BattleFin", "battlefin.com",
     "https://www.battlefin.com/about", "DATA_VENDOR_PARTNER",
     "https://www.battlefin.com/alternative-data-academy/msci-battlefin-the-alternative-data-provider-showcase-competition-is-open"),
    ("S&P Global Marketplace", "marketplace.spglobal.com",
     "https://www.marketplace.spglobal.com/en/data-vendor", "DATA_VENDOR_PARTNER",
     "https://www.marketplace.spglobal.com/en/data-vendor"),
    ("AlternativeData.org", "alternativedata.org",
     "https://alternativedata.org/about/", "DATA_VENDOR_PARTNER",
     "https://alternativedata.org/submit-provider/"),
)
# Match the original Agent Reach first-party search index's explicit intent
# vocabulary. General long-tail queries skipped genuine "data buyer" records
# while the public provider circuit was open.
COMPANY_SEARCH_QUERIES = (
    "data buyer",
    "data leads buyer",
    "data buyer publisher",
)
NON_PERSON_TOKENS = frozenset((
    "advisory", "board", "business", "development", "corporate", "solutions",
    "provider", "data", "expert", "exchange", "services", "management",
    "opportunity", "qualified", "marketing", "research", "team", "group",
    "product", "leadership", "conference", "organisation", "organization",
))


def _host(url: str) -> str:
    try:
        p = urlsplit(url)
        if p.scheme != "https" or not p.hostname or p.username or p.password or p.port not in (None, 443):
            return ""
        return p.hostname.casefold().removeprefix("www.").rstrip(".")
    except (ValueError, TypeError):
        return ""


def _real_name(name: Any) -> bool:
    if not looks_like_person_name(name):
        return False
    terms = set(re.findall(r"[^\W\d_]+", str(name).casefold(), flags=re.UNICODE))
    return not bool(terms & NON_PERSON_TOKENS)


def _role_fit(title: str, lane: str) -> tuple[int, str]:
    text = " ".join(str(title or "").casefold().split())
    if "data provider" in text or "vendor engagement" in text:
        return 98, "DATA_VENDOR_ONBOARDING"
    if "partnership" in text and lane != "BUY_SIDE_DATA_TEAM":
        return 94, "DATA_PARTNERSHIP_CONTACT"
    if "data strategy" in text or "head of data" in text or "data sourcing" in text:
        return 93, "BUY_SIDE_DATA_SOURCING"
    if "vendor management" in text or "market data" in text:
        return 90, "DATA_PROCUREMENT_OR_RESEARCH"
    if "head of research" in text:
        return 88, "DATA_RESEARCH_GATEKEEPER"
    if "corporate data" in text or "research analyst" in text:
        return 80, "DATA_RESEARCH_SPECIALIST"
    if "corporate solutions" in text:
        return 76, "CORPORATE_INTELLIGENCE_OWNER"
    if lane == "PRIVATE_MARKET_RESEARCH" and ("founder" in text or "editor" in text):
        return 75, "EDITORIAL_OR_PARTNERSHIP_OWNER"
    if ("founder" in text or "chief executive" in text
            or re.search(r"\bceo\b", text)):
        return 57, "FOUNDER_RESEARCH_FALLBACK"
    if "commercial director" in text or "chief revenue officer" in text:
        return 53, "COMMERCIAL_ROLE_UNQUALIFIED_FOR_DATA"
    return 0, "ROLE_NOT_RELEVANT_TO_THIS_PRODUCT"


def inspect_named_buyer_accounts(
    *, now: datetime, context: Mapping[str, Any],
    probe_fn: Callable[..., Mapping[str, Any]] = probe_site,
    targets: tuple[tuple[str, ...], ...] = TARGET_ORGS,
) -> dict[str, Any]:
    if now.utcoffset() is None or not isinstance(context, Mapping) or context.get("available") is not True:
        raise ValueError("existing_contact_owner_unavailable")
    if not context.get("workspace_source_available"):
        raise ValueError("workspace_sent_history_not_loaded_fail_closed")
    if len(targets) > 9 or any(len(t) not in (4, 5) for t in targets):
        raise ValueError("unbounded_buyer_account_scope")
    contacts, accounts, failures = [], [], []
    for target in targets:
        company, domain, page, lane = target[:4]
        program_url = target[4] if len(target) == 5 else None
        if not re.fullmatch(r"[a-z0-9.-]{4,130}", domain) or _host(page) != domain:
            raise ValueError("invalid_first_party_buyer_research_site")
        history = review(domain, context)
        account = {
            "company": company, "domain": domain, "product_buyer_lane": lane,
            "contact_history_state": history["state"],
            "contact_history_next_action": history["next_action"],
            "prior_outbound_observed": bool(history.get("last_outbound_at")),
            "prior_inbound_observed": bool(history.get("last_inbound_at")),
            "first_party_people_source": page, "first_party_probe_ok": False,
            "company_program_source": program_url,
            "company_program_source_verified": False,
            "company_research_discovery_state": (
                "PROGRAM_CANDIDATE_UNVERIFIED" if program_url
                else "ORIGINAL_BROKERAGE_ACCOUNT_RECHECK"
            ),
            "named_people_found": 0, "direct_email_confirmed": 0,
            "official_company_contact_page": None,
            "official_company_contact_email": None,
            "company_mailbox_is_not_person_verification": True,
            "company_mailbox_delivery_verified": False,
            "commercial_purchase_request_verified": False,
            "outbound_authorized": False,
        }
        try:
            source = probe_fn(page, max_pages=2, request_timeout=3.0,
                              time_budget_seconds=7.0, page_priority="people",
                              public_only=True)
        except (OSError, TimeoutError, ValueError, TypeError) as exc:
            source = {}
            failures.append({"domain": domain, "error_class": type(exc).__name__})
        if (not isinstance(source, Mapping)
                or source.get("ok") is not True
                or _host(str(source.get("final_url") or page)) != domain):
            failures.append({"domain": domain, "error_class": "FIRST_PARTY_PROBE_UNVERIFIED"})
            accounts.append(account)
            continue
        account["first_party_probe_ok"] = True
        # Every newly discovered candidate must prove it controls the actual
        # first-party vendor programme page. Public search title/snippet is
        # insufficient to promote the company as a verified dataset channel.
        if program_url is not None:
            if _host(program_url) != domain:
                raise ValueError("candidate_vendor_program_domain_mismatch")
            if program_url == page:
                programme = source
            else:
                try:
                    programme = probe_fn(
                        program_url, max_pages=1, request_timeout=3.0,
                        time_budget_seconds=5.0, page_priority="people",
                        public_only=True,
                    )
                except (OSError, TimeoutError, ValueError, TypeError):
                    programme = {}
            verified_programme = (
                isinstance(programme, Mapping)
                and programme.get("ok") is True
                and _host(str(programme.get("final_url") or program_url)) == domain
                and bool(
                    re.search(
                        r"data[\s-]*(?:vendors?|providers?|partners?|sellers?|marketplace)"
                        r"|alternative[\s-]*data|datasets?"
                        r"|sell(?:ing)?[\s-]+data|vendor[\s-]+solutions?",
                        " ".join((
                            str(programme.get("title") or "")[:200],
                            str(programme.get("description") or "")[:500],
                        )),
                        flags=re.IGNORECASE,
                    )
                )
            )
            account["company_program_source_verified"] = bool(verified_programme)
            account["company_research_discovery_state"] = (
                "VERIFIED_FIRST_PARTY_DATA_VENDOR_PROGRAM"
                if verified_programme else "PROGRAM_SOURCE_UNVERIFIED_HOLD"
            )
            if not verified_programme:
                accounts.append(account)
                continue
            account["verified_programme_page_title"] = str(
                programme.get("title") or ""
            )[:160]
        first_party_people = list((source.get("people") or [])[:60])
        account["about_pages_inspected"] = []
        # Programme pages establish a company's relevant data activity but
        # often list no actual staff. Use the original FIRST-PARTY probe on
        # up to two official people pages; do not substitute search snippets,
        # guest article authors, LinkedIn guesses or provider-derived names.
        has_relevant_staff = any(
            isinstance(person, Mapping)
            and _real_name(person.get("name"))
            and _role_fit(str(person.get("title") or ""), lane)[0] >= 50
            and _host(str(person.get("url") or "")) == domain
            and not urlsplit(str(person.get("url") or "")).path.startswith(
                ("/blog", "/news", "/resources", "/events", "/agenda")
            )
            for person in first_party_people
        )
        if program_url and not has_relevant_staff:
            for suffix in ("/about-us", "/about"):
                first_party_page = f"https://{domain}{suffix}"
                if first_party_page == page:
                    continue
                account["about_pages_inspected"].append(first_party_page)
                try:
                    people_probe = probe_fn(
                        first_party_page, max_pages=1, request_timeout=3.0,
                        time_budget_seconds=5.0, page_priority="people",
                        public_only=True,
                    )
                except (OSError, TimeoutError, ValueError, TypeError):
                    continue
                if (not isinstance(people_probe, Mapping)
                        or people_probe.get("ok") is not True
                        or _host(str(people_probe.get("final_url") or "")) != domain):
                    continue
                first_party_people.extend((people_probe.get("people") or [])[:30])
                if any(
                    isinstance(person, Mapping)
                    and _real_name(person.get("name"))
                    and _role_fit(str(person.get("title") or ""), lane)[0] >= 50
                    and _host(str(person.get("url") or "")) == domain
                    for person in (people_probe.get("people") or [])[:30]
                ):
                    break
        # A company-owned contact route is valuable even when the Waterfall
        # cannot verify an individual person's mailbox. Never conflate these
        # evidence levels or imply that publishing an email proves delivery.
        if program_url:
            potential_contacts = [source, programme]
            for contact_source in potential_contacts:
                if not isinstance(contact_source, Mapping):
                    continue
                if _host(str(contact_source.get("final_url") or "")) != domain:
                    continue
                for raw_email in (contact_source.get("emails") or [])[:12]:
                    if not isinstance(raw_email, str) or not re.fullmatch(
                        r"[^@\s]+@[^@\s]+\.[^@\s]+", raw_email
                    ):
                        continue
                    local, email_domain = raw_email.strip().casefold().rsplit("@", 1)
                    if (email_domain == domain and local in {
                        "info", "hello", "contact", "partners", "partnerships",
                        "vendors", "sales", "data",
                    }):
                        account["official_company_contact_email"] = raw_email.strip().casefold()
                        account["official_company_contact_page"] = str(
                            contact_source.get("final_url")
                        )
                        break
                if account["official_company_contact_email"]:
                    break
            if account["official_company_contact_email"] is None:
                contact_page = f"https://{domain}/contact"
                try:
                    contact_probe = probe_fn(
                        contact_page, max_pages=1, request_timeout=3.0,
                        time_budget_seconds=5.0, page_priority="people",
                        public_only=True,
                    )
                except (OSError, TimeoutError, ValueError, TypeError):
                    contact_probe = {}
                if (isinstance(contact_probe, Mapping)
                        and contact_probe.get("ok") is True
                        and _host(str(contact_probe.get("final_url") or "")) == domain):
                    account["official_company_contact_page"] = str(
                        contact_probe["final_url"]
                    )
                    for raw_email in (contact_probe.get("emails") or [])[:12]:
                        if not isinstance(raw_email, str) or not re.fullmatch(
                            r"[^@\s]+@[^@\s]+\.[^@\s]+", raw_email
                        ):
                            continue
                        local, email_domain = raw_email.strip().casefold().rsplit("@", 1)
                        if (email_domain == domain and local in {
                            "info", "hello", "contact", "partners", "partnerships",
                            "vendors", "sales", "data",
                        }):
                            account["official_company_contact_email"] = raw_email.strip().casefold()
                            break
            account["official_company_contact_is_new_intro_approved"] = False
        seen = set()
        accepted = []
        for item in first_party_people[:90]:
            if not isinstance(item, Mapping):
                continue
            name, title = str(item.get("name") or "").strip(), str(item.get("title") or "").strip()
            url = str(item.get("url") or item.get("page_url") or "").strip()
            try:
                page_path = urlsplit(url).path.lower()
            except (ValueError, TypeError):
                continue
            # A third-party speaker quoted in an article on a company's
            # website is NOT an employee of that website's company. Restrict
            # employment-role attribution to first-party team/about pages,
            # not its news, resources, event or guest-interview pages.
            article_or_guest_page = (
                "/resources/" in page_path
                or page_path.startswith(("/blog", "/post", "/news", "/events", "/agenda"))
            )
            if (not _real_name(name) or not title or _host(url) != domain
                    or article_or_guest_page or name.casefold() in seen):
                continue
            seen.add(name.casefold())
            fit, role = _role_fit(title, lane)
            if fit < 50:
                continue
            raw_email = str(item.get("email") or "").strip().casefold()
            # Never guess an address from a name. Only an explicitly attached
            # person-mail pair published by the same company is a candidate.
            verified_email = (
                raw_email if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",raw_email)
                and raw_email.split("@")[-1] == domain
                and raw_email.split("@")[0] not in
                {"info","contact","hello","sales","support","office","team"}
                else None
            )
            rank = fit - (60 if history["state"] not in {
                "UNKNOWN_HISTORY", "DISCOVERED_NO_CONFIRMED_CONTACT",
            } else 0)
            accepted.append({
                "company": company, "domain": domain, "name": name,
                "title": title, "buyer_lane": lane, "role_fit_score": fit,
                "priority_score_research_only": max(0, rank),
                "buyer_role_hypothesis": role, "person_source_url": url,
                "source_type": "FIRST_PARTY_COMPANY_SITE_PROBE",
                "work_email_directly_published": verified_email,
                "contact_route": (
                    "EXACT_FIRST_PARTY_WORK_EMAIL" if verified_email
                    else "NAMED_PERSON_OFFICIAL_COMPANY_CONTACT_OR_PROFILE_NEEDED"
                ),
                "duplicate_or_prior_contact_state": history["state"],
                "do_not_send_new_intro": history["state"] not in {
                    "UNKNOWN_HISTORY", "DISCOVERED_NO_CONFIRMED_CONTACT",
                },
                "company_general_contact_email_not_person_email": (
                    account.get("official_company_contact_email")
                ),
                "company_general_contact_page": account.get(
                    "official_company_contact_page"
                ),
                "person_name_and_role_observed": True,
                "direct_person_contact_verified": bool(verified_email),
                "buyer_purchase_request_verified": False,
                "canonical_crm_suppression_cleared": False,
                "outbound_authorized": False,
            })
        accepted.sort(key=lambda row: (-row["priority_score_research_only"], row["name"]))
        account["named_people_found"] = len(accepted)
        account["direct_email_confirmed"] = sum(bool(row["work_email_directly_published"]) for row in accepted)
        contacts.extend(accepted[:4])
        accounts.append(account)
    contacts.sort(key=lambda row: (-row["priority_score_research_only"], row["company"], row["name"]))
    output = {
        "schema_version": SCHEMA, "status": "NAMED_BUYER_RESEARCH_REVIEWED",
        "as_of": now.astimezone(timezone.utc).isoformat(),
        "source_owner": "EXISTING_EMPIREOS_DATA_BROKERAGE_SEARCH_FABRIC",
        "product": "US_SEC_FORMD_COMPANY_INTELLIGENCE",
        "accounts_checked": len(accounts), "actual_people_discovered": len(contacts),
        "new_first_party_company_programs_verified": sum(
            a["company_program_source_verified"] for a in accounts
        ),
        "verified_direct_person_emails": sum(bool(r["work_email_directly_published"]) for r in contacts),
        "verified_product_purchasing_requests": 0,
        "outbound_sent": False, "auto_send": False, "crm_writes": False,
        "execution_authority": "none", "source_failures": failures,
        "accounts": accounts, "named_decision_maker_research": contacts,
    }
    output["integrity_sha256"] = digest(output)
    return output


def run_existing_owner_named_buyer_research(
    *, root: Path, now: datetime | None = None,
    probe_fn: Callable[..., Mapping[str, Any]] = probe_site,
    context: Mapping[str, Any] | None = None,
    discovery_fn: Callable[..., Mapping[str, Any]] | None = None,
    waterfall_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Canonical once/12h company discovery + Waterfall contact enrichment."""
    root = Path(root)
    if root != Path("/srv/empire_os"):
        return {"status": "NONCANONICAL_NAMED_CONTACT_OWNER_HOLD", "outbound_sent": False}
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    destination = root / "runtime/data_brokerage" / STATE
    if destination.is_symlink():
        raise ValueError("unsafe_named_buyer_research_receipt")
    previous_rotation = -1
    recent_attempted_domains: set[str] = set()
    if destination.exists():
        raw = destination.read_bytes()
        if not 0 < len(raw) < 100_000:
            raise ValueError("named_research_packet_too_large")
        previous = json.loads(raw)
        if not isinstance(previous, dict) or previous.get("schema_version") != SCHEMA:
            raise ValueError("named_research_packet_contract_invalid")
        p = dict(previous)
        signature = p.pop("integrity_sha256", None)
        if signature != digest(p):
            raise ValueError("named_research_packet_integrity_fail")
        timestamp = datetime.fromisoformat(str(previous["as_of"]).replace("Z","+00:00"))
        if timestamp.utcoffset() is None or timestamp > current + timedelta(minutes=5):
            raise ValueError("named_research_packet_future_clock")
        if (current - timestamp < REFRESH_GAP
                and (previous.get("company_discovery") or {}).get(
                    "first_party_company_mailbox_v4"
                ) is True
                and "waterfall_attempted_people" in previous):
            return {"status": "NAMED_BUYER_RESEARCH_FRESH",
                    "actual_people_discovered": previous["actual_people_discovered"],
                    "accounts_checked": previous["accounts_checked"],
                    "outbound_sent": False, "crm_writes": False,
                    "external_requests": 0}
        previous_rotation = previous.get("discovery_rotation", -1)
        if type(previous_rotation) is not int or not -1 <= previous_rotation <= 1000000:
            raise ValueError("invalid_buyer_company_discovery_rotation")
        if current - timestamp < timedelta(hours=24):
            recent_attempted_domains = {
                str(p.get("domain") or "")
                for p in (previous.get("named_decision_maker_research") or [])[:40]
                if (isinstance(p, Mapping) and isinstance(p.get("waterfall_enrichment"), Mapping)
                    and p["waterfall_enrichment"].get("attempted") is True)
            }
    rotation = previous_rotation + 1
    targets, source_health = discover_brokerage_companies(
        rotation=rotation, search_fn=discovery_fn,
    )
    report = inspect_named_buyer_accounts(
        now=current, context=context or load_context(),
        probe_fn=probe_fn, targets=targets,
    )
    report["discovery_rotation"] = rotation
    report["company_discovery"] = source_health
    report = enrich_named_contacts_with_waterfall(
        report, waterfall_factory=waterfall_factory,
        max_people=2, rotation=rotation,
        recently_attempted_domains=recent_attempted_domains,
    )
    report.pop("integrity_sha256", None)
    report["integrity_sha256"] = digest(report)
    if report["outbound_sent"] or report["crm_writes"] or report["execution_authority"] != "none":
        raise ValueError("named_buyer_research_authority_violation")
    atomic_private(destination, report)
    return {"status": "NAMED_BUYER_RESEARCH_REVIEWED",
            "actual_people_discovered": report["actual_people_discovered"],
            "verified_direct_person_emails": report["verified_direct_person_emails"],
            "waterfall_verified_exact_person_emails": report["waterfall_verified_exact_person_emails"],
            "new_company_vendor_programmes_verified": report["new_first_party_company_programs_verified"],
            "company_search_provider_state": source_health["search_provider_state"],
            "accounts_checked": report["accounts_checked"],
            "report_sha256": report["integrity_sha256"],
            "outbound_sent": False, "crm_writes": False,
            "external_requests_upper_bound": len(targets) * 2 + 1}


def discover_brokerage_companies(
    *, rotation: int,
    search_fn: Callable[..., Mapping[str, Any]] | None = None,
    first_party_fn: Callable[..., Mapping[str, Any]] | None = None,
) -> tuple[tuple[tuple[str, ...], ...], dict[str, Any]]:
    """Discover source-linked data-distribution organisations, never buyers.

    Reuses the original Search Fabric recovery lane. Public/paid provider
    unavailable is logged as degraded, NOT as absence of potential customers.
    One search, three rotating independently identified first-party programmes,
    no unverified listing or generic company-domain blast.
    """
    if type(rotation) is not int or rotation < 0:
        raise ValueError("buyer_company_discovery_rotation_invalid")
    candidates = list(TARGET_ORGS)
    seen = {item[1] for item in candidates}
    for offset in range(3):
        target = PROGRAM_SOURCES[(rotation + offset) % len(PROGRAM_SOURCES)]
        if target[1] not in seen:
            candidates.append(target)
            seen.add(target[1])
    metrics: dict[str, Any] = {
        "source": "EXISTING_SEARCH_FABRIC_RECOVERY_AND_FIRST_PARTY_VENDOR_PROGRAMMES",
        "approved_first_party_programme_seeds": len(PROGRAM_SOURCES),
        "rotating_first_party_programmes_attempted": len(candidates)-len(TARGET_ORGS),
        "external_search_requests_upper_bound": 1,
        "search_provider_state": "UNAVAILABLE_OR_NO_USABLE_PUBLIC_RESULTS",
        "first_party_index_prefilter_v2": True,
        "first_party_about_page_enrichment_v3": True,
        "first_party_company_mailbox_v4": True,
        "fresh_unseeded_search_candidates": 0,
        "buyer_purchase_requests_verified": 0,
        "buyer_contact_authorized": False,
    }
    query = COMPANY_SEARCH_QUERIES[rotation % len(COMPANY_SEARCH_QUERIES)]
    # The existing Agent Reach index has first-party evidence from recent
    # cycles. A targeted lookup should consult it BEFORE any public web
    # attempt. The older isolated test worktree lacks the newer production
    # reader, so keep the import optional; no replacement module is created.
    if first_party_fn is None and search_fn is None:
        try:
            from empire_os.search_fabric.first_party_source_recovery import search_sources
            first_party_fn = search_sources
        except ImportError:
            first_party_fn = None
    result: Mapping[str, Any] = {}
    if first_party_fn is not None:
        try:
            first_party_result = first_party_fn(query, num=6)
            if (isinstance(first_party_result, Mapping)
                    and first_party_result.get("organic")):
                result = first_party_result
                metrics["external_search_requests_upper_bound"] = 0
        except (OSError, ValueError, TypeError, KeyError):
            pass
    if not result:
        if search_fn is None:
            from empire_os.search_fabric.reliable_search import search_reliable
            search_fn = search_reliable
        try:
            result = search_fn(query, num=6, use_cache=True)
        except Exception:
            result = {}
    if isinstance(result, Mapping):
        params = result.get("searchParameters") or {}
        metrics["search_provider_state"] = str(
            params.get("search_state") or result.get("search_operational_status") or
            "UNKNOWN_PROVIDER_STATE"
        )[:90]
        rows = result.get("organic") or []
        indexed = (
            params.get("engine") == "first_party_source_recovery"
            and params.get("source_scope") == "FIRST_PARTY_REVIEW_ONLY"
            and params.get("search_state") == "INDEXED_FIRST_PARTY_EVIDENCE"
        )
        metrics["first_party_index_recovered"] = bool(indexed)
        if isinstance(rows, list):
            for row in rows[:6]:
                if not isinstance(row, Mapping):
                    continue
                url = str(row.get("link") or row.get("url") or "").strip()
                domain = _host(url)
                if not domain or domain in seen or domain.count(".") < 1:
                    continue
                if re.search(r"(?:^|\.)((?:linkedin|facebook|google|youtube|bing|reddit|wikipedia)\.[a-z.]+)$",domain):
                    continue
                if not re.search(
                    r"vendor|data-provider|data-partner|data-seller|submit.provider|dataset|partners",
                    urlsplit(url).path, flags=re.IGNORECASE,
                ):
                    continue
                public_claim = " ".join((str(row.get("title") or ""),
                                         str(row.get("snippet") or ""))).casefold()
                first_party_index_evidence = (
                    indexed
                    and row.get("source_class") == "FIRST_PARTY_PUBLIC_REVIEW"
                    and str(row.get("evidence_url") or "") == url
                    and "buyer" in public_claim
                    and "data" in public_claim
                    and row.get("buyer_accepted") is False
                    and row.get("outreach_authorized") is False
                )
                if not first_party_index_evidence and not any(
                    term in public_claim
                    for term in ("data provider", "data vendor", "dataset", "alternative data")
                ):
                    continue
                # Indexed first-party source titles describe indexed sources,
                # not company legal names. Use the observed domain as a stable
                # research label until the official website establishes a name.
                candidate_name = (
                    domain if first_party_index_evidence
                    else str(row.get("title") or "").split("|")[-1].strip()[:70]
                )
                if not candidate_name or len(candidate_name)<3:
                    continue
                candidates.append((candidate_name,domain,url,"DATA_VENDOR_PARTNER",url))
                seen.add(domain)
                metrics["fresh_unseeded_search_candidates"] += 1
                if metrics["fresh_unseeded_search_candidates"] >= 2:
                    break
    return tuple(candidates[:9]), metrics


def enrich_named_contacts_with_waterfall(
    report: dict[str, Any],
    *, waterfall_factory: Callable[[], Any] | None = None,
    max_people: int = 1,
    rotation: int = 0,
    recently_attempted_domains: set[str] | None = None,
) -> dict[str, Any]:
    """Reuse original Registry -> SiteCrawler -> EmpireHunter, exact-person only.

    There is no contact guessing, acceptance of a different company employee,
    provider spend, SMTP send, CRM write, or email authority. Results from a
    domain-level best-contact search are NOT a match until exact person/source
    binding independently passes these additional constraints.
    """
    if waterfall_factory is None:
        from empire_os.waterfall import build_default_waterfall
        waterfall_factory = build_default_waterfall
    if (type(max_people) is not int or not 0 <= max_people <= 2
            or type(rotation) is not int or rotation < 0):
        raise ValueError("unbounded_contact_enrichment")
    people = report.get("named_decision_maker_research") or []
    recent = recently_attempted_domains or set()
    if not isinstance(recent, set) or len(recent) > 100:
        raise ValueError("invalid_prior_waterfall_enrichment_domains")
    # Expensive Waterfall requests should not inspect two people at the
    # same company in one cycle. Rotate distinct organisations across the
    # existing 12-hour owner schedule to avoid always querying Neudata.
    unique_companies = set()
    eligible = []
    for person in people:
        if (person["role_fit_score"] < 70
                or person["do_not_send_new_intro"]
                or person.get("direct_person_contact_verified")
                or person["domain"] in recent
                or person["domain"] in unique_companies):
            continue
        eligible.append(person)
        unique_companies.add(person["domain"])
    if eligible:
        start = rotation % len(eligible)
        eligible = eligible[start:] + eligible[:start]
    chosen = eligible[:max_people]
    chosen_people = {id(p) for p in chosen}
    attempted_order = chosen + [p for p in people if id(p) not in chosen_people]
    attempts = 0
    verified_count = 0
    for candidate in attempted_order:
        candidate["waterfall_enrichment"] = {
            "status": "NOT_DUE_OR_OUT_OF_SCOPE",
            "attempted": False,
            "personal_email_verified": False,
            "outbound_authorized": False,
        }
        if id(candidate) not in chosen_people:
            continue
        attempts += 1
        try:
            wf=waterfall_factory()
            names=[p.name for p in wf.providers[:wf.max_attempts]]
            if names != ["registry_scraper", "site_crawler", "empire_hunter"]:
                raise ValueError("noncanonical_waterfall_provider_list")
            if (wf.gate.min_confidence < 0.90
                    or wf.gate.require_bound_contact is not True
                    or wf.gate.require_email is not True
                    or any(p.cost_cents != 0 for p in wf.providers[:wf.max_attempts])):
                raise ValueError("noncanonical_waterfall_verification_or_spend")
            r=wf.enrich({
                "company": candidate["company"], "business_name": candidate["company"],
                "domain": candidate["domain"],
                "website": "https://" + candidate["domain"] + "/",
                "person_name": candidate["name"],
                "person_title": candidate["title"],
            })
            con = r.contact
            reason="NO_CONFIRMED_MATCH"
            exact = bool(
                r.success and r.validated and r.cost_cents == 0 and con
                and con.confidence >= 0.90
                and con.source == "empire_hunter"
                and (con.first_name+" "+con.last_name).strip().casefold()
                == candidate["name"].strip().casefold()
                and con.raw.get("bound_to_decision_maker") is True
                and con.raw.get("first_party") is True
                and _host(str(con.raw.get("source_url") or "")) == candidate["domain"]
                and isinstance(con.email,str)
                and con.email.casefold().rsplit("@",1)[-1] == candidate["domain"]
                and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",con.email)
            )
            if exact:
                # A person-matched Hunter verified email is NOT described as
                # "directly published" on a probed profile page.
                candidate["waterfall_verified_person_email"] = con.email.casefold()
                candidate["contact_route"] = "EMPIRE_HUNTER_FIRST_PARTY_EXACT_PERSON_VERIFIED"
                candidate["direct_person_contact_verified"] = True
                verified_count += 1
                reason="EXACT_PERSON_FIRST_PARTY_EMPIRE_HUNTER_VERIFIED"
            candidate["waterfall_enrichment"] = {
                "status": reason,
                "attempted": True,
                "personal_email_verified": exact,
                "provider_sequence": list(r.providers_tried),
                "verified_person_evidence_url": (
                    con.raw["source_url"] if exact else None
                ),
                "claimed_cost_cents": r.cost_cents,
                "outbound_authorized": False,
            }
        except Exception as exc:
            candidate["waterfall_enrichment"] = {
                "status": "FAIL_CLOSED_" + type(exc).__name__,
                "attempted": True,
                "personal_email_verified": False,
                "outbound_authorized": False,
            }
    report["waterfall_recent_domain_cooldown_count"] = len(recent)
    report["waterfall_attempted_people"] = attempts
    report["waterfall_verified_exact_person_emails"] = verified_count
    report["verified_contactable_person_count"] = sum(
        bool(x.get("direct_person_contact_verified"))
        for x in report.get("named_decision_maker_research") or []
    )
    report["waterfall_person_role_suppression_rechecked"] = True
    report["outbound_sent"] = False
    report["crm_writes"] = False
    return report
