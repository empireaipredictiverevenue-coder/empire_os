"""V5 evidence join for approved microsites, using original owner readers only.

This is an adapter around V4, not a new analytics collector or money ledger.
Every source is injected by its independently authorised owning service. A
caller-provided JSON manifest, score or boolean must never substitute for one.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
import re
from typing import Any

from empire_os.microsite_approved_page_measurement_v4 import review_deployed_microsite
from empire_os.predictive_microsite_factory import build_candidate

Reader = Callable[[str], Mapping[str, Any] | None]
_CAMPAIGN = re.compile(r"campaign_[0-9a-f]{24}\Z")


@dataclass(frozen=True)
class OriginalPageReaders:
    """Authorised service-owned adapters, not caller-provided proof objects."""
    site_owner: Reader | None = None
    gsc: Reader | None = None
    first_party_events: Reader | None = None
    crm: Reader | None = None
    settlement: Reader | None = None


def _window(start: str, end: str) -> tuple[str, str]:
    try:
        left, right = date.fromisoformat(start), date.fromisoformat(end)
    except (TypeError, ValueError) as exc:
        raise ValueError("measurement window requires ISO calendar dates") from exc
    if right < left or right - left > timedelta(days=31):
        raise ValueError("measurement window out of bounded range")
    return left.isoformat(), right.isoformat()


def _unique_refs(values: Any, label: str) -> tuple[str, ...]:
    if not isinstance(values, list) or len(values) > 10000:
        raise ValueError(f"{label} must be bounded original event references")
    if any(not isinstance(v, str) or not 8 <= len(v) <= 180
           or any(ch.isspace() for ch in v) for v in values):
        raise ValueError(f"{label} contains invalid event reference")
    if len(values) != len(set(values)):
        raise ValueError(f"{label} repeats event reference")
    return tuple(values)


def reconcile_approved_page(
    spec: Mapping[str, Any], *, readers: OriginalPageReaders,
    window_start: str, window_end: str,
) -> tuple[dict[str, Any], frozenset[str], frozenset[str]]:
    """Require identical release, dates and accepted-event lineage.

    Returns a public-safe aggregate and private event-ref sets for portfolio
    duplicate checks. Raw contact data and event references aren't emitted.
    """
    start, end = _window(window_start, window_end)
    candidate, _ = build_candidate(spec)
    cid = candidate["id"]
    observed: dict[str, Mapping[str, Any]] = {}
    release_identity: dict[str, str] = {}

    def site_owner(key: str) -> Mapping[str, Any] | None:
        if readers.site_owner is None:
            return None
        row = readers.site_owner(key)
        if row is None:
            return None
        if not isinstance(row, Mapping):
            raise ValueError("original website release row invalid")
        campaign = row.get("canonical_campaign_id")
        asset = row.get("canonical_asset_id")
        # The draft noindex preview is NOT the production HTML. The actual
        # deployed bytes must have an owner-custodied SHA bound to this draft.
        preview = row.get("source_preview_sha256")
        deployed = row.get("asset_sha256")
        if (not isinstance(campaign, str) or not _CAMPAIGN.fullmatch(campaign)
                or asset != campaign + ":landing"
                or row.get("public_url") !=
                f"https://empire-ai.co.uk/research/{campaign}"
                or row.get("immutable_release_readback") is not True
                or row.get("deployed_asset_readback_verified") is not True
                or not isinstance(preview, str) or len(preview) != 64
                or not isinstance(deployed, str) or len(deployed) != 64):
            raise ValueError("original immutable release identity invalid")
        release_identity.update(campaign_id=campaign, asset_id=asset)
        observed["site"] = row
        return row

    def original_reader(owner: str, reader: Reader | None) -> Reader | None:
        if reader is None:
            return None

        def verify(url: str) -> Mapping[str, Any] | None:
            if "site" not in observed:
                raise ValueError("original site-owner release must be checked first")
            row = reader(url)
            if row is None:
                return None
            if not isinstance(row, Mapping):
                raise ValueError(f"{owner} source must return a mapping")
            if (row.get("window_start") != start
                    or row.get("window_end") != end
                    or row.get("canonical_campaign_id") != release_identity["campaign_id"]
                    or row.get("canonical_asset_id") != release_identity["asset_id"]):
                raise ValueError(f"{owner} original page, asset or time-window join mismatched")
            observed[owner] = row
            return row
        return verify

    result = review_deployed_microsite(
        spec,
        original_site_owner_reader=site_owner if readers.site_owner else None,
        original_gsc_reader=original_reader("gsc", readers.gsc),
        original_first_party_reader=original_reader("events", readers.first_party_events),
        original_crm_reader=original_reader("crm", readers.crm),
        original_settlement_reader=original_reader("settlement", readers.settlement),
    )
    accepted: tuple[str, ...] = ()
    settled_ids: tuple[str, ...] = ()
    if "crm" in observed:
        crm = observed["crm"]
        accepted = _unique_refs(crm.get("canonical_buyer_accepted_event_refs"),
                                "CRM buyer acceptance")
        if len(accepted) != result["buyer_accepted_events"]:
            raise ValueError("CRM accepted event references don't match canonical count")

    if "settlement" in observed:
        settlement = observed["settlement"]
        records = settlement.get("original_settled_event_rows")
        if not isinstance(records, list) or len(records) > 10000:
            raise ValueError("settlement requires bounded original event rows")
        if any(not isinstance(r, Mapping) for r in records):
            raise ValueError("settlement contains invalid event rows")
        settled_ids = _unique_refs(
            [r.get("accepted_event_ref") for r in records], "settled accepted-event")
        settlement_refs = _unique_refs(
            [r.get("settlement_ref") for r in records], "settlement receipt")
        if not set(settled_ids) <= set(accepted):
            raise ValueError("settled event not found in original accepted buyer events")
        amounts = [r.get("amount_minor") for r in records]
        if any(type(amount) is not int or amount <= 0 or amount > 100000000
               for amount in amounts):
            raise ValueError("unverified or nonpositive settlement amount")
        if sum(amounts) != result["settled_revenue_minor"]:
            raise ValueError("settlement total differs from original event receipts")

    status = (
        "NO_ORIGINAL_OWNER_PAGE_RELEASE" if result["public_url"] is None
        else "ATTRIBUTED_SETTLEMENT_VERIFIED"
        if result["attributed_revenue_verified"]
        else "OWNER_RELEASE_VERIFIED_PARTIAL_MEASUREMENT"
    )
    # CTR uses page impressions, not consented website sessions; unrelated
    # metrics remain separate and are never described as buyer conversion.
    impressions = result["organic_search_impressions"]
    clicks = result["organic_search_clicks"]
    ctr = round(clicks / impressions, 6) if impressions else None
    sessions = result["consent_verified_sessions"]
    enquiries = result["consented_enquiries"]
    enquiry_per_session = round(enquiries / sessions, 6) if sessions and enquiries is not None else None
    report = {
        "schema_version": "empire.microsite.verified_page_outcome_v5",
        "candidate_id": cid,
        "period": [start, end],
        "status": status,
        "public_url": result["public_url"],
        "original_release_asset_sha256": result["source_asset_sha256"] if result["public_url"] else None,
        "canonical_campaign_id": release_identity.get("campaign_id"),
        "canonical_asset_id": release_identity.get("asset_id"),
        "organic_search_impressions": impressions,
        "organic_search_clicks": clicks,
        "organic_search_ctr": ctr,
        "consent_verified_sessions": sessions,
        "consented_enquiries": enquiries,
        "enquiry_per_consented_session": enquiry_per_session,
        "qualified_enquiries": result["qualified_enquiries"],
        "buyer_accepted_events": result["buyer_accepted_events"],
        "individually_reconciled_accepted_event_count": len(accepted) if "crm" in observed else None,
        "settled_events": len(settled_ids) if "settlement" in observed else None,
        "settled_revenue_minor": result["settled_revenue_minor"],
        "settlement_currency": result["settled_currency"],
        "attributed_revenue_verified": result["attributed_revenue_verified"] and
        "settlement" in observed,
        "source_receipts": result["source_receipts"],
        "source_count": len(result["source_receipts"]),
        "private_identity_refs_exposed": False,
        "original_reader_identity_requires_external_authorisation": True,
        "independent_reader_permission_verified_by_this_module": False,
        "execution_authority": "none",
        "publishing_enabled": False,
        "database_writes": False,
        "payment_action": False,
    }
    return report, frozenset(accepted), frozenset(settled_ids)


def build_approved_microsite_scorecard(
    specs: Sequence[Mapping[str, Any]], *,
    readers: OriginalPageReaders,
    window_start: str, window_end: str,
) -> dict[str, Any]:
    """Scorecard over separately owner-approved pages, not whole-site estimates."""
    start, end = _window(window_start, window_end)
    if not isinstance(specs, (list, tuple)) or not 1 <= len(specs) <= 25:
        raise ValueError("candidate scorecard must be a bounded list")
    seen_candidates: set[str] = set()
    all_accepted: set[str] = set()
    all_settled: set[str] = set()
    all_campaigns: set[str] = set()
    all_urls: set[str] = set()
    reports = []
    for spec in specs:
        row, accepted, settled = reconcile_approved_page(
            spec, readers=readers, window_start=start, window_end=end)
        cid = row["candidate_id"]
        if cid in seen_candidates:
            raise ValueError("duplicate factory candidate identity")
        if all_accepted.intersection(accepted) or all_settled.intersection(settled):
            raise ValueError("canonical event claimed by more than one microsite")
        if (row["canonical_campaign_id"] is not None
                and row["canonical_campaign_id"] in all_campaigns):
            raise ValueError("canonical campaign claimed by multiple factory pages")
        if row["public_url"] is not None and row["public_url"] in all_urls:
            raise ValueError("deployed URL claimed by multiple factory pages")
        if row["canonical_campaign_id"]:
            all_campaigns.add(row["canonical_campaign_id"])
        if row["public_url"]:
            all_urls.add(row["public_url"])
        seen_candidates.add(cid)
        all_accepted.update(accepted)
        all_settled.update(settled)
        reports.append(row)
    return {
        "schema_version": "empire.microsite.approved_portfolio_outcomes_v5",
        "period": [start, end], "mode": "READ_ONLY",
        "candidate_count": len(reports),
        "approved_original_site_pages": sum(r["public_url"] is not None for r in reports),
        "pages_with_original_gsc_metrics": sum(r["organic_search_impressions"] is not None for r in reports),
        "pages_with_verified_sessions": sum(r["consent_verified_sessions"] is not None for r in reports),
        "pages_with_canonical_enquiries": sum(r["consented_enquiries"] is not None for r in reports),
        "pages_with_independently_settled_revenue": sum(r["attributed_revenue_verified"] for r in reports),
        "realised_revenue_by_currency": {
            currency: sum(
                r["settled_revenue_minor"] for r in reports
                if r["attributed_revenue_verified"] and r["settlement_currency"] == currency
            )
            for currency in ("GBP", "USD")
            if any(r["attributed_revenue_verified"] and r["settlement_currency"] == currency
                   for r in reports)
        },
        "unknown_is_not_zero": True,
        "execution_authority": "none",
        "new_event_collectors": 0, "database_writes": False,
        "outbound_sent": False, "payment_action": False, "published": False,
        "pages": reports,
    }
