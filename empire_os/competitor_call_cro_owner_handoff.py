"""CRO evidence bridge for the ORIGINAL Conversion Intelligence specialist.

Static first-party roofing source review + verified existing attribution
readiness. This NEVER claims live browser behaviour or conversion results.
No duplicated CRO agent, no website/SEO changes, no behavioural surveillance.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from empire_os.conversion_intelligence import (
    CANONICAL_STAGES,
    ConversionStageEvidence,
    review_conversion_system,
)

SCHEMA = "empire.competitor_call_cro_owner_handoff.v1"
ATTRIBUTION_SCHEMA = "empire.competitor_call_conversion_readiness.v1"
ATTRIBUTION = Path("runtime/competitive_intelligence/call_conversion_readiness_latest.json")
PAGE = Path("apps/empire-public-site/src/app/roofing/page.tsx")
FORM = Path("apps/empire-public-site/src/app/roofing/coverage-check.tsx")
DEST = Path("runtime/competitive_intelligence/call_cro_owner_handoff_latest.json")

def _guard(readiness: Mapping[str, Any]) -> None:
    if (not isinstance(readiness, Mapping)
            or readiness.get("schema_version") != ATTRIBUTION_SCHEMA
            or readiness.get("mode") != "OBSERVE"
            or readiness.get("exact_source_to_settlement_proven") is not False
            or readiness.get("acquisition_source_profitability_calibrated") is not False
            or readiness.get("ad_spend_authorized") is not False
            or readiness.get("content_publication_authorized") is not False
            or readiness.get("external_send_authorized") is not False
            or readiness.get("database_writes") is not False
            or readiness.get("execution_authority") != "none"):
        raise ValueError("untrusted traffic-to-settlement evidence authority")
    steps = readiness.get("measurement_chain_steps")
    if (not isinstance(steps, list) or len(steps) != 6
            or any(not isinstance(x, Mapping) or x.get("verified") is not False
                   or x.get("count") is not None for x in steps)):
        raise ValueError("missing unverified source-to-cash stage contract")

def build_cro_owner_handoff(
    *, readiness: Mapping[str, Any], page_source: str | None,
    form_source: str | None, now: datetime | None = None,
) -> dict:
    _guard(readiness)
    at = now or datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ValueError("offset-aware review time required")
    at = at.astimezone(timezone.utc)

    # Reuse the original Conversion Intelligence capability, not an invented
    # second scoring engine. No cohorts/call lineage means NULL on every
    # stage. Never use "GSC page rows" as visitors or ZIP entries as leads.
    existing = review_conversion_system([
        ConversionStageEvidence(
            stage=stage, entered=None, converted=None, evidence_ref=None
        ) for stage in CANONICAL_STAGES
    ], min_sample_size=20).as_dict()

    page_found = isinstance(page_source, str) and 0 < len(page_source) < 200000
    form_found = isinstance(form_source, str) and 0 < len(form_source) < 100000
    banner_off = page_found and "Review only · Traffic disabled" in page_source
    cta = page_found and "Check ZIP &amp; request a roofing call" in page_source
    faq_disabled = page_found and "Calls are not currently enabled on this preview." in page_source
    has_zip_form = form_found and 'onSubmit={checkZip}' in form_source
    has_inline_feedback = form_found and 'aria-live="polite"' in form_source
    handoff_conditional = form_found and 'result.kind === "covered" && result.callReady' in form_source
    has_expiry_guard = form_found and "validPreview(data)" in form_source
    has_first_party_emitter = form_found and any(token in form_source for token in (
        "trackEvent(", "analytics.track(", "gtag(", "plausible(", "captureEvent(",
    ))
    tasks = [
        {
            "rank": 1, "owner": "ORIGINAL_WEBSITE_AND_CONVERSION_OWNER",
            "hypothesis": "REVIEW_DISABLED_TRAFFIC_VS_REQUEST_A_CALL_CTA_COPY",
            "source_signal_observed": bool(banner_off and cta and faq_disabled),
            "interpretation": "Static source messages conflict in expectations; not proof that the live deployed page is the same",
            "next_evidence": "Existing owner confirms candidate/live version and reviews truthful traffic-state wording",
            "experiment_or_publish_authority": "none",
        },
        {
            "rank": 2, "owner": "ORIGINAL_WEBSITE_SESSION_COLLECTOR_OWNER",
            "hypothesis": "MEASURE_CTA_TO_ZIP_CHECK_DROPOFF",
            "source_signal_observed": bool(page_found and cta and has_zip_form),
            "interpretation": "The hero CTA and ZIP form exist in source; actual impressions, clicks and responses are unknown",
            "next_evidence": "Privacy-respecting same-session page arrival, CTA choice, ZIP response and errors; no raw IP or customer-data export",
            "experiment_or_publish_authority": "none",
        },
        {
            "rank": 3, "owner": "ORIGINAL_LEAD_SMART_COMMERCIAL_OWNER",
            "hypothesis": "VERIFY_ZIP_GUIDANCE_TO_ELIGIBLE_CALL_CHOICE",
            "source_signal_observed": bool(has_zip_form and handoff_conditional and has_expiry_guard),
            "interpretation": "Source gates call option on authoritative ZIP response and call readiness; no measured connected-call proof",
            "next_evidence": "Joined first-party accepted ZIP/call-choice aggregate plus protected buyer/Ringba lineage from original owner",
            "experiment_or_publish_authority": "none",
        },
        {
            "rank": 4, "owner": "ORIGINAL_CRO_AND_ACCESSIBILITY_OWNER",
            "hypothesis": "AUDIT_MOBILE_FORM_FRICTION_AND_ERROR_COHORT",
            "source_signal_observed": bool(form_found and has_inline_feedback),
            "interpretation": "Accessible status feedback appears in source; no recordings, usability proof or measured abandonment",
            "next_evidence": "Consent-reviewed aggregate form errors, device grouping, accessibility checks; no session recording by default",
            "experiment_or_publish_authority": "none",
        },
        {
            "rank": 5, "owner": "ORIGINAL_MEDIA_FINANCE_AND_CRO_OWNERS",
            "hypothesis": "TEST_FIRST_PARTY_SOURCE_CONVERSION_AFTER_PROOF",
            "source_signal_observed": readiness.get("source_registry_available") is True,
            "interpretation": "Traffic channels are research candidates; absent paid/source-to-settlement rates prohibit uplift claims",
            "next_evidence": "Same-cohort by-channel arrivals, eligible call choices, accepted payable calls, settlement and actual acquisition expense",
            "experiment_or_publish_authority": "none",
        },
    ]
    return {
        "schema_version": SCHEMA, "mode": "OBSERVE",
        "generated_at": at.isoformat(),
        "original_specialist_module": "empire_os.conversion_intelligence",
        "existing_specialist_reused": True,
        "original_specialist_stage_count": len(existing["stages"]),
        "original_specialist_primary_bottleneck": existing["primary_bottleneck"],
        "original_specialist_experiment_candidate": existing["experiment_candidate"],
        "original_specialist_unknown_stage_count": len(existing["unknown_stages"]),
        "existing_stage_review": existing,
        "static_candidate_source_review": {
            "source_path": str(PAGE),
            "form_path": str(FORM),
            "source_available": page_found and form_found,
            "not_live_deployment_attestation": True,
            "traffic_disabled_banner_in_source": bool(banner_off),
            "hero_call_request_cta_in_source": bool(cta),
            "calls_disabled_faq_in_source": bool(faq_disabled),
            "form_validation_in_source": bool(has_zip_form and has_expiry_guard),
            "accessible_feedback_in_source": bool(has_inline_feedback),
            "call_handoff_conditional_in_source": bool(handoff_conditional),
            "visible_client_form_tracking_emitter_in_source": bool(has_first_party_emitter),
            "absence_of_visible_emitter_is_not_proof_of_absent_server_analytics": True,
        },
        "source_to_paid_call_calibrated": False,
        "measured_conversion_bottleneck_established": False,
        "automated_experiment_approved": False,
        "proposed_cro_reviews": tasks,
        "site_changed": False, "paid_media_activated": False,
        "buyer_route_changed": False,
        "new_agent_or_scheduler_created": False,
        "consumer_records_exported": False,
        "execution_authority": "none",
    }

def refresh(root: Path) -> dict:
    path = root / ATTRIBUTION
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 150000:
        raise ValueError("original readiness record unavailable")
    readiness = json.loads(path.read_text(encoding="utf-8"))
    def source(file: Path) -> str | None:
        src = root / file
        try:
            if src.is_symlink() or not src.is_file() or src.stat().st_size > 200000:
                return None
            return src.read_text(encoding="utf-8")
        except (OSError, ValueError, UnicodeError):
            return None
    result = build_cro_owner_handoff(
        readiness=readiness, page_source=source(PAGE), form_source=source(FORM)
    )
    target = root / DEST
    if not target.parent.is_dir() or target.parent.is_symlink() or target.is_symlink():
        raise ValueError("unsafe existing competitive intelligence runtime")
    fd, tmp = tempfile.mkstemp(prefix=".cro-owner-handoff-", dir=target.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as writer:
            json.dump(result, writer, indent=2, sort_keys=True)
            writer.write("\n")
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return result
