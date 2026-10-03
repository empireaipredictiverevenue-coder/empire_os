"""Fail-closed activation readiness for Recall-backed Digital Avatar SHADOW."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping
from urllib.parse import urlparse


_ALLOWED_REGIONS = {
    "us-west-2",
    "us-east-1",
    "eu-central-1",
    "ap-northeast-1",
}


@dataclass(frozen=True)
class RecallShadowReadiness:
    ready_for_activation: bool
    blockers: tuple[str, ...]
    region: str | None
    public_realtime_url: str | None
    api_key_configured: bool
    workspace_verification_configured: bool
    public_gateway_route_ready: bool
    webhook_unit_ready: bool
    worker_unit_ready: bool
    tunnel_route_ready: bool
    live_join_execution: bool = False
    speech_execution: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_recall_shadow_readiness(
    *,
    config: Mapping[str, Any],
    public_gateway_route_ready: bool,
    webhook_unit_ready: bool,
    worker_unit_ready: bool,
    tunnel_route_ready: bool,
) -> RecallShadowReadiness:
    region = str(config.get("RECALL_REGION") or "").strip()
    api_key = str(config.get("RECALL_API_KEY") or "").strip()
    secret = str(
        config.get("RECALL_WORKSPACE_VERIFICATION_SECRET") or ""
    ).strip()
    public_url = str(
        config.get(
            "EMPIRE_RECALL_PUBLIC_REALTIME_URL",
            "https://empire-ai.co.uk/v1/providers/recall/realtime",
        )
        or ""
    ).strip()

    blockers: list[str] = []
    if not region:
        blockers.append("recall_region_missing")
    elif region not in _ALLOWED_REGIONS:
        blockers.append("recall_region_invalid")
    if not api_key:
        blockers.append("recall_api_key_missing")
    if not secret:
        blockers.append("recall_workspace_verification_secret_missing")
    elif not secret.startswith("whsec_"):
        blockers.append("recall_workspace_verification_secret_invalid")

    parsed = urlparse(public_url)
    if parsed.scheme != "https" or not parsed.netloc:
        blockers.append("public_realtime_https_url_invalid")


    if not public_gateway_route_ready:
        blockers.append("public_gateway_recall_route_not_ready")
    if not webhook_unit_ready:
        blockers.append("recall_webhook_unit_not_ready")
    if not worker_unit_ready:
        blockers.append("recall_shadow_worker_unit_not_ready")
    if not tunnel_route_ready:
        blockers.append("public_tunnel_route_not_ready")

    unique = tuple(sorted(set(blockers)))
    return RecallShadowReadiness(
        ready_for_activation=not unique,
        blockers=unique,
        region=region or None,
        public_realtime_url=public_url or None,
        api_key_configured=bool(api_key),
        workspace_verification_configured=bool(
            secret and secret.startswith("whsec_")
        ),
        public_gateway_route_ready=public_gateway_route_ready,
        webhook_unit_ready=webhook_unit_ready,
        worker_unit_ready=worker_unit_ready,
        tunnel_route_ready=tunnel_route_ready,
    )
