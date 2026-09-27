"""Strategic keyword universe for Empire Search / Strategy.

This layer maps search demand to products, ICPs, funnel stages, asset types and
revenue attribution. It never fabricates search volume and cannot publish or
index content.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping

from empire_os.strategy_operating_system import score_keyword_opportunity


INTENT_CLASSES = {
    "category",
    "problem",
    "product",
    "commercial",
    "comparison",
    "territory",
    "event_trigger",
    "agency_white_label",
    "enterprise_api",
    "education",
}

FUNNEL_STAGES = {
    "awareness",
    "consideration",
    "evaluation",
    "conversion",
    "expansion",
}

ASSET_TYPES = {
    "pillar_page",
    "product_page",
    "comparison_page",
    "territory_report",
    "market_report",
    "calculator",
    "free_tool",
    "benchmark_report",
    "api_page",
    "partner_page",
    "guide",
    "case_study",
    "demo",
    "faq",
}

DEFAULT_ASSET_BY_INTENT = {
    "category": "pillar_page",
    "problem": "guide",
    "product": "product_page",
    "commercial": "demo",
    "comparison": "comparison_page",
    "territory": "territory_report",
    "event_trigger": "market_report",
    "agency_white_label": "partner_page",
    "enterprise_api": "api_page",
    "education": "guide",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class KeywordRecord:
    keyword: str
    cluster_key: str
    intent_class: str
    product_key: str
    icp_key: str
    funnel_stage: str
    asset_type: str
    cta_key: str
    free_tool_key: str | None
    territory_key: str | None
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        for field in ("keyword", "cluster_key", "product_key", "icp_key", "cta_key"):
            if not _text(getattr(self, field)):
                raise ValueError(f"{field} required")
        if self.intent_class not in INTENT_CLASSES:
            raise ValueError("unsupported intent_class")
        if self.funnel_stage not in FUNNEL_STAGES:
            raise ValueError("unsupported funnel_stage")
        if self.asset_type not in ASSET_TYPES:
            raise ValueError("unsupported asset_type")
        if not self.evidence_refs:
            raise ValueError("keyword record requires evidence_refs")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        result = asdict(self)
        result["evidence_refs"] = list(self.evidence_refs)
        return result


def keyword_record_from_mapping(raw: Mapping[str, Any]) -> KeywordRecord:
    intent = _text(raw.get("intent_class")).lower()
    asset = _text(raw.get("asset_type")).lower()
    if not asset and intent in DEFAULT_ASSET_BY_INTENT:
        asset = DEFAULT_ASSET_BY_INTENT[intent]
    return KeywordRecord(
        keyword=_text(raw.get("keyword")),
        cluster_key=_text(raw.get("cluster_key")),
        intent_class=intent,
        product_key=_text(raw.get("product_key")),
        icp_key=_text(raw.get("icp_key")),
        funnel_stage=_text(raw.get("funnel_stage")).lower(),
        asset_type=asset,
        cta_key=_text(raw.get("cta_key")),
        free_tool_key=_text(raw.get("free_tool_key")) or None,
        territory_key=_text(raw.get("territory_key")) or None,
        evidence_refs=tuple(
            _text(ref) for ref in raw.get("evidence_refs", ()) if _text(ref)
        ),
    )


def review_keyword_record(raw: Mapping[str, Any]) -> dict[str, Any]:
    try:
        record = keyword_record_from_mapping(raw)
        record.validate()
    except ValueError as exc:
        return {
            "schema_version": "keyword_record_review.v1",
            "review_ready": False,
            "blockers": [str(exc)],
            "publishing_enabled": False,
            "indexation_enabled": False,
            "execution_authority": "none",
        }

    score = score_keyword_opportunity({
        "keyword": record.keyword,
        "observed_demand": raw.get("observed_demand"),
        "commercial_intent": raw.get("commercial_intent"),
        "product_fit": raw.get("product_fit"),
        "buyer_fit": raw.get("buyer_fit"),
        "coverage_gap": raw.get("coverage_gap"),
        "competitor_gap": raw.get("competitor_gap"),
        "ai_citation_gap": raw.get("ai_citation_gap"),
        "conversion_evidence": raw.get("conversion_evidence"),
        "strategic_category_value": raw.get("strategic_category_value"),
        "confidence": raw.get("confidence"),
        "evidence_refs": list(record.evidence_refs),
    })

    expected_gp = _number(raw.get("expected_gross_profit_cents"))
    realized_gp = _number(raw.get("attributed_realized_gross_profit_cents"))
    attribution_confidence = _number(raw.get("attribution_confidence"))
    if attribution_confidence is not None and not 0 <= attribution_confidence <= 1:
        raise ValueError("attribution_confidence must be between 0 and 1")

    revenue_evidence = {
        "expected_gross_profit_cents": expected_gp,
        "attributed_realized_gross_profit_cents": realized_gp,
        "attribution_confidence": attribution_confidence,
        "actual_revenue_claimed": False,
    }

    return {
        "schema_version": "keyword_record_review.v1",
        "review_ready": True,
        "record": record.as_dict(),
        "opportunity": score,
        "revenue_evidence": revenue_evidence,
        "publishing_enabled": False,
        "indexation_enabled": False,
        "execution_authority": "none",
    }


def _asset_plan(record: KeywordRecord) -> dict[str, Any]:
    objectives = {
        "awareness": "educate category/problem demand",
        "consideration": "help buyer evaluate the problem and product fit",
        "evaluation": "support vendor/product comparison and proof",
        "conversion": "convert high-intent demand into a governed commercial path",
        "expansion": "support renewal, adjacent-product or territory expansion",
    }
    return {
        "keyword": record.keyword,
        "cluster_key": record.cluster_key,
        "product_key": record.product_key,
        "icp_key": record.icp_key,
        "funnel_stage": record.funnel_stage,
        "intent_class": record.intent_class,
        "recommended_asset_type": record.asset_type,
        "free_tool_key": record.free_tool_key,
        "cta_key": record.cta_key,
        "territory_key": record.territory_key,
        "objective": objectives[record.funnel_stage],
        "draft_only": True,
        "publishing_enabled": False,
        "indexation_enabled": False,
    }


def build_keyword_universe(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    records = []
    rejected = []
    seen: set[str] = set()

    for raw in rows:
        review = review_keyword_record(raw)
        if not review["review_ready"]:
            rejected.append(review)
            continue

        record = review["record"]
        key = record["keyword"].lower()
        if key in seen:
            raise ValueError("duplicate keyword")
        seen.add(key)
        records.append(review)

    ranked = sorted(
        records,
        key=lambda item: (
            item["opportunity"]["available"],
            item["opportunity"]["score"] if item["opportunity"]["score"] is not None else -1,
            item["record"]["keyword"],
        ),
        reverse=True,
    )
    for idx, item in enumerate(ranked, 1):
        item["universe_rank"] = idx

    return {
        "schema_version": "keyword_universe.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "keywords": ranked,
        "rejected": rejected,
        "publishing_enabled": False,
        "indexation_enabled": False,
    }


def keyword_coverage_matrix(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    universe = build_keyword_universe(rows)
    by_product: dict[str, dict[str, int]] = {}
    by_cluster: dict[str, dict[str, int]] = {}

    for item in universe["keywords"]:
        record = item["record"]
        product = record["product_key"]
        cluster = record["cluster_key"]
        stage = record["funnel_stage"]

        by_product.setdefault(product, {s: 0 for s in sorted(FUNNEL_STAGES)})
        by_product[product][stage] += 1

        by_cluster.setdefault(cluster, {s: 0 for s in sorted(FUNNEL_STAGES)})
        by_cluster[cluster][stage] += 1

    coverage_gaps = []
    for product, counts in sorted(by_product.items()):
        for stage, count in counts.items():
            if count == 0:
                coverage_gaps.append({
                    "product_key": product,
                    "funnel_stage": stage,
                    "reason": "no_mapped_keyword",
                })

    return {
        "schema_version": "keyword_coverage_matrix.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "by_product": by_product,
        "by_cluster": by_cluster,
        "coverage_gaps": coverage_gaps,
        "publishing_enabled": False,
        "indexation_enabled": False,
    }


def build_asset_backlog(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    universe = build_keyword_universe(rows)
    backlog = []

    for item in universe["keywords"]:
        record = keyword_record_from_mapping(item["record"])
        plan = _asset_plan(record)
        plan["opportunity_score"] = item["opportunity"]["score"]
        plan["opportunity_available"] = item["opportunity"]["available"]
        plan["revenue_evidence"] = item["revenue_evidence"]
        backlog.append(plan)

    backlog.sort(
        key=lambda item: (
            item["opportunity_available"],
            item["opportunity_score"] if item["opportunity_score"] is not None else -1,
            item["keyword"],
        ),
        reverse=True,
    )
    for idx, item in enumerate(backlog, 1):
        item["backlog_rank"] = idx

    return {
        "schema_version": "keyword_asset_backlog.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "assets": backlog,
        "publishing_enabled": False,
        "indexation_enabled": False,
    }
