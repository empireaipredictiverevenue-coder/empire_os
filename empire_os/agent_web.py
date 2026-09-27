"""Shared capability catalogue for Empire WebMCP, MCP and A2A surfaces.

Public capabilities are discovery/read intelligence only. Privileged commercial
execution stays behind Astra governance and authenticated internal services.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Capability:
    key: str
    title: str
    description: str
    intelligence: tuple[str, ...]
    input_schema: dict[str, Any]
    surfaces: tuple[str, ...] = ("webmcp", "mcp", "a2a")
    access: str = "public_read"
    read_only: bool = True
    untrusted_content: bool = False
    consequential: bool = False


def _schema(properties: dict[str, Any], required: tuple[str, ...] = ()) -> dict[str, Any]:
    out: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        out["required"] = list(required)
    return out

CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        "market.search",
        "Market Search",
        "Discover a market by niche and metro with evidence-aware demand signals.",
        ("market", "signal", "intent", "provenance"),
        _schema({
            "niche": {"type": "string", "minLength": 2},
            "metro": {"type": "string", "minLength": 2},
            "query": {"type": "string"},
        }, ("niche", "metro")),
    ),
    Capability(
        "market.forecast",
        "Market Forecast",
        "Return a directional market forecast with confidence and evidence summary.",
        ("market", "forecast", "demand", "confidence", "provenance"),
        _schema({
            "niche": {"type": "string", "minLength": 2},
            "metro": {"type": "string", "minLength": 2},
            "horizon_days": {"type": "integer", "minimum": 1, "maximum": 365, "default": 30},
        }, ("niche", "metro")),
    ),
    Capability(
        "opportunity.search",
        "Opportunity Search",
        "Find scored commercial opportunities without allocating or reserving inventory.",
        ("opportunity", "revenue", "buyer_fit", "confidence", "provenance"),
        _schema({
            "niche": {"type": "string", "minLength": 2},
            "metro": {"type": "string", "minLength": 2},
            "min_score": {"type": "number", "minimum": 0, "maximum": 100, "default": 60},
            "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 10},
        }, ("niche", "metro")),
    ),
    Capability(
        "growth.seo.audit",
        "SEO Audit",
        "Inspect a public page for technical and commercial-search opportunities.",
        ("seo", "keyword", "content", "commercial_intent"),
        _schema({"url": {"type": "string", "format": "uri"}}, ("url",)),
        untrusted_content=True,
    ),
    Capability(
        "growth.aeo.audit",
        "AEO Audit",
        "Assess answer extractability, entity coverage, evidence and question gaps.",
        ("aeo", "entity", "evidence", "question_graph", "citation"),
        _schema({"url": {"type": "string", "format": "uri"}, "question": {"type": "string"}}, ("url",)),
        untrusted_content=True,
    ),
    Capability(
        "growth.geo.visibility",
        "GEO Visibility",
        "Inspect generative-engine visibility, source coverage and citation gaps.",
        ("geo", "ai_visibility", "citation", "competitor_gap", "provenance"),
        _schema({
            "brand": {"type": "string", "minLength": 2},
            "query": {"type": "string", "minLength": 2},
            "locale": {"type": "string", "default": "en-GB"},
        }, ("brand", "query")),
        untrusted_content=True,
    ),
    Capability(
        "citation.search",
        "Citation Search",
        "Find evidence and citation opportunities for an entity or commercial question.",
        ("citation", "authority", "evidence", "entity", "provenance"),
        _schema({
            "entity": {"type": "string", "minLength": 2},
            "query": {"type": "string"},
        }, ("entity",)),
    ),
    Capability(
        "product.catalog",
        "Product Catalogue",
        "Discover Empire products and availability without creating a quote or commitment.",
        ("product_fit", "commercial_intent", "buyer_fit"),
        _schema({"category": {"type": "string"}}),
    ),
)

def public_capabilities(surface: str | None = None) -> list[Capability]:
    return [
        cap for cap in CAPABILITIES
        if cap.access == "public_read" and (surface is None or surface in cap.surfaces)
    ]


def capability_manifest(surface: str | None = None) -> list[dict[str, Any]]:
    return [{
        "name": cap.key,
        "title": cap.title,
        "description": cap.description,
        "intelligence": list(cap.intelligence),
        "inputSchema": cap.input_schema,
        "access": cap.access,
        "annotations": {
            "readOnlyHint": cap.read_only,
            "untrustedContentHint": cap.untrusted_content,
            "consequentialHint": cap.consequential,
        },
    } for cap in public_capabilities(surface)]


def webmcp_manifest() -> list[dict[str, Any]]:
    return capability_manifest("webmcp")

def a2a_agent_card(base_url: str) -> dict[str, Any]:
    base = base_url.rstrip("/")
    tags = sorted({tag for cap in public_capabilities("a2a") for tag in cap.intelligence})
    return {
        "name": "Empire Astra Intelligence Agent",
        "description": "Read-only discovery surface for Empire market, opportunity and growth intelligence.",
        "version": "0.1.0",
        "provider": {"organization": "Empire AI", "url": base},
        "supportedInterfaces": [{
            "url": f"{base}/a2a/v1",
            "protocolBinding": "HTTP+JSON",
            "protocolVersion": "1.0",
        }],
        "capabilities": {"streaming": False, "pushNotifications": False, "extendedAgentCard": False},
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["application/json", "text/plain"],
        "skills": [{
            "id": "empire.agent-web.discovery",
            "name": "Empire Intelligence Discovery",
            "description": "Discover public read-only Empire intelligence capabilities and their schemas.",
            "tags": tags,
            "examples": ["What market intelligence can Empire provide?", "List your SEO, AEO and GEO tools."],
        }],
    }
