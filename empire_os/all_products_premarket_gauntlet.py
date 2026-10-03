"""Product-code-complete pre-market gauntlet for Empire commercial products."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from empire_os.commercial_product_catalog import (
    assess_catalog_item,
    public_catalog_projection,
)
from empire_os.digital_avatar_commercial_packaging import (
    avatar_commercial_package_catalog,
)
from empire_os.digital_avatar_pricing_economics_proposal import (
    DIGITAL_AVATAR_PRICING_PROPOSALS,
)


@dataclass(frozen=True)
class ProductPremarketVerdict:
    product_code: str
    product_name: str
    product_family: str
    active: bool
    classification: str
    readiness_blockers: tuple[str, ...]
    public_catalog_visible: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AllProductsPremarketSnapshot:
    total_catalog_rows: int
    verified_sellable_count: int
    active_pending_count: int
    inactive_recovery_count: int
    verified_sellable_codes: tuple[str, ...]
    active_pending_codes: tuple[str, ...]
    inactive_recovery_codes: tuple[str, ...]
    live_smoke_verified_codes: tuple[str, ...]
    live_smoke_evidence_refs: Mapping[str, str]
    live_smoke_missing_codes: tuple[str, ...]
    campaign_ready_product_codes: tuple[str, ...]
    campaign_blocked_product_codes: tuple[str, ...]
    digital_avatar_proposal_codes: tuple[str, ...]
    rows: tuple[ProductPremarketVerdict, ...]
    all_rows_classified: bool
    duplicate_product_codes: tuple[str, ...]
    malformed_product_codes: tuple[str, ...]
    mode: str = "OBSERVE"
    outbound_send_performed: bool = False
    checkout_created: bool = False
    payment_request_created: bool = False
    funds_moved: bool = False
    binding_terms_mutated: bool = False
    live_meeting_join_performed: bool = False
    revenue_recognized: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "rows": [row.as_dict() for row in self.rows],
        }


def _catalog_rows(snapshot: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    raw = snapshot.get("products")
    if not isinstance(raw, (list, tuple)):
        raise ValueError("catalog snapshot products required")
    rows: list[Mapping[str, Any]] = []
    for row in raw:
        if not isinstance(row, Mapping):
            raise ValueError("catalog product row must be mapping")
        rows.append(row)
    return tuple(rows)


def _digital_avatar_proposal_codes() -> tuple[str, ...]:
    package_codes = tuple(
        item.product_code
        for item in avatar_commercial_package_catalog()
    )
    pricing_codes = tuple(
        item.product_code
        for item in DIGITAL_AVATAR_PRICING_PROPOSALS
    )
    if package_codes != pricing_codes:
        raise ValueError("digital avatar package/pricing proposal mismatch")
    return package_codes


def build_all_products_premarket_snapshot(
    catalog_snapshot: Mapping[str, Any],
    *,
    live_smoke_evidence: Mapping[str, str] | None = None,
) -> AllProductsPremarketSnapshot:
    rows = _catalog_rows(catalog_snapshot)
    seen: set[str] = set()
    duplicates: set[str] = set()
    malformed: set[str] = set()
    assessed_rows: list[dict[str, Any]] = []
    raw_by_code: dict[str, Mapping[str, Any]] = {}

    for row in rows:
        code = str(row.get("product_code") or "").strip()
        if not code:
            malformed.add("<missing>")
            continue
        if code in seen:
            duplicates.add(code)
        seen.add(code)
        raw_by_code[code] = row
        assessed_rows.append(dict(assess_catalog_item(row)))

    if duplicates:
        raise ValueError(
            "duplicate product codes: " + ",".join(sorted(duplicates))
        )
    if malformed:
        raise ValueError("malformed product codes present")

    public = public_catalog_projection({"products": assessed_rows})
    public_codes = {
        str(row.get("product_code") or "").strip()
        for row in public.get("products") or ()
        if str(row.get("product_code") or "").strip()
    }

    verdicts: list[ProductPremarketVerdict] = []
    for assessed in assessed_rows:
        code = str(assessed.get("product_code") or "").strip()
        raw = raw_by_code[code]
        active = bool(raw.get("active"))
        blockers = tuple(
            str(value)
            for value in (assessed.get("readiness_blockers") or ())
        )
        public_visible = code in public_codes

        if active and not blockers and public_visible:
            classification = "verified_sellable"
        elif active:
            classification = "active_pending"
            if public_visible:
                raise ValueError(
                    f"pending product publicly visible: {code}"
                )
        else:
            classification = "inactive_recovery"
            if public_visible:
                raise ValueError(
                    f"inactive product publicly visible: {code}"
                )

        verdicts.append(
            ProductPremarketVerdict(
                product_code=code,
                product_name=str(raw.get("product_name") or "").strip(),
                product_family=str(raw.get("product_family") or "").strip(),
                active=active,
                classification=classification,
                readiness_blockers=blockers,
                public_catalog_visible=public_visible,
            )
        )

    verdicts.sort(key=lambda row: row.product_code)
    verified = tuple(
        row.product_code
        for row in verdicts
        if row.classification == "verified_sellable"
    )
    pending = tuple(
        row.product_code
        for row in verdicts
        if row.classification == "active_pending"
    )
    inactive = tuple(
        row.product_code
        for row in verdicts
        if row.classification == "inactive_recovery"
    )
    proposal_codes = _digital_avatar_proposal_codes()

    smoke = {
        str(code or "").strip(): str(ref or "").strip()
        for code, ref in dict(live_smoke_evidence or {}).items()
        if str(code or "").strip()
    }
    if any(not ref for ref in smoke.values()):
        raise ValueError("live smoke evidence reference required")
    unknown_smoke = set(smoke) - set(verified)
    if unknown_smoke:
        raise ValueError(
            "live smoke evidence supplied for non-sellable product: "
            + ",".join(sorted(unknown_smoke))
        )

    overlap = set(proposal_codes).intersection(seen)
    if overlap:
        raise ValueError(
            "proposal-only Digital Avatar product already in catalog: "
            + ",".join(sorted(overlap))
        )

    all_classified = (
        len(verdicts) == len(rows)
        and len(verified) + len(pending) + len(inactive) == len(rows)
    )
    if not all_classified:
        raise ValueError("not all catalog products classified")

    smoke_verified = tuple(sorted(smoke))
    smoke_missing = tuple(sorted(set(verified) - set(smoke_verified)))
    campaign_ready = smoke_verified
    blocked = tuple(sorted(
        (set(seen) - set(campaign_ready)) | set(proposal_codes)
    ))
    return AllProductsPremarketSnapshot(
        total_catalog_rows=len(rows),
        verified_sellable_count=len(verified),
        active_pending_count=len(pending),
        inactive_recovery_count=len(inactive),
        verified_sellable_codes=verified,
        active_pending_codes=pending,
        inactive_recovery_codes=inactive,
        live_smoke_verified_codes=smoke_verified,
        live_smoke_evidence_refs=smoke,
        live_smoke_missing_codes=smoke_missing,
        campaign_ready_product_codes=campaign_ready,
        campaign_blocked_product_codes=blocked,
        digital_avatar_proposal_codes=proposal_codes,
        rows=tuple(verdicts),
        all_rows_classified=True,
        duplicate_product_codes=(),
        malformed_product_codes=(),
    )
