"""Evidence-first trust readiness for EmpireOS.

The internal score is operational guidance only. Public trust surfaces expose
verified evidence, never a self-awarded vanity rating.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

WEIGHTS = {
    "identity_transparency": 15,
    "domain_email_authentication": 10,
    "security_privacy": 15,
    "commercial_terms_clarity": 10,
    "agreement_integrity": 10,
    "payment_verification": 10,
    "delivery_outcomes": 15,
    "customer_references": 10,
    "incident_response": 5,
}

@dataclass(frozen=True)
class TrustEvidence:
    key: str
    state: str
    evidence_refs: tuple[str, ...] = ()
    note: str | None = None

    def validate(self) -> None:
        if self.key not in WEIGHTS:
            raise ValueError(f"unsupported trust dimension: {self.key}")
        if self.state not in {"verified", "partial", "failed", "unknown"}:
            raise ValueError(f"unsupported trust state: {self.state}")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

def assess_trust_readiness(
    evidence: Mapping[str, TrustEvidence],
) -> dict[str, Any]:
    verified_weight = 0
    observed_weight = 0
    blockers: list[str] = []
    unknown: list[str] = []
    dimensions: list[dict[str, Any]] = []

    for key, weight in WEIGHTS.items():
        item = evidence.get(key) or TrustEvidence(key=key, state="unknown")
        item.validate()
        refs = tuple(ref for ref in item.evidence_refs if str(ref).strip())

        if item.state != "unknown":
            observed_weight += weight
        if item.state == "verified":
            verified_weight += weight
            if not refs:
                blockers.append(f"{key}:verified_without_evidence")
        elif item.state == "partial":
            verified_weight += weight * 0.5
            if not refs:
                blockers.append(f"{key}:partial_without_evidence")
        elif item.state == "failed":
            blockers.append(f"{key}:failed")
        else:
            unknown.append(key)

        dimensions.append({
            "key": key,
            "weight": weight,
            "state": item.state,
            "evidence_refs": list(refs),
            "note": item.note,
        })

    score = round(verified_weight, 2)
    coverage = round(observed_weight / 100.0, 4)
    public_ready = (
        coverage >= 0.75
        and not blockers
        and evidence.get("identity_transparency", TrustEvidence(
            "identity_transparency", "unknown"
        )).state == "verified"
        and evidence.get("security_privacy", TrustEvidence(
            "security_privacy", "unknown"
        )).state == "verified"
    )

    return {
        "schema_version": "empire.trust_readiness.v1",
        "mode": "OBSERVE",
        "internal_score": score,
        "evidence_coverage": coverage,
        "public_score_allowed": False,
        "public_trust_center_ready": public_ready,
        "dimensions": dimensions,
        "unknown_dimensions": unknown,
        "blockers": sorted(set(blockers)),
        "execution_authority": "none",
    }

def build_public_trust_manifest(
    assessment: Mapping[str, Any],
) -> dict[str, Any]:
    verified = []
    for row in assessment.get("dimensions") or []:
        if (
            isinstance(row, Mapping)
            and row.get("state") == "verified"
            and row.get("evidence_refs")
        ):
            verified.append({
                "key": row.get("key"),
                "evidence_refs": list(row.get("evidence_refs") or []),
                "note": row.get("note"),
            })

    return {
        "schema_version": "empire.public_trust_manifest.v1",
        "verified_claims": verified,
        "self_awarded_score": None,
        "trust_center_ready": bool(
            assessment.get("public_trust_center_ready")
        ),
        "unknowns_hidden": False,
        "fabricated_social_proof": False,
    }
