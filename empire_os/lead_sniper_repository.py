"""EmpireDB-only Lead Sniper review queue adapter.

Replaces legacy empire_os.sb/Supabase in lead_sniper_agent.py. This is a
review queue for independently corroborated B2B firms, NOT outreach approval.

Operator must separately set two explicit gates before production writes:
 EMPIRE_SNIPER_REVIEW_QUEUE_ENABLE=1
 EMPIRE_SNIPER_CANONICAL_WRITES_APPROVED=1

No automatic contact enrolment, CRM promotion, financial/trade execution, or
consumer/claimant targeting. Never silently falls back to a second backend.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit
import ipaddress
import os
import re

from empire_os.canonical_data_gateway import (
    CanonicalDataGateway, gateway_from_environment,
)
from empire_os.data_cloud_contract import DataBackend
from empire_os.data_query import DataFilter
from empire_os.runtime_env import load_runtime_env
from empire_os.source_intelligence import SOURCES

TASK_TABLE = "empire_tasks"
TASK_TYPE = "sniper_review"
SCHEMA = "empire.lead_sniper_canonical_review.v1"
MAX_URL_LEN = 1800
MAX_QUERY_RESULTS = 2
MAX_DEDUP_HOURS = 168
# Only explicit registered corporate source evidence, not consumer urgency
# RSS or non-verified directory snippets.
SAFE_VERTICALS = frozenset({
    "roofing", "solar", "hvac", "restoration", "dental",
    "insurance", "legal", "mass_torts", "plumbing", "electrical",
    "pest_control", "landscaping",
})
REGULATED = frozenset({"insurance", "legal", "mass_torts", "dental"})
SOURCE_ALIASES = {"recc_solar": "gb_recc_solar"}


def _evidence_reference(value: Any) -> bool:
    return (isinstance(value, str) and 8 <= len(value) <= 250
            and value == value.strip()
            and not any(ord(ch) < 32 for ch in value))


def _source_url(value: Any) -> str:
    if not isinstance(value, str) or not 0 < len(value) <= MAX_URL_LEN:
        return ""
    try:
        parts = urlsplit(value)
        if (parts.scheme != "https" or not parts.hostname
                or parts.username or parts.password or parts.port is not None
                or parts.fragment or parts.query):
            return ""
        host = parts.hostname.lower().rstrip(".")
        if (not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", host)
                or host.endswith((".local", ".internal", ".localhost"))
                or ".." in host
                or any(x.startswith("-") or x.endswith("-") for x in host.split("."))):
            return ""
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return value
    except ValueError:
        pass
    return ""


def _timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def review_b2b_sniper_candidate(
    lead: Mapping[str, Any], niche: str, score: float,
    *, now: datetime | None = None,
) -> dict[str, Any]:
    """Produce one *review proposal*. Untrusted sniper scores never prove intent."""
    if not isinstance(lead, Mapping):
        raise TypeError("lead must be mapping")
    if not isinstance(niche, str) or not isinstance(score, (int, float)):
        raise TypeError("invalid niche/score")
    import math
    if not math.isfinite(score):
        raise ValueError("nonfinite score")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must be timezone aware")

    details = lead.get("details")
    details = details if isinstance(details, Mapping) else {}
    url = _source_url(details.get("url"))
    name = lead.get("business_name") or lead.get("company_name")
    company = name.strip() if isinstance(name, str) else ""
    reasons = []
    if not url:
        reasons.append("verified_https_source_url_required")
    if niche not in SAFE_VERTICALS:
        reasons.append("unsupported_business_vertical")
    if (not company or len(company) < 4 or len(company) > 200
            or company.casefold() in {"home", "contact", "services", "unknown"}):
        reasons.append("business_name_not_verified")
    if lead.get("entity_kind") not in {"company", "business"}:
        reasons.append("b2b_entity_classification_not_proven")
    if lead.get("contains_consumer_claimant_or_patient_data") is not False:
        reasons.append("consumer_and_sensitive_data_exclusion_not_proven")
    if not _evidence_reference(lead.get("canonical_business_identity_ref")):
        reasons.append("independent_canonical_business_identity_receipt_required")
    if not _evidence_reference(lead.get("source_rights_receipt_ref")):
        reasons.append("lawful_source_use_receipt_required")
    if not _evidence_reference(lead.get("source_territory_ref")):
        reasons.append("business_territory_evidence_required")
    if niche in REGULATED and not _evidence_reference(
        lead.get("jurisdiction_policy_ref")
    ):
        reasons.append("regulated_b2b_jurisdiction_review_required")
    if lead.get("outreach_authorized") is not False:
        reasons.append("outreach_must_be_explicitly_disabled")
    source_id = lead.get("registered_source_id") or lead.get("source")
    source_id = SOURCE_ALIASES.get(source_id, source_id) if isinstance(source_id, str) else None
    contract = SOURCES.get(source_id) if isinstance(source_id, str) else None
    territory = str(lead.get("territory_code") or "")
    if (contract is None or contract.production_status != "verified"
            or "identity" not in contract.roles
            or "internal_acquisition" not in contract.allowed_uses):
        reasons.append("registered_identity_source_and_rights_required")
    else:
        if niche not in contract.niches and "all" not in contract.niches:
            reasons.append("source_not_authorized_for_vertical")
        if not territory.startswith(contract.country_code + "-"):
            reasons.append("source_country_or_territory_mismatch")
        evidence_url = _source_url(lead.get("registered_source_evidence_url"))
        if not evidence_url or urlsplit(evidence_url).hostname != urlsplit(contract.url).hostname:
            reasons.append("registered_source_evidence_host_mismatch")
    observed = _timestamp(details.get("observed_at"))
    if observed is None or not -3600 <= (current - observed).total_seconds() <= 72 * 3600:
        reasons.append("source_evidence_not_recent")
    if score < 0.60 or score > 1.0:
        reasons.append("score_out_of_review_range")

    proposal = {
        "schema_version": SCHEMA,
        "decision": "B2B_REVIEW_PROPOSAL" if not reasons else "HOLD",
        "reasons": sorted(set(reasons)),
        "business_name": company if not reasons else None,
        "niche": niche,
        "score": round(score, 3),
        "source": str(source_id or "")[:120],
        "url": url,
        "identity_ref": lead.get("canonical_business_identity_ref") if not reasons else None,
        "territory_ref": lead.get("source_territory_ref") if not reasons else None,
        "source_rights_ref": lead.get("source_rights_receipt_ref") if not reasons else None,
        "jurisdiction_policy_ref": lead.get("jurisdiction_policy_ref") if not reasons else None,
        "outreach_authorized": False,
        "buyer_intent_verified": False,
        "canonical_prospect_promotion_authorized": False,
        "execution_authority": "none",
    }
    return proposal


class LeadSniperRepository:
    """Use the same canonical gateway already used by IdleAssetRepository."""

    def __init__(self, gateway: CanonicalDataGateway, *, queue_enabled: bool = False):
        self._gateway = gateway
        self._queue_enabled = queue_enabled

    @classmethod
    def from_environment(cls) -> "LeadSniperRepository":
        env = load_runtime_env("/etc/empire_os.env")
        gateway = gateway_from_environment(env)
        approved = (
            os.environ.get("EMPIRE_SNIPER_REVIEW_QUEUE_ENABLE") == "1"
            and os.environ.get("EMPIRE_SNIPER_CANONICAL_WRITES_APPROVED") == "1"
        )
        return cls(gateway, queue_enabled=approved)

    def _require_empiredb(self) -> None:
        if self._gateway.backend is not DataBackend.EMPIREDB:
            raise RuntimeError("canonical_primary_must_be_empiredb")
        if not self._gateway.configured:
            raise RuntimeError("canonical_empiredb_not_configured")

    def pending_review_exists(
        self, url: str, *, dedup_hours: int = 24,
        now: datetime | None = None,
    ) -> bool:
        """Dedup all recent review statuses; fail closed on ambiguous DB reads."""
        self._require_empiredb()
        source = _source_url(url)
        if not source:
            raise ValueError("valid_https_source_url_required")
        if not 1 <= dedup_hours <= MAX_DEDUP_HOURS:
            raise ValueError("invalid_dedup_window")
        current = now or datetime.now(timezone.utc)
        matches = self._gateway.query(
            TASK_TABLE, "id,payload,created_at",
            filters=(
                DataFilter.eq("task_type", TASK_TYPE),
                DataFilter.eq("payload->>url", source),
            ),
            limit=MAX_QUERY_RESULTS,
        )
        if len(matches) >= MAX_QUERY_RESULTS:
            raise RuntimeError("duplicate_task_rows_need_manual_reconciliation")
        cutoff = current - timedelta(hours=dedup_hours)
        for row in matches:
            payload = row.get("payload")
            if not isinstance(payload, Mapping) or payload.get("url") != source:
                raise RuntimeError("canonical_sniper_dedup_evidence_inconsistent")
            created = _timestamp(row.get("created_at"))
            if created is None or created > current + timedelta(minutes=5):
                raise RuntimeError("canonical_sniper_dedup_timestamp_missing")
            if created >= cutoff:
                return True
        return False

    def queue_review(
        self, proposal: Mapping[str, Any],
        *, now: datetime | None = None,
    ) -> dict[str, Any]:
        """Optional canonical insertion; never activates anything downstream."""
        self._require_empiredb()
        if proposal.get("decision") != "B2B_REVIEW_PROPOSAL":
            return {"ok": False, "status": "held", "reason": "b2b_evidence_hold"}
        if not self._queue_enabled:
            return {"ok": False, "status": "held", "reason": "canonical_review_queue_not_activated"}
        url = _source_url(proposal.get("url"))
        if not url or not _evidence_reference(proposal.get("identity_ref")):
            return {"ok": False, "status": "held", "reason": "invalid_source_or_identity"}
        if self.pending_review_exists(url, now=now):
            return {"ok": True, "status": "deduped", "canonical_write_performed": False}
        current = now or datetime.now(timezone.utc)
        row = {
            "task_type": TASK_TYPE,
            "status": "pending",
            "payload": {
                "schema_version": SCHEMA,
                "review_state": "B2B_RESEARCH_ONLY",
                "niche": proposal["niche"],
                "source": proposal["source"],
                "url": url,
                "business_name": proposal["business_name"],
                "score": proposal["score"],
                "identity_ref": proposal["identity_ref"],
                "source_rights_ref": proposal["source_rights_ref"],
                "territory_ref": proposal["territory_ref"],
                "jurisdiction_policy_ref": proposal.get("jurisdiction_policy_ref"),
                "queued_at": current.isoformat(),
                "outbound_authorized": False,
                "canonical_prospect_promotion_authorized": False,
            },
        }
        self._gateway.insert(TASK_TABLE, row, return_repr=False)
        # This is not an atomic singleton transaction/unique constraint;
        # readback is mandatory before claiming any success.
        if not self.pending_review_exists(url, now=current):
            raise RuntimeError("canonical_review_write_not_confirmed")
        return {"ok": True, "status": "review_queued", "canonical_write_performed": True}
