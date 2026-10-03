"""Buyer-safe read-only evidence adapters for Digital Avatar drafting."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Callable, Mapping
from uuid import UUID

from empire_os.canonical_data_gateway import CanonicalDataGateway
from empire_os.commercial_product_catalog import public_catalog_projection
from empire_os.data_query import DataFilter


_BUYER_SAFE_PRICE_SOURCES = {
    "buyer_stated",
    "founder_approved",
    "observed_contract",
    "public_price",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _uuid_from_ref(value: str, prefix: str) -> str | None:
    raw = str(value or "").strip()
    if not raw.startswith(prefix):
        return None
    candidate = raw[len(prefix):].strip()
    try:
        return str(UUID(candidate))
    except (ValueError, TypeError, AttributeError):
        return None


def _parse_time(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


class CanonicalCommercialEvidenceResolver:
    """Resolve verified buyer-safe price evidence by canonical UUID."""

    def __init__(
        self,
        gateway: CanonicalDataGateway,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.gateway = gateway
        self.now = now or (lambda: datetime.now(timezone.utc))

    def resolve(self, evidence_ref: str) -> Mapping[str, Any] | None:
        evidence_id = _uuid_from_ref(
            evidence_ref,
            "commercial_evidence:",
        )
        if evidence_id is None:
            return None

        rows = self.gateway.query(
            "commercial_evidence_registry",
            (
                "id,evidence_kind,niche,metro,amount_cents,currency,unit,"
                "source_type,status,valid_until,verified_at"
            ),
            filters=(
                DataFilter.eq("id", evidence_id),
                DataFilter.eq("status", "verified"),
            ),
            limit=2,
        )
        if len(rows) != 1:
            return None
        row = rows[0]
        if str(row.get("id") or "").strip() != evidence_id:
            return None
        if str(row.get("evidence_kind") or "").strip() != "price":
            return None
        source_type = str(row.get("source_type") or "").strip()
        if source_type not in _BUYER_SAFE_PRICE_SOURCES:
            return None
        if str(row.get("currency") or "").strip().upper() != "USD":
            return None
        try:
            amount_cents = int(row.get("amount_cents") or 0)
        except (TypeError, ValueError):
            return None
        if amount_cents <= 0:
            return None
        verified_at = _parse_time(row.get("verified_at"))
        if verified_at is None:
            return None
        valid_until = _parse_time(row.get("valid_until"))
        current = self.now().astimezone(timezone.utc)
        if valid_until is not None and valid_until <= current:
            return None

        unit = str(row.get("unit") or "").strip() or "unspecified"
        scope = " ".join(
            part
            for part in (
                str(row.get("niche") or "").strip(),
                str(row.get("metro") or "").strip(),
            )
            if part
        )
        price = f"${amount_cents / 100:,.2f} USD"
        content = f"Verified price: {price} per {unit}."
        if scope:
            content += f" Scope: {scope}."

        return {
            "evidence_ref": f"commercial_evidence:{evidence_id}",
            "content": content,
            "truth_class": "VERIFIED",
            "source_kind": "commercial_price",
            "provenance": (
                f"commercial_evidence_registry:{evidence_id}:"
                f"verified_at:{verified_at.isoformat()}"
            ),
            "verified": True,
            "facts": {
                "amount_cents": amount_cents,
                "currency": "USD",
                "unit": unit,
                "niche": str(row.get("niche") or "").strip() or None,
                "metro": str(row.get("metro") or "").strip() or None,
                "source_type": source_type,
            },
        }


class CanonicalCommercialTermsResolver:
    """Resolve approved commercial terms without internal cost/margin fields."""

    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self.gateway = gateway

    def resolve(self, evidence_ref: str) -> Mapping[str, Any] | None:
        review_id = _uuid_from_ref(
            evidence_ref,
            "commercial_terms_review:",
        )
        if review_id is None:
            return None

        raw = self.gateway.rpc(
            "get_commercial_terms_review",
            {"p_review_id": review_id},
        )
        if isinstance(raw, list):
            if len(raw) != 1 or not isinstance(raw[0], Mapping):
                return None
            raw = raw[0]
        if not isinstance(raw, Mapping):
            return None
        if str(raw.get("review_id") or "").strip() != review_id:
            return None
        if str(raw.get("status") or "").strip().lower() != "approved":
            return None

        terms_hash = str(raw.get("commercial_terms_sha256") or "").lower()
        if not _SHA256_RE.fullmatch(terms_hash):
            return None
        decided_at = _parse_time(raw.get("decided_at"))
        decided_by = str(raw.get("decided_by") or "").strip()
        if decided_at is None or not decided_by:
            return None
        try:
            price_cents = int(raw.get("price_cents") or 0)
        except (TypeError, ValueError):
            return None
        if price_cents <= 0:
            return None

        terms = raw.get("terms")
        if not isinstance(terms, Mapping):
            return None
        buyer_safe_keys = (
            "currency",
            "settlement_asset",
            "settlement_chain",
            "product_id",
            "product_code",
            "territory",
            "daily_cap",
            "delivery_route",
            "price_cents",
            "buyer_capacity_evidence_ref",
            "verified_price_evidence_ref",
        )
        safe_terms = {
            key: terms.get(key)
            for key in buyer_safe_keys
            if terms.get(key) is not None
        }
        safe_terms["price_cents"] = price_cents
        safe_terms["commercial_terms_sha256"] = terms_hash
        safe_terms["status"] = "approved"

        content = (
            "Approved commercial terms: "
            + json.dumps(
                safe_terms,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
        )
        return {
            "evidence_ref": f"commercial_terms_review:{review_id}",
            "content": content,
            "truth_class": "VERIFIED",
            "source_kind": "approved_commercial_terms",
            "provenance": (
                f"commercial_terms_reviews:{review_id}:"
                f"approved_at:{decided_at.isoformat()}"
            ),
            "verified": True,
            "facts": dict(safe_terms),
        }


class CanonicalCommercialOutcomeResolver:
    """Resolve one canonical buyer-safe commercial outcome by outcome UUID."""

    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self.gateway = gateway

    def resolve(self, evidence_ref: str) -> Mapping[str, Any] | None:
        outcome_id = _uuid_from_ref(
            evidence_ref,
            "canonical:commercial_outcomes:",
        )
        if outcome_id is None:
            return None

        rows = self.gateway.query(
            "commercial_outcomes",
            (
                "id,fulfilment_order_id,delivery_outcome,conversion_outcome,"
                "buyer_satisfaction,evidence_kind,evidence_reference,recorded_at"
            ),
            filters=(DataFilter.eq("id", outcome_id),),
            limit=2,
        )
        if len(rows) != 1:
            return None
        row = rows[0]
        if str(row.get("id") or "").strip() != outcome_id:
            return None

        delivery = str(row.get("delivery_outcome") or "").strip().lower()
        conversion = str(row.get("conversion_outcome") or "").strip().lower()
        evidence_kind = str(row.get("evidence_kind") or "").strip().lower()
        evidence_reference = str(
            row.get("evidence_reference") or ""
        ).strip()
        recorded_at = _parse_time(row.get("recorded_at"))
        order_id = str(row.get("fulfilment_order_id") or "").strip()

        if not order_id or recorded_at is None:
            return None
        if not evidence_kind or not evidence_reference:
            return None
        if delivery == "unknown" and conversion == "unknown":
            return None

        proof = {
            "delivery_outcome": delivery,
            "conversion_outcome": conversion,
        }
        satisfaction = row.get("buyer_satisfaction")
        if satisfaction is not None:
            try:
                score = float(satisfaction)
            except (TypeError, ValueError):
                return None
            if score < 1 or score > 5:
                return None
            proof["buyer_satisfaction"] = round(score, 2)

        content = (
            "Verified commercial outcome: "
            + json.dumps(
                proof,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return {
            "evidence_ref": f"canonical:commercial_outcomes:{outcome_id}",
            "content": content,
            "truth_class": "VERIFIED",
            "source_kind": "commercial_outcome",
            "provenance": (
                f"commercial_outcomes:{outcome_id}:"
                f"{evidence_kind}:{evidence_reference}:"
                f"recorded_at:{recorded_at.isoformat()}"
            ),
            "verified": True,
            "facts": dict(proof),
        }


class CanonicalCommercialProductResolver:
    """Resolve verified public product facts without exposing internal economics."""

    def __init__(self, gateway: CanonicalDataGateway) -> None:
        self.gateway = gateway

    def _product_code(self, evidence_ref: str) -> str | None:
        raw = str(evidence_ref or "").strip()
        if raw.startswith("commercial_product_code:"):
            code = raw.removeprefix("commercial_product_code:").strip()
            return code or None

        product_id = _uuid_from_ref(raw, "commercial_product:")
        if product_id is None:
            return None
        rows = self.gateway.query(
            "commercial_products",
            "id,product_code",
            filters=(DataFilter.eq("id", product_id),),
            limit=2,
        )
        if len(rows) != 1:
            return None
        row = rows[0]
        if str(row.get("id") or "").strip() != product_id:
            return None
        return str(row.get("product_code") or "").strip() or None

    def resolve(self, evidence_ref: str) -> Mapping[str, Any] | None:
        product_code = self._product_code(evidence_ref)
        if not product_code:
            return None

        rows = self.gateway.rpc(
            "get_commercial_product_catalog",
            {
                "p_product_code": product_code,
                "p_limit": 1,
            },
        )
        if isinstance(rows, Mapping):
            rows = [rows]
        if not isinstance(rows, list):
            return None

        public = public_catalog_projection({"products": rows})
        products = public.get("products") or []
        if len(products) != 1 or not isinstance(products[0], Mapping):
            return None
        product = dict(products[0])
        if str(product.get("product_code") or "").strip() != product_code:
            return None

        content = (
            "Verified Empire product: "
            + json.dumps(
                product,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
        )
        return {
            "evidence_ref": str(evidence_ref).strip(),
            "content": content,
            "truth_class": "VERIFIED",
            "source_kind": "commercial_product_catalog",
            "provenance": f"get_commercial_product_catalog:{product_code}",
            "verified": True,
            "facts": dict(product),
        }
