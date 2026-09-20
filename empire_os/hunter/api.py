"""OBSERVE-only internal API for Empire Hunter."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field

from empire_os.hunter.domain_intelligence import analyze_domain
from empire_os.hunter.models import ContactEvidence, VerificationState
from empire_os.hunter.outcome_learning import (
    calibrate_contact,
    calibrate_pattern_outcomes,
)
from empire_os.hunter.pattern_brain import learn_domain_pattern
from empire_os.hunter.prioritization import prioritize_enrichment
from empire_os.hunter.signals import derive_temporal_signals
from empire_os.hunter.verification_mesh import VerificationMesh


class VerifyRequest(BaseModel):
    email: str
    source: str
    source_url: str | None = None
    person_name: str | None = None
    person_title: str | None = None
    person_bound: bool = False
    first_party: bool = False
    delivered_evidence: bool = False
    bounced_evidence: bool = False


class PatternRequest(BaseModel):
    domain: str
    observations: list[dict[str, Any]] = Field(default_factory=list)


class ContactCalibrationRequest(BaseModel):
    contact: dict[str, Any]
    observations: list[dict[str, Any]] = Field(default_factory=list)


class PatternCalibrationRequest(BaseModel):
    domain: str
    observations: list[dict[str, Any]] = Field(default_factory=list)


class EnrichmentPriorityRequest(BaseModel):
    entity_id: str
    evidence_confidence: float = Field(ge=0, le=1)
    omega_score: float | None = Field(default=None, ge=0, le=100)
    omega_confidence: float | None = Field(default=None, ge=0, le=1)
    buyer_demand_strength: float | None = Field(default=None, ge=0, le=1)
    buyer_demand_confidence: float | None = Field(default=None, ge=0, le=1)
    contact_ready: bool = False
    modeled_expected_gp_cents: int | None = Field(default=None, ge=0)
    enrichment_cost_cents: int | None = Field(default=None, ge=0)
    evidence_refs: list[str] = Field(min_length=1)


class TemporalSignalsRequest(BaseModel):
    entity_id: str
    observed_at: str
    previous: dict[str, Any] | None = None
    current: dict[str, Any]
    evidence_refs: list[str] = Field(min_length=1)


class DomainAnalyseRequest(BaseModel):
    website: str
    max_pages: int = Field(default=5, ge=1, le=12)
    request_timeout: float = Field(default=5.0, gt=0, le=15)
    time_budget_seconds: float = Field(default=25.0, gt=0, le=90)


def _contact_from_dict(row: dict[str, Any]) -> ContactEvidence:
    data = dict(row)
    try:
        data["state"] = VerificationState(
            str(data.get("state") or "unknown")
        )
        return ContactEvidence(**data)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid contact evidence: {exc}") from exc


def create_hunter_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/hunter",
        tags=["empire-hunter"],
    )

    @router.get("/health")
    def health():
        return {
            "product": "Empire Hunter",
            "mode": "OBSERVE",
            "third_party_contact_data": False,
            "external_verifier_required": False,
            "outbound_execution": False,
            "payment_execution": False,
            "revenue_mutation": False,
            "api_contract_version": "hunter-v1",
        }

    @router.post("/verify/preview")
    def verify_preview(req: VerifyRequest):
        result = VerificationMesh().verify(
            req.email,
            source=req.source,
            source_url=req.source_url,
            person_name=req.person_name,
            person_title=req.person_title,
            person_bound=req.person_bound,
            first_party=req.first_party,
            delivered_evidence=req.delivered_evidence,
            bounced_evidence=req.bounced_evidence,
        )
        return {
            "mode": "OBSERVE",
            "execution_allowed": False,
            "contact": result.as_dict(),
        }

    @router.post("/pattern/preview")
    def pattern_preview(req: PatternRequest):
        try:
            pattern = learn_domain_pattern(
                req.observations,
                domain=req.domain,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "execution_allowed": False,
            "pattern": pattern.as_dict(),
        }

    @router.post("/outcomes/contact/preview")
    def contact_outcome_preview(req: ContactCalibrationRequest):
        try:
            contact = _contact_from_dict(req.contact)
            result = calibrate_contact(
                contact,
                req.observations,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "execution_allowed": False,
            "calibration": result.as_dict(),
        }

    @router.post("/outcomes/pattern/preview")
    def pattern_outcome_preview(req: PatternCalibrationRequest):
        result = calibrate_pattern_outcomes(
            req.observations,
            domain=req.domain,
        )
        return {
            "mode": "OBSERVE",
            "execution_allowed": False,
            "calibration": result.as_dict(),
        }

    @router.post("/prioritize/preview")
    def prioritize_preview(req: EnrichmentPriorityRequest):
        try:
            result = prioritize_enrichment(
                entity_id=req.entity_id,
                evidence_confidence=req.evidence_confidence,
                omega_score=req.omega_score,
                omega_confidence=req.omega_confidence,
                buyer_demand_strength=req.buyer_demand_strength,
                buyer_demand_confidence=req.buyer_demand_confidence,
                contact_ready=req.contact_ready,
                modeled_expected_gp_cents=req.modeled_expected_gp_cents,
                enrichment_cost_cents=req.enrichment_cost_cents,
                evidence_refs=req.evidence_refs,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "execution_allowed": False,
            "priority": result.as_dict(),
        }

    @router.post("/signals/preview")
    def signals_preview(req: TemporalSignalsRequest):
        try:
            signals = derive_temporal_signals(
                entity_id=req.entity_id,
                observed_at=req.observed_at,
                previous=req.previous,
                current=req.current,
                evidence_refs=req.evidence_refs,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "execution_allowed": False,
            "signals": [signal.as_dict() for signal in signals],
        }

    @router.post("/domain/analyse")
    def domain_analyse(req: DomainAnalyseRequest):
        try:
            report = analyze_domain(
                req.website,
                max_pages=req.max_pages,
                request_timeout=req.request_timeout,
                time_budget_seconds=req.time_budget_seconds,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"hunter_domain_probe_failed:{type(exc).__name__}",
            ) from exc
        return {
            "mode": "OBSERVE",
            "execution_allowed": False,
            "report": report.as_dict(),
        }

    return router


router = create_hunter_router()

app = FastAPI(
    title="Empire Hunter",
    version="1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(router)
