"""Private, unmounted Empire Data Cloud proof-of-contract API.

This is a TestClient/injected-adapter harness, not a production router.
It does not retrieve secrets, call any network provider, or alter EmpireOS.
Runtime source rights and authenticated tenant identity MUST be supplied by
an existing authorised EmpireOS component before any real deployment.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from ipaddress import ip_address
from threading import RLock
from typing import Callable, Mapping, Any
from urllib.parse import urlsplit

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=3, max_length=180)
    limit: int = Field(default=10, ge=1, le=20)


class AuditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=12, max_length=2048)


@dataclass(frozen=True)
class TenantPolicy:
    tenant_id: str  # derived only from existing verified server-side identity
    monthly_cap: int
    permitted_operations: frozenset[str]
    approved_site_hosts: frozenset[str] = frozenset()
    # Scope is intentionally fixed per authenticated customer.


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_safe_http_url(raw: str, approved_hosts: frozenset[str]) -> str:
    """Syntactic and exact-host admission only. Adapter must enforce safe DNS/redirects."""
    try:
        p = urlsplit(raw)
        host = (p.hostname or "").lower().rstrip(".")
        port = p.port
    except ValueError as exc:
        raise HTTPException(400, "invalid_site_url") from exc
    if (p.scheme != "https" or not host or p.username or p.password or
            port not in (None, 443) or p.fragment):
        raise HTTPException(400, "invalid_site_url")
    if host == "localhost" or host.endswith((".local", ".localhost", ".internal")):
        raise HTTPException(400, "invalid_site_url")
    try:
        ip_address(host)
    except ValueError:
        pass
    else:
        raise HTTPException(400, "literal_ip_not_supported")
    if host not in approved_hosts:
        raise HTTPException(403, "site_not_approved_for_tenant")
    return raw


def hash_token(raw: str) -> str:
    return sha256(raw.encode("utf-8")).hexdigest()


class PrivateUsageLedger:
    """Thread-safe proof ledger. Non-durable: NOT suitable for public metering."""
    def __init__(self):
        self._lock = RLock()
        self._counts: dict[tuple[str, str], int] = {}

    def snapshot(self, policy: TenantPolicy) -> dict[str, Any]:
        window = datetime.now(timezone.utc).strftime("%Y-%m")
        with self._lock:
            count = self._counts.get((policy.tenant_id, window), 0)
        return {"window": window, "request_count": count,
                "cap": policy.monthly_cap, "billing_enabled": False}

    def reserve(self, policy: TenantPolicy) -> None:
        window = datetime.now(timezone.utc).strftime("%Y-%m")
        key = (policy.tenant_id, window)
        with self._lock:
            count = self._counts.get(key, 0)
            if count >= policy.monthly_cap:
                raise HTTPException(429, "usage_cap_reached")
            self._counts[key] = count + 1


def create_private_app(
    *,
    # SHA-256 hashes of caller-provisioned API tokens. Never accept a caller tenant_id.
    tenant_registry: Mapping[str, TenantPolicy] | None = None,
    search_adapter: Callable[[str, int], Mapping[str, Any]] | None = None,
    site_adapter: Callable[[str], Mapping[str, Any]] | None = None,
    ledger: PrivateUsageLedger | None = None,
    # Provider rights approval is an explicit out-of-band evidence gate.
    licensed_search_output: bool = False,
    site_adapter_enforces_public_dns_and_redirects: bool = False,
) -> FastAPI:
    registry = tenant_registry or {}
    usage = ledger or PrivateUsageLedger()
    app = FastAPI(title="Empire Data Cloud private proof", version="0.1.0-private")

    def authenticate(authorization: str | None) -> TenantPolicy:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "valid_bearer_token_required")
        token = authorization[7:]
        if not 24 <= len(token) <= 512:
            raise HTTPException(401, "valid_bearer_token_required")
        from hmac import compare_digest
        digest = hash_token(token)
        for stored, policy in registry.items():
            if compare_digest(digest, stored):
                if not policy.tenant_id or policy.monthly_cap < 0:
                    raise HTTPException(403, "tenant_not_configured")
                return policy
        raise HTTPException(401, "valid_bearer_token_required")

    @app.get("/v1/data/usage")
    def get_usage(authorization: str | None = Header(default=None)):
        policy = authenticate(authorization)
        return usage.snapshot(policy)

    @app.post("/v1/data/search")
    def search(req: SearchRequest, authorization: str | None = Header(default=None)):
        policy = authenticate(authorization)
        if "search" not in policy.permitted_operations:
            raise HTTPException(403, "search_not_entitled")
        if not licensed_search_output:
            raise HTTPException(403, "source_resale_rights_unverified")
        if search_adapter is None:
            raise HTTPException(503, "approved_search_adapter_unavailable")
        usage.reserve(policy)
        try:
            payload = search_adapter(req.query, req.limit)
        except Exception as exc:
            raise HTTPException(503, "source_unavailable") from exc
        if not isinstance(payload, Mapping) or not isinstance(payload.get("organic"), list):
            raise HTTPException(503, "invalid_source_response")
        if payload.get("error"):
            raise HTTPException(503, "source_unavailable")
        observed_at = utc_now()
        results = []
        for result in payload["organic"][:req.limit]:
            if not isinstance(result, Mapping):
                raise HTTPException(503, "invalid_source_response")
            try:
                url = str(result["link"])
                parsed = urlsplit(url)
                if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                    raise ValueError("invalid URL")
                title = str(result["title"])
            except (KeyError, TypeError, ValueError):
                raise HTTPException(503, "invalid_source_response") from None
            results.append({"title": title, "url": url,
                            "snippet": str(result.get("snippet") or ""),
                            "source": {"url": url, "retrieved_at": observed_at,
                                       "evidence_type": "public_search"}})
        return {"status": "results" if results else "no_results",
                "results": results, "buyer_intent_verified": False}

    @app.post("/v1/data/site-audits")
    def audit(req: AuditRequest, authorization: str | None = Header(default=None)):
        policy = authenticate(authorization)
        if "site_audit" not in policy.permitted_operations:
            raise HTTPException(403, "site_audit_not_entitled")
        url = parse_safe_http_url(req.url, policy.approved_site_hosts)
        if site_adapter is None or not site_adapter_enforces_public_dns_and_redirects:
            raise HTTPException(503, "safe_site_adapter_unavailable")
        usage.reserve(policy)
        try:
            report = site_adapter(url)
        except Exception as exc:
            raise HTTPException(503, "site_audit_unavailable") from exc
        if not isinstance(report, Mapping):
            raise HTTPException(503, "site_audit_unavailable")
        observed_at = utc_now()
        findings = []
        for item in report.get("findings", []):
            if not isinstance(item, Mapping):
                raise HTTPException(503, "invalid_site_report")
            findings.append({"code": str(item.get("code") or "unknown"),
                             "severity": str(item.get("severity") or "low"),
                             "message": str(item.get("message") or ""),
                             **({"url": item["url"]} if item.get("url") else {})})
        return {"status": "observed" if report.get("available") is True else "unavailable",
                "findings": findings,
                "source": {"url": url, "retrieved_at": observed_at,
                           "evidence_type": "public_site_probe"},
                "verified_revenue_impact": False}

    return app
