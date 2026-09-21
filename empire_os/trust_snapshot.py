"""Evidence-first Trust Center snapshot builder for Founder operations."""
from __future__ import annotations

from typing import Any, Mapping

from empire_os.trust_readiness import (
    TrustEvidence,
    assess_trust_readiness,
    build_public_trust_manifest,
)


def _count(mapping: Mapping[str, Any], key: str) -> int:
    try:
        return int(mapping.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _stage_observed(loop: Mapping[str, Any], *names: str) -> bool:
    for row in loop.get("stages") or []:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("stage") or "") in names and row.get("observed") is True:
            return True
    return False


def build_trust_snapshot(
    *,
    ops_control: Mapping[str, Any],
    security_audit: Mapping[str, Any],
    commercial_loop: Mapping[str, Any],
    public_domain: str = "empire-ai.co.uk",
) -> dict[str, Any]:
    findings = security_audit.get("findings")
    findings = findings if isinstance(findings, Mapping) else {}
    security_errors = (
        _count(findings, "rls_disabled_in_public")
        + _count(findings, "security_definer_view")
    )
    security_state = (
        "failed" if security_errors > 0
        else "verified" if security_audit else "unknown"
    )
    ops_healthy = ops_control.get("healthy") is True
    ops_observed = bool(str(ops_control.get("observed_at") or "").strip())

    evidence = {
        "identity_transparency": TrustEvidence(
            key="identity_transparency",
            state="partial",
            evidence_refs=(f"https://{public_domain}",),
            note="Public domain is live; fuller legal identity evidence is separate.",
        ),
        "domain_email_authentication": TrustEvidence(
            key="domain_email_authentication",
            state="unknown",
            note="Canonical SPF/DKIM/DMARC evidence is not bound into this snapshot yet.",
        ),
        "security_privacy": TrustEvidence(
            key="security_privacy",
            state=security_state,
            evidence_refs=(
                "runtime/security/supabase_audit_latest.json",
            ) if security_audit else (),
            note=(
                "Current Supabase audit has unresolved ERROR-level findings."
                if security_errors > 0 else None
            ),
        ),
        "commercial_terms_clarity": TrustEvidence(
            key="commercial_terms_clarity",
            state=(
                "verified"
                if _stage_observed(commercial_loop, "commercial_terms")
                else "unknown"
            ),
            evidence_refs=(
                "canonical:buyers:commercial_terms",
            ) if _stage_observed(commercial_loop, "commercial_terms") else (),
        ),
        "agreement_integrity": TrustEvidence(
            key="agreement_integrity",
            state="unknown",
            note="Canonical e-signature/agreement bridge is not activated yet.",
        ),
        "payment_verification": TrustEvidence(
            key="payment_verification",
            state=(
                "verified"
                if _stage_observed(commercial_loop, "bsc_usdt_payment")
                else "unknown"
            ),
            evidence_refs=(
                "canonical:bsc_payment_evidence",
            ) if _stage_observed(commercial_loop, "bsc_usdt_payment") else (),
        ),
        "delivery_outcomes": TrustEvidence(
            key="delivery_outcomes",
            state=(
                "verified"
                if _stage_observed(commercial_loop, "fulfilment")
                else "unknown"
            ),
            evidence_refs=(
                "canonical:fulfilment_orders:delivery",
            ) if _stage_observed(commercial_loop, "fulfilment") else (),
        ),
        "customer_references": TrustEvidence(
            key="customer_references",
            state="unknown",
            note="No verified customer-reference evidence is asserted.",
        ),
        "incident_response": TrustEvidence(
            key="incident_response",
            state="verified" if ops_healthy and ops_observed else "unknown",
            evidence_refs=(
                "runtime/ops_control/latest.json",
            ) if ops_healthy and ops_observed else (),
        ),
    }
    assessment = assess_trust_readiness(evidence)
    return {
        "schema_version": "empire.trust_snapshot.v1",
        "assessment": assessment,
        "public_manifest": build_public_trust_manifest(assessment),
        "security_findings": dict(findings),
        "execution_authority": "none",
        "publishing_authority": False,
    }
