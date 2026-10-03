"""Bounded health interpretation for open-source deliverability evidence."""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.outbound_open_source_evidence import (
    normalize_checkdmarc_result,
    normalize_dnscontrol_preview,
    summarize_parsedmarc_aggregate,
)


def evaluate_open_source_evidence(
    bundle: Mapping[str, Any],
    *,
    min_dmarc_messages: int = 20,
    dmarc_warn_rate: float = 0.98,
    dmarc_hold_rate: float = 0.90,
) -> dict[str, Any]:
    payload = dict(bundle or {})
    evidence: dict[str, Any] = {}
    hard_holds: list[str] = []
    warnings: list[str] = []

    checkdmarc_payload = payload.get("checkdmarc")
    if isinstance(checkdmarc_payload, Mapping):
        auth = normalize_checkdmarc_result(checkdmarc_payload)
        evidence["checkdmarc"] = auth
        if auth["spf_valid"] is False:
            hard_holds.append("spf_record_invalid")
        if auth["dmarc_valid"] is False:
            hard_holds.append("dmarc_record_invalid")
        if auth["warning_count"]:
            warnings.append("authentication_observer_warnings")

    parsedmarc_payload = payload.get("parsedmarc")
    if isinstance(parsedmarc_payload, Mapping):
        aggregate = summarize_parsedmarc_aggregate(parsedmarc_payload)
        evidence["parsedmarc"] = aggregate
        messages = int(aggregate["messages"])
        pass_rate = float(aggregate["dmarc_pass_rate"])
        if messages >= min_dmarc_messages:
            if pass_rate < dmarc_hold_rate:
                hard_holds.append("dmarc_alignment_rate_critical")
            elif pass_rate < dmarc_warn_rate:
                warnings.append("dmarc_alignment_rate_degraded")

    dns_preview = payload.get("dnscontrol_preview")
    if isinstance(dns_preview, list):
        dns = normalize_dnscontrol_preview(dns_preview)
        evidence["dnscontrol_preview"] = dns
        if dns["posture"] == "APPROVAL_REQUIRED":
            warnings.append("dns_destructive_change_requires_approval")
        elif dns["posture"] == "DRIFT":
            warnings.append("dns_desired_state_drift")

    if hard_holds:
        posture = "HOLD"
    elif warnings:
        posture = "REMEDIATE"
    elif evidence:
        posture = "GREEN"
    else:
        posture = "UNKNOWN"

    return {
        "posture": posture,
        "hard_holds": hard_holds,
        "warnings": warnings,
        "evidence": evidence,
        "mutation_authorized": False,
    }
