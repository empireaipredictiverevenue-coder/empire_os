"""Bounded read-only API contract for the canonical Revenue CRM."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field, ConfigDict

from empire_os.revenue_crm_transport import (
    PostgresRevenueCrmRepository, RevenueCrmTransportError,
)
from empire_os.revenue_crm_customer_success import (
    route_customer_success_review,
)
from empire_os.revenue_crm_search_growth import build_crm_search_growth_brief
from empire_os.revenue_crm_journeys import (
    journey_blueprint, preview_crm_journey, preview_segment_distribution,
)
from empire_os.revenue_crm_channel_evidence import (
    ChannelEvidenceError, TrustedChannelEvidence, review_channel_evidence,
)
from empire_os.revenue_crm_designs import UnsafeJourneyDesign
from empire_os.revenue_crm_design_store import (
    JourneyStorageUnavailable, PostgresCrmJourneyDesignStore,
)
from empire_os.search_intelligence.ai_visibility import AiCitationObservation
from empire_os.search_intelligence.backlinks import BacklinkObservation
from empire_os.revenue_crm_readiness import assess_close_readiness
from empire_os.revenue_crm_reply_qualification import review_crm_reply_qualification
from empire_os.workspace_solar_crm_tenant_prospect_match import (
    TenantProspectMatchHeld, preview_six_tenant_prospect_name_matches,
)
from empire_os.opportunity_commercial_source_health import assess_sources
from empire_os.revenue_crm_retention import (
    RevenueCrmRetentionEvidence,
    assess_retention_expansion_readiness,
)
from empire_os.revenue_crm_retention_freshness import (
    RevenueCrmRetentionTiming,
    assess_retention_expansion_freshness,
)


class RevenueCrmRepository(Protocol):
    def prospects(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def buyers(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        ...

    def prospect(self, prospect_id: str) -> Mapping[str, Any] | None:
        ...


@dataclass(frozen=True)
class AuthenticatedRevenueCrmRead:
    """Server-authenticated, tenant-bound repository handoff.

    Never construct this from client-supplied tenant IDs or headers. The caller
    must independently verify request authentication and choose a dedicated
    PostgreSQL login whose session_user is bound to the same tenant.
    """
    tenant_id: str
    repository: PostgresRevenueCrmRepository


def build_authenticated_revenue_crm_resolver(
    authenticate_tenant: Callable[[Request], str | None],
    dedicated_tenant_dsns: Mapping[str, str],
    *,
    connect_factory: Callable | None = None,
) -> Callable[[Request], AuthenticatedRevenueCrmRead | None]:
    """Existing CRM's opt-in integration for verified, per-tenant DB logins.

    authenticate_tenant MUST independently authenticate the HTTP principal
    through a trusted server-side mechanism. Do not use client tenant headers,
    query strings, or unverified session claims as this callback's result.
    Every DSN must authenticate as a distinct, dedicated, tenant-bound LOGIN.
    Configuration does not grant DB roles or activate the HTTP router.
    """
    if not callable(authenticate_tenant):
        raise ValueError("authenticated CRM principal resolver required")
    credentials: dict[str, str] = {}
    seen_dsns: set[str] = set()
    for raw_tenant, raw_dsn in dedicated_tenant_dsns.items():
        try:
            tenant = str(UUID(str(raw_tenant)))
        except (TypeError, ValueError, AttributeError):
            raise ValueError("canonical CRM tenant configuration required") from None
        if tenant in credentials:
            raise ValueError("duplicate canonical CRM tenant configuration")
        if not isinstance(raw_dsn, str) or not raw_dsn.strip():
            raise ValueError("dedicated CRM tenant connection required")
        dsn = raw_dsn.strip()
        if dsn in seen_dsns:
            raise ValueError("shared CRM database connection is prohibited")
        credentials[tenant] = dsn
        seen_dsns.add(dsn)
    if not credentials:
        raise ValueError("no dedicated CRM tenant connections configured")

    def resolve(request: Request) -> AuthenticatedRevenueCrmRead | None:
        verified_tenant = authenticate_tenant(request)
        if verified_tenant is None:
            return None
        try:
            tenant = str(UUID(str(verified_tenant)))
        except (TypeError, ValueError, AttributeError):
            raise RevenueCrmTransportError("authenticated CRM scope invalid") from None
        dsn = credentials.get(tenant)
        if not dsn:
            raise RevenueCrmTransportError("authenticated CRM tenant not provisioned")
        return AuthenticatedRevenueCrmRead(
            tenant_id=tenant,
            repository=PostgresRevenueCrmRepository(
                dsn, tenant_id=tenant, connect_factory=connect_factory,
            ),
        )

    return resolve


class RevenueCrmRetentionRequest(BaseModel):
    buyer_id: str
    buyer_activated: bool
    buyer_evidence_ref: str | None = None
    payment_verified: bool
    payment_evidence_ref: str | None = None
    fulfilment_delivered: bool
    fulfilment_evidence_ref: str | None = None
    outcome_observed: bool
    outcome_success_verified: bool | None = None
    outcome_evidence_ref: str | None = None
    buyer_available_capacity: int | None = Field(default=None, ge=0)
    capacity_evidence_ref: str | None = None


class RevenueCrmBacklinkObservationRequest(BaseModel):
    source_url: str
    target_url: str
    observed_at: str
    anchor_text: str | None = None
    rel: str | None = None
    source: str = "observed_backlink"
    provenance: list[str] = Field(min_length=1)


class RevenueCrmCitationObservationRequest(BaseModel):
    query: str
    engine: str
    observed_at: str
    cited_url: str
    source_url: str | None = None
    citation_position: int | None = Field(default=None, ge=1)
    mention_text: str | None = None
    provenance: list[str] = Field(min_length=1)


class RevenueCrmSearchGrowthRequest(BaseModel):
    prospect_id: str
    domain: str
    query: str
    engine: str
    competitor_domains: list[str] = Field(default_factory=list)
    backlinks: list[RevenueCrmBacklinkObservationRequest] = Field(default_factory=list)
    citations: list[RevenueCrmCitationObservationRequest] = Field(default_factory=list)


class RevenueCrmRetentionFreshnessRequest(RevenueCrmRetentionRequest):
    buyer_observed_at: str
    payment_observed_at: str | None = None
    fulfilment_observed_at: str | None = None
    outcome_observed_at: str | None = None
    capacity_observed_at: str | None = None
    now_utc: str
    max_age_seconds: int = Field(default=86400, gt=0)


@dataclass(frozen=True)
class EvidenceRef:
    kind: str
    record_id: str
    state: str | None
    observed_at: str | None
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NextActionEvidence:
    available: bool
    action: str | None
    reason: str
    evidence: tuple[EvidenceRef, ...]
    execution_authority: str = "none"
    approval_required: bool = True

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [item.as_dict() for item in self.evidence]
        return data


def _canonical_ref(
    *,
    kind: str,
    record_id: Any,
    state: Any,
    observed_at: Any,
    detail: str | None = None,
) -> EvidenceRef | None:
    rid = str(record_id or "").strip()
    if not rid:
        return None
    state_text = str(state or "").strip() or None
    observed_text = str(observed_at or "").strip() or None
    return EvidenceRef(
        kind=kind,
        record_id=rid,
        state=state_text,
        observed_at=observed_text,
        detail=detail,
    )


def derive_next_action(
    prospect: Mapping[str, Any],
) -> NextActionEvidence:
    closer_state = str(
        prospect.get("closer_state") or ""
    ).strip().lower()
    conversation_state = str(
        prospect.get("conversation_state") or ""
    ).strip().lower()
    fulfilment_state = str(
        prospect.get("fulfilment_state") or ""
    ).strip().lower()

    closer_ref = _canonical_ref(
        kind="closer_case",
        record_id=prospect.get("closer_case_id"),
        state=prospect.get("closer_state"),
        observed_at=prospect.get("closer_updated_at"),
    )
    conversation_ref = _canonical_ref(
        kind="conversation",
        record_id=prospect.get("conversation_id"),
        state=prospect.get("conversation_state"),
        observed_at=prospect.get("conversation_updated_at"),
    )
    fulfilment_ref = _canonical_ref(
        kind="fulfilment_order",
        record_id=prospect.get("fulfilment_order_id"),
        state=prospect.get("fulfilment_state"),
        observed_at=prospect.get("fulfilment_updated_at"),
    )

    if closer_state == "awaiting_payment" and closer_ref is not None:
        return NextActionEvidence(
            available=True,
            action="review_payment_status",
            reason="closer_case_is_waiting_on_payment",
            evidence=(closer_ref,),
        )

    if closer_state == "proposal_ready" and closer_ref is not None:
        return NextActionEvidence(
            available=True,
            action="review_proposal_readiness",
            reason="closer_case_has_observed_proposal_ready_state",
            evidence=(closer_ref,),
        )

    if conversation_state == "engaged" and conversation_ref is not None:
        return NextActionEvidence(
            available=True,
            action="review_engaged_conversation",
            reason="canonical_conversation_is_engaged",
            evidence=(conversation_ref,),
        )

    if (
        fulfilment_state
        in {"accepted", "invoiced", "delivered", "confirmed"}
        and fulfilment_ref is not None
    ):
        return NextActionEvidence(
            available=True,
            action="review_fulfilment_state",
            reason="canonical_fulfilment_requires_operator_review",
            evidence=(fulfilment_ref,),
        )

    buyer_id = str(prospect.get("buyer_id") or "").strip()
    buyer_activation = str(
        prospect.get("buyer_activation_state") or ""
    ).strip().lower()
    capacity = prospect.get("buyer_available_capacity")
    capacity_verified_at = str(
        prospect.get("buyer_capacity_verified_at") or ""
    ).strip()
    if (
        buyer_id
        and buyer_activation == "activated"
        and capacity is not None
        and capacity_verified_at
    ):
        capacity_value = int(capacity)
        if capacity_value > 0:
            buyer_ref = EvidenceRef(
                kind="buyer_capacity",
                record_id=buyer_id,
                state=buyer_activation,
                observed_at=capacity_verified_at,
                detail=f"available_capacity:{capacity_value}",
            )
            return NextActionEvidence(
                available=True,
                action="review_buyer_capacity",
                reason="allocated_buyer_has_verified_available_capacity",
                evidence=(buyer_ref,),
            )

    return NextActionEvidence(
        available=False,
        action=None,
        reason="insufficient_observed_evidence",
        evidence=(),
    )


class JourneyDesignDraftRequest(BaseModel):
    # No caller-supplied tenant ID. Reject extra fields, not just ignore them.
    model_config = ConfigDict(extra="forbid")
    design: dict[str, Any]
    design_id: str | None = None
    expected_prior_revision: int | None = Field(default=None, ge=1, le=999999)


def create_revenue_crm_router(
    repository: RevenueCrmRepository | None = None,
    *,
    conversation_read_repository: Any = None,
    evidence_root: Path = Path("/srv/empire_os"),
    resolve_authenticated_read: Callable[[Request], AuthenticatedRevenueCrmRead | None] | None = None,
    resolve_authenticated_design_writer: Callable[[Request], PostgresCrmJourneyDesignStore | None] | None = None,
    resolve_authenticated_channel_evidence: Callable[[Request, str, str], TrustedChannelEvidence | None] | None = None,
) -> APIRouter:
    # A single global Postgres repository is not a multi-tenant HTTP auth
    # boundary. Keep test-only in-memory repositories compatible.
    if isinstance(repository, PostgresRevenueCrmRepository):
        raise ValueError("request-scoped CRM authentication required")
    if repository is not None and resolve_authenticated_read is not None:
        raise ValueError("ambiguous CRM repository authority")
    if (resolve_authenticated_design_writer is not None
            and (resolve_authenticated_read is None or repository is not None)):
        raise ValueError("design storage requires authenticated CRM tenant resolver")
    if (resolve_authenticated_channel_evidence is not None
            and (resolve_authenticated_read is None or repository is not None)):
        raise ValueError("channel evidence requires authenticated CRM tenant resolver")
    router = APIRouter(prefix="/v1/revenue-crm")

    @router.get("/health")
    def health():
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "follow_up_execution": False,
            "payment_execution": False,
            "repository_available": repository is not None,
        }

    def require_repository(request: Request) -> RevenueCrmRepository:
        if resolve_authenticated_read is not None:
            try:
                access = resolve_authenticated_read(request)
            except Exception:
                # Never disclose identity, login, tenant or database details.
                raise HTTPException(
                    status_code=503, detail="authenticated_crm_read_unavailable",
                ) from None
            if access is None:
                raise HTTPException(
                    status_code=401, detail="authenticated_crm_scope_required",
                )
            if (
                not isinstance(access, AuthenticatedRevenueCrmRead)
                or not isinstance(access.repository, PostgresRevenueCrmRepository)
                or access.tenant_id != access.repository.tenant_id
            ):
                raise HTTPException(
                    status_code=503, detail="authenticated_crm_read_unavailable",
                )
            # DB transport separately verifies trusted session_user binding,
            # executes SET LOCAL ROLE and rejects tenant-mismatched rows.
            return access.repository
        if repository is None:
            raise HTTPException(
                status_code=503,
                detail="revenue_crm_repository_not_activated",
            )
        return repository

    def guarded_crm_read(read: Callable[[], Any]) -> Any:
        try:
            return read()
        except RevenueCrmTransportError:
            raise HTTPException(
                status_code=503, detail="authenticated_crm_read_unavailable",
            ) from None

    @router.post("/search-growth/preview")
    def search_growth_preview(req: RevenueCrmSearchGrowthRequest):
        try:
            brief = build_crm_search_growth_brief(
                prospect_id=req.prospect_id,
                domain=req.domain,
                query=req.query,
                engine=req.engine,
                backlinks=tuple(
                    BacklinkObservation(
                        source_url=item.source_url,
                        target_url=item.target_url,
                        observed_at=item.observed_at,
                        anchor_text=item.anchor_text,
                        rel=item.rel,
                        source=item.source,
                        provenance=tuple(item.provenance),
                    )
                    for item in req.backlinks
                ),
                citations=tuple(
                    AiCitationObservation(
                        query=item.query,
                        engine=item.engine,
                        observed_at=item.observed_at,
                        cited_url=item.cited_url,
                        source_url=item.source_url,
                        citation_position=item.citation_position,
                        mention_text=item.mention_text,
                        provenance=tuple(item.provenance),
                    )
                    for item in req.citations
                ),
                competitor_domains=tuple(req.competitor_domains),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "crm_mutation": False,
            "publishing_execution": False,
            "link_building_execution": False,
            "outreach_execution": False,
            "search_products": [
                "authority_intelligence",
                "geo_ai_visibility",
                "competitor_search_gap",
                "search_growth_command",
            ],
            "brief": brief.as_dict(),
        }

    @router.post("/retention-expansion/preview")
    def retention_expansion_preview(req: RevenueCrmRetentionRequest):
        try:
            evidence = RevenueCrmRetentionEvidence(
                buyer_id=req.buyer_id,
                buyer_activated=req.buyer_activated,
                buyer_evidence_ref=req.buyer_evidence_ref,
                payment_verified=req.payment_verified,
                payment_evidence_ref=req.payment_evidence_ref,
                fulfilment_delivered=req.fulfilment_delivered,
                fulfilment_evidence_ref=req.fulfilment_evidence_ref,
                outcome_observed=req.outcome_observed,
                outcome_success_verified=req.outcome_success_verified,
                outcome_evidence_ref=req.outcome_evidence_ref,
                buyer_available_capacity=req.buyer_available_capacity,
                capacity_evidence_ref=req.capacity_evidence_ref,
            )
            readiness = assess_retention_expansion_readiness(evidence)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "follow_up_execution": False,
            "payment_execution": False,
            "crm_mutation": False,
            "offer_mutation": False,
            "readiness": readiness.as_dict(),
        }

    @router.post("/retention-expansion/freshness/preview")
    def retention_expansion_freshness_preview(
        req: RevenueCrmRetentionFreshnessRequest,
    ):
        try:
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            evidence = RevenueCrmRetentionEvidence(
                buyer_id=req.buyer_id,
                buyer_activated=req.buyer_activated,
                buyer_evidence_ref=req.buyer_evidence_ref,
                payment_verified=req.payment_verified,
                payment_evidence_ref=req.payment_evidence_ref,
                fulfilment_delivered=req.fulfilment_delivered,
                fulfilment_evidence_ref=req.fulfilment_evidence_ref,
                outcome_observed=req.outcome_observed,
                outcome_success_verified=req.outcome_success_verified,
                outcome_evidence_ref=req.outcome_evidence_ref,
                buyer_available_capacity=req.buyer_available_capacity,
                capacity_evidence_ref=req.capacity_evidence_ref,
            )
            freshness = assess_retention_expansion_freshness(
                evidence=evidence,
                timing=RevenueCrmRetentionTiming(
                    buyer_observed_at=req.buyer_observed_at,
                    payment_observed_at=req.payment_observed_at,
                    fulfilment_observed_at=req.fulfilment_observed_at,
                    outcome_observed_at=req.outcome_observed_at,
                    capacity_observed_at=req.capacity_observed_at,
                ),
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "follow_up_execution": False,
            "payment_execution": False,
            "crm_mutation": False,
            "offer_mutation": False,
            "freshness": freshness.as_dict(),
        }

    @router.post("/customer-success/preview")
    def customer_success_preview(req: RevenueCrmRetentionFreshnessRequest):
        try:
            normalized = (
                req.now_utc[:-1] + "+00:00"
                if req.now_utc.endswith("Z")
                else req.now_utc
            )
            now = datetime.fromisoformat(normalized)
            if now.tzinfo is None:
                raise ValueError("now_utc must include timezone")
            evidence = RevenueCrmRetentionEvidence(
                buyer_id=req.buyer_id,
                buyer_activated=req.buyer_activated,
                buyer_evidence_ref=req.buyer_evidence_ref,
                payment_verified=req.payment_verified,
                payment_evidence_ref=req.payment_evidence_ref,
                fulfilment_delivered=req.fulfilment_delivered,
                fulfilment_evidence_ref=req.fulfilment_evidence_ref,
                outcome_observed=req.outcome_observed,
                outcome_success_verified=req.outcome_success_verified,
                outcome_evidence_ref=req.outcome_evidence_ref,
                buyer_available_capacity=req.buyer_available_capacity,
                capacity_evidence_ref=req.capacity_evidence_ref,
            )
            freshness = assess_retention_expansion_freshness(
                evidence=evidence,
                timing=RevenueCrmRetentionTiming(
                    buyer_observed_at=req.buyer_observed_at,
                    payment_observed_at=req.payment_observed_at,
                    fulfilment_observed_at=req.fulfilment_observed_at,
                    outcome_observed_at=req.outcome_observed_at,
                    capacity_observed_at=req.capacity_observed_at,
                ),
                now=now,
                max_age_seconds=req.max_age_seconds,
            )
            route = route_customer_success_review(freshness)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "follow_up_execution": False,
            "payment_execution": False,
            "crm_mutation": False,
            "offer_mutation": False,
            "customer_success": route.as_dict(),
        }

    @router.get("/journeys/designer", response_class=HTMLResponse)
    def journey_designer(request: Request):
        # Never serve the designer through the unauthenticated legacy CRM UI.
        # A server-verified tenant read is required even for the static view.
        require_repository(request)
        asset = Path(__file__).resolve().parent / "static" / "revenue_crm_journey_designer.html"
        return HTMLResponse(content=asset.read_text(encoding="utf-8"), headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": (
                "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; "
                "connect-src 'self'; base-uri 'none'; object-src 'none'; "
                "form-action 'none'; frame-ancestors 'none'"
            ),
        })

    @router.get("/journeys/designer.js")
    def journey_designer_javascript(request: Request):
        require_repository(request)
        asset = Path(__file__).resolve().parent / "static" / "revenue_crm_journey_designer.js"
        return Response(content=asset.read_bytes(), media_type="text/javascript", headers={
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
        })

    @router.post("/journeys/designs/drafts", status_code=201)
    def save_journey_design_draft(request: Request, draft: JourneyDesignDraftRequest):
        # Explicit opt-in ONLY: no production resolver, role or table is
        # activated by the existence of this route. Never accept tenant ID
        # from a header/body; require the real dedicated tenant read context.
        repo = require_repository(request)
        if (resolve_authenticated_design_writer is None
                or not isinstance(repo, PostgresRevenueCrmRepository)):
            raise HTTPException(status_code=503, detail="crm_journey_storage_not_activated")
        try:
            writer = resolve_authenticated_design_writer(request)
        except Exception:
            raise HTTPException(status_code=503, detail="crm_journey_storage_not_activated") from None
        if (not isinstance(writer, PostgresCrmJourneyDesignStore)
                or writer.tenant_id != repo.tenant_id):
            raise HTTPException(status_code=503, detail="crm_journey_tenant_writer_unavailable")
        try:
            result = writer.save(
                draft.design, design_id=draft.design_id,
                expected_prior_revision=draft.expected_prior_revision,
            )
        except UnsafeJourneyDesign:
            raise HTTPException(status_code=422, detail="unsafe_journey_design") from None
        except JourneyStorageUnavailable:
            raise HTTPException(status_code=503, detail="crm_journey_storage_not_activated") from None
        return {
            "mode": "DESIGN_ONLY", "tenant_id": result.tenant_id,
            "design_id": result.design_id, "revision": result.revision,
            "sha256": result.sha256, "status": result.result,
            "execution_authority": "none", "send_authorized": False,
            "payment_authorized": False, "workflow_activated": False,
        }

    @router.get("/journeys/blueprint")
    def journeys_blueprint(request: Request):
        # Same repository/auth boundary as tenant CRM views, even though the
        # visual graph is static. No public unauthenticated CRM expansion.
        require_repository(request)
        return journey_blueprint()

    @router.get("/journeys/segments/preview")
    def journeys_segment_preview(
        request: Request, limit: int = Query(default=100, ge=1, le=500),
    ):
        repo = require_repository(request)
        rows = [dict(row) for row in guarded_crm_read(
            lambda: repo.prospects(limit=limit)
        )]
        # A real tenant reader carries the authenticated tenant scope. The
        # test-memory repository is also required to declare one explicitly.
        tenant = getattr(repo, "tenant_id", None)
        if not isinstance(tenant, str) or not tenant.strip():
            raise HTTPException(status_code=503, detail="crm_tenant_scope_unavailable")
        try:
            return preview_segment_distribution(
                rows, tenant_id=tenant, requested_limit=limit,
            )
        except ValueError:
            raise HTTPException(status_code=503, detail="crm_segment_source_invalid") from None

    @router.get("/prospects/{prospect_id}/channel-evidence-preview")
    def crm_channel_evidence_preview(prospect_id: str, request: Request):
        repo = require_repository(request)
        row = guarded_crm_read(lambda: repo.prospect(prospect_id))
        if row is None:
            raise HTTPException(status_code=404, detail="prospect_not_found")
        tenant = getattr(repo, "tenant_id", None)
        if (not isinstance(tenant, str) or not tenant.strip()
                or not isinstance(row, Mapping)
                or str(row.get("tenant_id") or "") != tenant):
            raise HTTPException(status_code=503, detail="crm_channel_tenant_scope_invalid")
        if (resolve_authenticated_channel_evidence is not None
                and not isinstance(repo, PostgresRevenueCrmRepository)):
            raise HTTPException(status_code=503, detail="crm_channel_reader_unavailable")
        channels = {}
        for channel in ("email", "sms", "web_push"):
            try:
                evidence = (resolve_authenticated_channel_evidence(request, prospect_id, channel)
                            if resolve_authenticated_channel_evidence is not None else None)
                channels[channel] = review_channel_evidence(
                    row, channel=channel, evidence=evidence,
                    now=datetime.now(timezone.utc),
                )
            except (ChannelEvidenceError, ValueError, TypeError, RuntimeError, OSError):
                raise HTTPException(status_code=503, detail="crm_channel_reader_unavailable") from None
        return {
            "schema_version": "empire.crm_channel_evidence_preview.v1",
            "mode": "OBSERVE", "tenant_id": tenant,
            "prospect_id": str(row.get("prospect_id")),
            "channels": channels, "contact_values_disclosed": False,
            "send_authorized": False, "execution_authority": "none",
        }

    @router.get("/prospects/{prospect_id}/journey-preview")
    def crm_journey_preview(prospect_id: str, request: Request):
        repo = require_repository(request)
        row = guarded_crm_read(lambda: repo.prospect(prospect_id))
        if row is None:
            raise HTTPException(status_code=404, detail="prospect_not_found")
        tenant = getattr(repo, "tenant_id", None)
        if (not isinstance(tenant, str) or not tenant.strip()
                or not isinstance(row, Mapping)
                or str(row.get("tenant_id") or "") != tenant):
            raise HTTPException(status_code=503, detail="crm_journey_tenant_scope_invalid")
        try:
            return preview_crm_journey(
                row, now=datetime.now(timezone.utc),
                next_action=derive_next_action(row).as_dict(),
            )
        except (ValueError, TypeError):
            raise HTTPException(status_code=503, detail="crm_journey_source_invalid") from None

    @router.get("/prospects")
    def prospects(request: Request, limit: int = Query(default=100, ge=1, le=500)):
        repo = require_repository(request)
        rows = [dict(row) for row in guarded_crm_read(
            lambda: repo.prospects(limit=limit)
        )]
        return {
            "source": "canonical_revenue_crm_repository",
            "count": len(rows),
            "limit": limit,
            "items": rows,
            "read_only": True,
        }

    @router.get("/workspace-solar/prospect-name-matches/preview")
    def workspace_solar_tenant_prospect_name_preview(request: Request):
        """Six-company name-only duplicate preview, signed tenant scope only.

        This is deliberately not a historical receipt-to-contact binding.
        Existing source RLS/tenant membership decides rows first.
        """
        repo = require_repository(request)
        tenant = getattr(repo, "tenant_id", None)
        if not isinstance(tenant, str):
            raise HTTPException(
                status_code=503, detail="crm_tenant_scope_unavailable"
            )
        rows = guarded_crm_read(lambda: repo.prospects(limit=500))
        try:
            return preview_six_tenant_prospect_name_matches(
                rows, authenticated_tenant_id=tenant, window_limit=500,
            )
        except (TenantProspectMatchHeld, ValueError, TypeError):
            raise HTTPException(
                status_code=503, detail="crm_tenant_name_match_source_invalid"
            ) from None

    @router.get("/buyers")
    def buyers(request: Request, limit: int = Query(default=100, ge=1, le=500)):
        repo = require_repository(request)
        rows = [dict(row) for row in guarded_crm_read(
            lambda: repo.buyers(limit=limit)
        )]
        return {
            "source": "canonical_revenue_crm_repository",
            "count": len(rows),
            "limit": limit,
            "items": rows,
            "read_only": True,
        }

    @router.get("/prospects/{prospect_id}/next-action")
    def next_action(prospect_id: str, request: Request):
        repo = require_repository(request)
        row = guarded_crm_read(lambda: repo.prospect(prospect_id))
        if row is None:
            raise HTTPException(status_code=404, detail="prospect_not_found")
        return derive_next_action(row).as_dict()

    @router.get("/prospects/{prospect_id}/reply-qualification-review")
    def reply_qualification_review(prospect_id: str, request: Request):
        """Existing canonical CRM read + Conversation OS review; never a closer handoff."""
        repo = require_repository(request)
        prospect = guarded_crm_read(lambda: repo.prospect(prospect_id))
        if prospect is None:
            raise HTTPException(status_code=404, detail="prospect_not_found")
        cid = str(prospect.get("conversation_id") or "").strip()
        conversation = None
        events = []
        if conversation_read_repository is not None and cid:
            try:
                conversation = conversation_read_repository.conversation(
                    conversation_id=cid
                )
                if conversation is not None:
                    events = list(conversation_read_repository.timeline(
                        conversation_id=cid, limit=200,
                    ))
            except Exception:
                # Never reveal source credentials, provider internals, or
                # an unverified read as an empty successful inbox result.
                raise HTTPException(
                    status_code=503, detail="canonical_conversation_read_unavailable"
                ) from None
        source = assess_sources(evidence_root)
        stage3 = (
            (source.get("sources") or {})
            .get("conversation_os", {})
            .get("reply_identity_integration_health")
        )
        try:
            return review_crm_reply_qualification(
                prospect=prospect,
                conversation=conversation,
                events=events,
                stage3_source_health=stage3,
                now=datetime.now(timezone.utc),
            )
        except ValueError:
            raise HTTPException(
                status_code=422, detail="canonical_qualification_contract_invalid"
            ) from None

    @router.get("/prospects/{prospect_id}/close-readiness")
    def close_readiness(prospect_id: str, request: Request):
        repo = require_repository(request)
        row = guarded_crm_read(lambda: repo.prospect(prospect_id))
        if row is None:
            raise HTTPException(status_code=404, detail="prospect_not_found")
        try:
            readiness = assess_close_readiness(row)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "mode": "OBSERVE",
            "read_only": True,
            "execution_authority": "none",
            "follow_up_execution": False,
            "payment_execution": False,
            "crm_mutation": False,
            "readiness": readiness.as_dict(),
        }

    return router
