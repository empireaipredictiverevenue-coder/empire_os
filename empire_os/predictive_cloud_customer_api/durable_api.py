"""Private customer-style API proof backed by a durable cost and key ledger.

This is intentionally *not* mounted inside EmpireOS. Existing gateway auth,
commercial rights, egress controls and production meter must be integrated
by the owning operator before external use.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit
import json
import re

from fastapi import FastAPI, Header, HTTPException, Request
from empire_os.predictive_cloud_gateway_attestation import verify_gateway_attestation

from .durable_store import DurablePilotStore, ActiveTenant, AdmissionError
from .private_api import AuditRequest, SearchRequest, parse_safe_http_url

_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")
_SEARCH_SOURCE_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{2,63}$")


# The existing Scrapling Revenue Data Fabric produces OFFLINE_REVIEW_ONLY
# company observations, not licensed customer search results. Even a
# misconfigured operator rights callback cannot override an explicit HOLD.
_NON_CUSTOMER_MODES = frozenset({
    "OFFLINE_REVIEW_ONLY", "RESEARCH_ONLY", "OBSERVE", "ONE_SHOT_SHADOW_ONLY",
})
_NON_RESALE_FIELDS = (
    "commercial_resale_authorized", "source_raw_resale_policy",
    "customer_output_authorized",
)


def _source_output_has_explicit_hold(payload: Mapping[str, Any]) -> bool:
    if (payload.get("schema_version") == "empire.scrapling_source_evidence.v1"
            or payload.get("mode") in _NON_CUSTOMER_MODES
            or any(payload.get(field) is False for field in _NON_RESALE_FIELDS)):
        return True
    for result in payload.get("organic", []):
        if isinstance(result, Mapping) and (
            result.get("mode") in _NON_CUSTOMER_MODES
            or any(result.get(field) is False for field in _NON_RESALE_FIELDS)
        ):
            return True
    return False


def _licensed_search_formatter(
    payload: Mapping[str, Any], limit: int, tenant_id: str, source_id: str,
    rights_check: Callable[[str, str, Mapping[str, Any]], bool],
) -> dict[str, Any]:
    # Bind BOTH trusted rights checks and the provider's returned lineage to
    # the source selected by the existing gateway owner before a paid request.
    # Source-id claims in a payload are not independent licence proof.
    if (
        not isinstance(payload, Mapping)
        or payload.get("source_id") != source_id
        or _source_output_has_explicit_hold(payload)
        or rights_check(tenant_id, source_id, payload) is not True
    ):
        raise ValueError("customer_output_source_or_rights_not_proven")
    return _format_search(payload, limit, source_id)


def _http_error(exc: AdmissionError) -> HTTPException:
    return HTTPException(exc.status_code, exc.detail)


def _fingerprint(operation: str, payload: Mapping[str, Any]) -> str:
    content = json.dumps({"operation": operation, "payload": payload}, sort_keys=True, separators=(",", ":"))
    return sha256(content.encode()).hexdigest()


def _trusted_actual_cost(payload: Mapping[str, Any]) -> tuple[int | None, str | None]:
    """Only a provider adapter may supply signed/verified cost evidence.

    Fixture contract: a trusted upstream adapter must validate cost against
    its invoice/call receipt before labelling it verified. Unverified amounts
    never become 'actual' usage or billing claims.
    """
    receipt = payload.get("provider_cost_receipt")
    if receipt is None:
        return None, None
    if (not isinstance(receipt, Mapping) or receipt.get("verified") is not True or
            type(receipt.get("actual_usd_micros")) is not int or
            receipt["actual_usd_micros"] < 0 or
            not isinstance(receipt.get("source_ref"), str) or
            not receipt["source_ref"].strip()):
        raise ValueError("invalid verified provider cost receipt")
    return receipt["actual_usd_micros"], receipt["source_ref"].strip()


def _format_search(payload: Mapping[str, Any], limit: int, source_id: str) -> dict[str, Any]:
    """Format only a recent, operationally healthy, source-identified response.

    Do not relabel a stale Search Fabric cache or failed provider as a fresh
    customer search. The trusted adapter is responsible for proving when its
    underlying source was actually observed, not simply when JSON was built.
    """
    from empire_os.search_intelligence.backlink_live_verifier import safe_https_url
    if (
        not isinstance(payload, Mapping)
        or payload.get("source_id") != source_id
        or payload.get("error")
        or not isinstance(payload.get("organic"), list)
        or payload.get("search_operational_status") not in {"HEALTHY", "RECOVERED"}
        or not isinstance(payload.get("searchParameters"), Mapping)
    ):
        raise ValueError("invalid_or_unhealthy_search_source")
    state = payload["searchParameters"].get("search_state")
    if state not in {"RESULTS", "NO_RELEVANT_RESULTS"}:
        raise ValueError("unverified_search_result_state")
    if (state == "RESULTS") != bool(payload["organic"]):
        raise ValueError("inconsistent_search_result_state")

    raw_observed = payload.get("source_observed_at")
    if type(raw_observed) is not str or not 1 <= len(raw_observed) <= 40:
        raise ValueError("source_observation_time_required")
    try:
        observed = datetime.fromisoformat(raw_observed.replace("Z", "+00:00"))
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("naive observation")
        observed = observed.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("source_observation_time_invalid") from None
    now = datetime.now(timezone.utc)
    if now - observed > timedelta(hours=24) or observed > now + timedelta(minutes=5):
        raise ValueError("stale_or_future_search_observation")
    timestamp = now.isoformat()
    observed_at = observed.isoformat()
    results = []
    for result in payload["organic"][:limit]:
        if not isinstance(result, Mapping):
            raise ValueError("invalid search result")
        url = result.get("link")
        title = result.get("title")
        snippet = result.get("snippet", "")
        if (
            type(url) is not str or type(title) is not str
            or not title.strip() or len(title) > 300
            or type(snippet) is not str or len(snippet) > 2000
        ):
            raise ValueError("invalid_or_unbounded_search_result")
        try:
            normalized_url = safe_https_url(url)
        except Exception:
            raise ValueError("unsafe_search_result_url") from None
        results.append({
            "title": title, "url": normalized_url, "snippet": snippet,
            "source": {
                "url": normalized_url, "source_id": source_id,
                "retrieved_at": timestamp, "observed_at": observed_at,
                "evidence_type": "public_search",
            },
        })
    return {
        "status": "results" if results else "no_results",
        "results": results, "buyer_intent_verified": False,
    }


def _format_audit(report: Mapping[str, Any], url: str) -> dict[str, Any]:
    if not isinstance(report, Mapping) or not isinstance(report.get("findings", []), list):
        raise ValueError("invalid site audit payload")
    findings = []
    for finding in report.get("findings", []):
        if not isinstance(finding, Mapping):
            raise ValueError("invalid finding")
        severity = str(finding.get("severity") or "low")
        if severity not in {"critical", "high", "medium", "low"}:
            raise ValueError("invalid severity")
        item = {"code": str(finding.get("code") or "unknown"),
                "severity": severity, "message": str(finding.get("message") or "")}
        if finding.get("url"):
            item["url"] = str(finding["url"])
        findings.append(item)
    response_at = datetime.now(timezone.utc).isoformat()
    source = {"url": url, "retrieved_at": response_at,
              "evidence_type": "public_site_probe"}
    # The published API contract uses retrieved_at for response assembly.
    # A previously captured source must also declare the real observation time
    # instead of being misrepresented as a fresh live retrieval.
    if report.get("source_observed_at") is not None:
        observed_at = report["source_observed_at"]
        if not isinstance(observed_at, str):
            raise ValueError("invalid source observation time")
        try:
            parsed_observation = datetime.fromisoformat(observed_at)
        except ValueError as exc:
            raise ValueError("invalid source observation time") from exc
        if parsed_observation.tzinfo is None:
            raise ValueError("source timestamp lacks timezone")
        source["observed_at"] = parsed_observation.astimezone(timezone.utc).isoformat()
    return {"status": "observed" if report.get("available") is True else "unavailable",
            "findings": findings, "source": source,
            "verified_revenue_impact": False}


def create_metered_private_app(
    *,
    store: DurablePilotStore,
    search_adapter: Callable[[str, int], Mapping[str, Any]] | None = None,
    # Fixed trusted supplier/collector identity; never taken from request JSON.
    search_source_id: str | None = None,
    site_adapter: Callable[[str], Mapping[str, Any]] | None = None,
    licensed_search_output: bool = False,
    # Existing owner must supply an independently evidenced provider/source
    # entitlement check. Boolean enablement alone is insufficient.
    source_rights_check: Callable[[str, str, Mapping[str, Any]], bool] | None = None,
    # Must authorize the planned query BEFORE reserving quota or calling a
    # potentially chargeable provider. The output check still runs afterward.
    source_request_preflight: Callable[[str, str, str, int], bool] | None = None,
    site_adapter_egress_reviewed: bool = False,
    # Customer may submit only an independently approved site. Tenant host
    # allowlisting is necessary but NOT sufficient proof of ownership/consent.
    site_request_preflight: Callable[[str, str], bool] | None = None,
    require_gateway_attestation: bool = False,
) -> FastAPI:
    """Private customer-like API. All privileged inputs come from operator code."""
    app = FastAPI(title="Empire Data Cloud private cost-metered proof", version="0.2.0-private")

    @app.middleware("http")
    async def prevent_sensitive_response_caching(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def authenticate(authorization: str | None, request: Request) -> tuple[ActiveTenant, str]:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "valid_bearer_token_required")
        token = authorization[7:]
        try:
            policy = store.authenticate(token)
            if require_gateway_attestation:
                verify_gateway_attestation(request, tenant_id=policy.tenant_id)
            return policy, sha256(token.encode()).hexdigest()
        except AdmissionError as exc:
            raise _http_error(exc) from exc

    def reserve(policy: ActiveTenant, token_hash: str, operation: str,
                idempotency_key: str | None, request: Mapping[str, Any],
                target_host: str | None = None) -> int:
        if not idempotency_key or not _IDEMPOTENCY_RE.fullmatch(idempotency_key):
            raise HTTPException(400, "valid_idempotency_key_required")
        try:
            return store.reserve(policy, operation, idempotency_key,
                                 _fingerprint(operation, request), token_hash, target_host=target_host)
        except AdmissionError as exc:
            raise _http_error(exc) from exc

    def run_operation(policy: ActiveTenant, reservation_id: int, token_hash: str,
                      adapter: Callable[[], Mapping[str, Any]],
                      formatter: Callable[[Mapping[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        try:
            payload = adapter()
            if not isinstance(payload, Mapping):
                raise ValueError("invalid adapter payload")
            response = formatter(payload)
            amount, ref = _trusted_actual_cost(payload)
        except Exception as exc:
            try:
                store.settle(policy, reservation_id, "provider_error", token_hash=token_hash)
            except Exception:
                pass  # Reservation stays consumed and requires operator recovery.
            raise HTTPException(503, "upstream_or_cost_evidence_unavailable") from exc
        try:
            store.settle(policy, reservation_id, "completed",
                         actual_usd_micros=amount, cost_source_ref=ref, token_hash=token_hash)
        except AdmissionError as exc:
            raise _http_error(exc) from exc
        except Exception as exc:
            raise HTTPException(503, "usage_settlement_unavailable") from exc
        return response

    @app.get("/v1/data/usage")
    def get_usage(request: Request, authorization: str | None = Header(default=None)):
        policy, token_hash = authenticate(authorization, request)
        try:
            return store.snapshot(policy, token_hash=token_hash)
        except AdmissionError as exc:
            raise _http_error(exc) from exc

    @app.post("/v1/data/search")
    def search(req: SearchRequest, request: Request, authorization: str | None = Header(default=None),
               idempotency_key: str | None = Header(default=None)):
        policy, token_hash = authenticate(authorization, request)
        if "search" not in policy.permitted_operations:
            raise HTTPException(403, "search_not_entitled")
        if not licensed_search_output:
            raise HTTPException(403, "source_resale_rights_unverified")
        if type(search_source_id) is not str or not _SEARCH_SOURCE_ID_RE.fullmatch(search_source_id):
            raise HTTPException(503, "trusted_search_source_id_unconfigured")
        if source_rights_check is None:
            raise HTTPException(503, "source_rights_checker_unconfigured")
        if search_adapter is None:
            raise HTTPException(503, "approved_search_adapter_unavailable")
        if source_request_preflight is None:
            raise HTTPException(503, "source_request_rights_preflight_unconfigured")
        try:
            permitted = source_request_preflight(policy.tenant_id, search_source_id, req.query, req.limit)
        except Exception as exc:
            raise HTTPException(503, "source_request_rights_preflight_unavailable") from exc
        if permitted is not True:
            raise HTTPException(403, "source_request_rights_not_authorized")
        rid = reserve(policy, token_hash, "search", idempotency_key,
                      {"query": req.query, "limit": req.limit})
        return run_operation(policy, rid, token_hash, lambda: search_adapter(req.query, req.limit),
                             lambda data: _licensed_search_formatter(
                                 data, req.limit, policy.tenant_id, search_source_id, source_rights_check))

    @app.post("/v1/data/site-audits")
    def site_audit(req: AuditRequest, request: Request, authorization: str | None = Header(default=None),
                   idempotency_key: str | None = Header(default=None)):
        policy, token_hash = authenticate(authorization, request)
        if "site_audit" not in policy.permitted_operations:
            raise HTTPException(403, "site_audit_not_entitled")
        url = parse_safe_http_url(req.url, policy.approved_site_hosts)
        if site_adapter is None or not site_adapter_egress_reviewed:
            raise HTTPException(503, "safe_site_adapter_unavailable")
        if site_request_preflight is None:
            raise HTTPException(503, "site_ownership_preflight_unconfigured")
        try:
            # The proof is tenant-bound; global domain ownership is not enough.
            permission = site_request_preflight(policy.tenant_id, url)
        except Exception as exc:
            raise HTTPException(503, "site_ownership_preflight_unavailable") from exc
        if permission is not True:
            raise HTTPException(403, "site_ownership_not_verified")
        rid = reserve(policy, token_hash, "site_audit", idempotency_key, {"url": url},
                      target_host=urlsplit(url).hostname)
        return run_operation(policy, rid, token_hash, lambda: site_adapter(url),
                             lambda data: _format_audit(data, url))

    return app
