"""Bounded public first-party research refresher on native founder-acquisition cadence.

YC listings are *claims*, not proof of customer interest or CRM clearance.
Does not contact prospects, store web content, mutate CRM, or create send intent.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import html
import re
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from empire_os.workspace_solar_reply_tracking import EvidenceHeld

SCHEMA = "empire.founder_acquisition_public_source_refresh.v1"
MAX_BYTES = 600_000
URL_PATTERN = re.compile(r"^/companies/[a-z0-9]+(?:-[a-z0-9]+)*$")
EMAIL_PATTERN = re.compile(r"^[a-z0-9._+%-]+@[a-z0-9.-]+\.[a-z]{2,24}$")
ASK_PATTERN = re.compile(r"(?:our ask|we(?:'|’|\u2019)?d love warm intros|looking for introductions)", re.I)


def _safe_url(value: Any) -> bool:
    if not isinstance(value, str) or not 20 <= len(value) <= 180:
        return False
    parts = urlsplit(value)
    return (parts.scheme == "https" and parts.netloc == "www.ycombinator.com"
            and not parts.username and not parts.password
            and not parts.query and not parts.fragment
            and bool(URL_PATTERN.fullmatch(parts.path)))


def verify_profile(company: str, url: str, email: str, *, fetched: Mapping[str, Any],
                   observed_at: datetime) -> dict[str, Any]:
    """Validate only original first-party profile provenance and published contact."""
    if not _safe_url(url) or not isinstance(email, str) or not EMAIL_PATTERN.fullmatch(email):
        raise EvidenceHeld("INVALID_OR_UNTRUSTED_SOURCE_IDENTITY")
    if (not isinstance(fetched, Mapping) or fetched.get("status_code") != 200
            or fetched.get("final_url") != url
            or fetched.get("content_type") != "text/html"):
        raise EvidenceHeld("ORIGINAL_SOURCE_HTTP_NOT_VERIFIED")
    body = fetched.get("body")
    if not isinstance(body, bytes) or not 100 <= len(body) <= MAX_BYTES:
        raise EvidenceHeld("UNTRUSTED_SOURCE_BODY_SIZE")
    page = html.unescape(body.decode("utf-8", errors="replace"))
    m = re.search(r"<title[^>]*>(.*?)</title\s*>", page, flags=re.I | re.S)
    title = html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""
    name = " ".join(str(company or "").split())
    if (not name or len(name) > 140 or not re.search(
            r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])",
            title, flags=re.I)):
        raise EvidenceHeld("COMPANY_TITLE_IDENTITY_MISMATCH")
    # The email must appear *literally* in the original page and must be the
    # already catalogued first-party contact, never inferred or generated.
    if email.casefold() not in page.casefold():
        raise EvidenceHeld("PUBLISHED_ADDRESS_NOT_CORROBORATED")
    return {
        "company": name, "source_url": url,
        "observed_at_utc": observed_at.astimezone(timezone.utc).isoformat(),
        "source_sha256": sha256(body).hexdigest(),
        "profile_source_status": "FIRST_PARTY_PROFILE_AND_ADDRESS_OBSERVED",
        "public_ask_marker_observed": bool(ASK_PATTERN.search(page)),
        "buyer_intent_verified": False, "canonical_suppression_verified": False,
        "crm_reconciled": False, "outbound_authorized": False,
        "email_draft_approved": False,
    }


def fetch_profile(url: str) -> Mapping[str, Any]:
    """Use an exact allowlisted public URL, refuse redirected/private sources."""
    if not _safe_url(url):
        raise EvidenceHeld("UNTRUSTED_PUBLIC_SOURCE_URL")
    import requests
    try:
        response = requests.get(
            url, timeout=(2, 5), allow_redirects=False,
            headers={"User-Agent": "EmpireAI-OriginalSourceResearch/1.0",
                     "Accept": "text/html"},
            stream=True,
        )
        try:
            raw = response.raw.read(MAX_BYTES + 1, decode_content=True)
        finally:
            response.close()
        ctype = str(response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        return {"status_code": response.status_code, "final_url": response.url,
                "content_type": ctype, "body": raw}
    except (requests.RequestException, OSError, ValueError):
        raise EvidenceHeld("PUBLIC_SOURCE_FETCH_UNAVAILABLE") from None


def refresh_pending(
    rows: list[Mapping[str, str]], *,
    previous: Mapping[str, Any] | None,
    now: datetime,
    fetch: Callable[[str], Mapping[str, Any]] = fetch_profile,
    max_fetch: int = 2,
) -> dict[str, Any]:
    if (now.tzinfo is None or now.utcoffset() is None
            or type(max_fetch) is not int or not 1 <= max_fetch <= 2
            or not 1 <= len(rows) <= 500):
        raise EvidenceHeld("INVALID_REFRESH_BOUNDARIES")
    at = now.astimezone(timezone.utc)
    prior: dict[str, dict[str, Any]] = {}
    if previous is not None:
        if (previous.get("schema_version") != SCHEMA
                or previous.get("status") != "PUBLIC_SOURCES_REVIEW_ONLY"):
            raise EvidenceHeld("UNTRUSTED_PREVIOUS_PUBLIC_SOURCE_SNAPSHOT")
        old = previous.get("profiles")
        if not isinstance(old, list) or len(old) > 500:
            raise EvidenceHeld("UNTRUSTED_PREVIOUS_PROFILE_LIST")
        for item in old:
            if (not isinstance(item, dict) or item.get("company") in prior
                    or item.get("profile_source_status") not in (
                        "FIRST_PARTY_PROFILE_AND_ADDRESS_OBSERVED",
                        "HELD_SOURCE_NOT_VERIFIED")):
                raise EvidenceHeld("INVALID_PREVIOUS_SOURCE_ATTESTATION")
            prior[item["company"]] = item
    names = [str(row.get("company") or "") for row in rows]
    if len(names) != len(set(names)) or any(name in ("", "Plena Health") for name in names):
        raise EvidenceHeld("DUPLICATE_OR_CONTACTED_SOURCE_CANDIDATE")
    if set(prior) - set(names):
        raise EvidenceHeld("UNEXPLAINED_SOURCE_PROSPECT_REMOVAL")
    output = []
    checked = 0
    for row in rows:
        name = row["company"]
        previous_item = prior.get(name)
        eligible = True
        if previous_item:
            try:
                previous_at = datetime.fromisoformat(previous_item["observed_at_utc"])
                if previous_at.tzinfo is None or previous_at > at:
                    raise ValueError("untrusted_previous_time")
                # Source profiles are rechecked each 7d; failed sources are
                # retried no faster than every 24h. Two fetches max per cycle.
                interval = timedelta(days=7 if previous_item["profile_source_status"].startswith("FIRST_PARTY") else 1)
                eligible = at - previous_at >= interval
            except (ValueError, TypeError, KeyError):
                raise EvidenceHeld("INVALID_PREVIOUS_REFRESH_CLOCK") from None
        if eligible and checked < max_fetch:
            checked += 1
            try:
                result = verify_profile(
                    name, row["yc_original_source"], row["published_contact"],
                    fetched=fetch(row["yc_original_source"]), observed_at=at,
                )
            except Exception:
                # No source text/error is retained; network failures never
                # turn a prospect into an approved contact.
                result = {
                    "company": name, "source_url": row["yc_original_source"],
                    "observed_at_utc": at.isoformat(),
                    "profile_source_status": "HELD_SOURCE_NOT_VERIFIED",
                    "buyer_intent_verified": False,
                    "canonical_suppression_verified": False,
                    "outbound_authorized": False,
                }
            output.append(result)
        elif previous_item is not None:
            output.append(previous_item)
    verified = sum(x["profile_source_status"] == "FIRST_PARTY_PROFILE_AND_ADDRESS_OBSERVED" for x in output)
    # No automatic email draft can be shipped without the original company
    # asking for introductions and a verified original profile contact.
    # Proposals remain editing prompts, not claims about buying interest.
    by_company = {row["company"]: row for row in rows}
    suggested = []
    for evidence in output:
        if (evidence["profile_source_status"] != "FIRST_PARTY_PROFILE_AND_ADDRESS_OBSERVED"
                or evidence.get("public_ask_marker_observed") is not True):
            continue
        name = evidence["company"]
        target = str(by_company[name].get("public_request_target") or "").strip()
        # The segment is internal targeting research: a *hypothesis*, not a
        # fact independently verified by the external public profile.
        if not 8 <= len(target) <= 190 or any(c in target for c in "\r\n"):
            continue
        suggested.append({
            "company": name,
            "subject": "Source-verified account research for " + name,
            "body": (
                "Hi,\n\n"
                "I came across " + name + "\'s public YC profile and your request "
                "for relevant introductions. We can't promise existing warm "
                "introductions, but Empire AI researches source-verified "
                "company-level account opportunities.\n\n"
                "We could scope a short, five-company research sample around "
                + target + ", including dated original sources, fit checks "
                "and reasons to exclude weak matches. These would be "
                "research hypotheses, not verified buyers.\n\n"
                "Would something like that be useful for your current "
                "prospecting, or does your team already have sufficient "
                "coverage?\n\nPhil\nEmpire AI"
            ),
            "status": "UNSENT_FOUNDER_REVIEW_REQUIRED",
            "public_profile_contact_proved": True,
            "crm_contact_and_suppression_verified": False,
        })
    return {
        "schema_version": SCHEMA,
        "status": "PUBLIC_SOURCES_REVIEW_ONLY",
        "mode": "OBSERVE", "observed_at_utc": at.isoformat(),
        "prospect_count": len(rows), "reviewed_profiles": len(output),
        "verified_public_profiles": verified,
        "source_fetches_this_cycle": checked,
        "profiles": output,
        "unsent_review_drafts": suggested,
        "prospects_waiting_for_source_check": len(rows) - len(output),
        "crm_writes": False, "outbound_sent": False,
        "buyer_interest_verified": False, "automatic_send_authorized": False,
        "paid_pilot_authorized": False, "execution_authority": "none",
    }
