"""Media Attention Graph packets for the canonical Intelligence Fabric.

This module defines media node/edge observations only. It does not create a
second graph database and does not infer commercial relationships without
evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable


NODE_TYPES = frozenset({
    "PERSON",
    "AUDIENCE",
    "TOPIC",
    "QUERY",
    "KEYWORD",
    "VIDEO",
    "SHORT",
    "CHANNEL",
    "COMMENT",
    "PAIN",
    "DESIRE",
    "PRODUCT",
    "COMPANY",
    "MARKET",
    "LEAD",
    "OPPORTUNITY",
    "CAMPAIGN",
    "TRAFFIC",
    "REVENUE",
    "COMPETITOR",
    "OFFER",
    "TREND",
})

EDGE_TYPES = frozenset({
    "INTERESTED_IN",
    "MENTIONS",
    "ASKS_ABOUT",
    "EXPRESSES_PAIN",
    "EXPRESSES_DESIRE",
    "TARGETS",
    "ABOUT",
    "PUBLISHED_ON",
    "DERIVED_FROM",
    "RELATED_TO",
    "SEARCHES_FOR",
    "INFLUENCED_SESSION",
    "ATTRIBUTED_TO",
    "CREATED_LEAD",
    "CREATED_OPPORTUNITY",
    "SUPPORTED_REVENUE",
    "COMPETES_WITH",
    "ALIGNS_WITH_PRODUCT",
    "SHOWS_TREND",
})


@dataclass(frozen=True)
class AttentionNode:
    node_id: str
    node_type: str
    label: str
    evidence_refs: tuple[str, ...]
    properties: dict[str, Any] | None = None

    def validate(self) -> None:
        if not self.node_id.strip():
            raise ValueError("attention node_id is required")
        if self.node_type not in NODE_TYPES:
            raise ValueError("unsupported attention node_type")
        if not self.label.strip():
            raise ValueError("attention node label is required")
        if not self.evidence_refs:
            raise ValueError("attention nodes require evidence_refs")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            **asdict(self),
            "properties": dict(self.properties or {}),
        }


@dataclass(frozen=True)
class AttentionEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_type: str
    evidence_refs: tuple[str, ...]
    confidence: float | None = None
    inferred: bool = False

    def validate(self) -> None:
        if not self.edge_id.strip():
            raise ValueError("attention edge_id is required")
        if not self.source_node_id.strip() or not self.target_node_id.strip():
            raise ValueError("attention edge endpoints are required")
        if self.edge_type not in EDGE_TYPES:
            raise ValueError("unsupported attention edge_type")
        if not self.evidence_refs:
            raise ValueError("attention edges require evidence_refs")
        if self.confidence is not None:
            if not 0.0 <= float(self.confidence) <= 1.0:
                raise ValueError("edge confidence must be within 0..1")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def build_attention_graph_packet(
    *,
    nodes: Iterable[AttentionNode],
    edges: Iterable[AttentionEdge],
) -> dict[str, Any]:
    node_rows = [node.as_dict() for node in nodes]
    edge_rows = [edge.as_dict() for edge in edges]
    ids = {row["node_id"] for row in node_rows}

    dangling = [
        row["edge_id"]
        for row in edge_rows
        if (
            row["source_node_id"] not in ids
            or row["target_node_id"] not in ids
        )
    ]
    if dangling:
        raise ValueError(
            "attention graph contains dangling edges: "
            + ",".join(sorted(dangling))
        )

    commercial_edges = {
        "CREATED_LEAD",
        "CREATED_OPPORTUNITY",
        "SUPPORTED_REVENUE",
        "ATTRIBUTED_TO",
    }
    unsupported_commercial = [
        row["edge_id"]
        for row in edge_rows
        if row["edge_type"] in commercial_edges
        and row["inferred"] is True
    ]
    if unsupported_commercial:
        raise ValueError(
            "commercial graph edges cannot be inference-only: "
            + ",".join(sorted(unsupported_commercial))
        )

    return {
        "schema_version": "empire.media.attention_graph_packet.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "node_count": len(node_rows),
        "edge_count": len(edge_rows),
        "nodes": node_rows,
        "edges": edge_rows,
        "graph_owner": "intelligence_fabric",
        "second_graph_created": False,
        "commercial_truth_owner": "revenue_pulse",
        "buyer_intent_inferred": False,
        "actual_revenue": False,
        "execution_authority": "none",
    }


def attention_graph_questions() -> dict[str, Any]:
    return {
        "schema_version": "empire.media.attention_graph_questions.v1",
        "supported_question_families": [
            "topics_that_gain_subscribers_without_buyers",
            "videos_that_attract_founders",
            "audience_clusters_that_create_leads",
            "comment_themes_that_repeat_as_product_requests",
            "youtube_topics_that_accelerate_in_search",
            "markets_with_early_attention_acceleration",
            "videos_with_evidence_backed_pipeline_influence",
            "low_value_vs_high_value_audience_content",
            "product_candidates_from_repeated_audience_demand",
        ],
        "answers_require_observed_edges": True,
        "unknown_when_evidence_missing": True,
        "execution_authority": "none",
    }
