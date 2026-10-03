"""Canonical benchmark evidence adapter for Node Economic Scheduler.

This layer converts verified matched benchmark evidence into NodePerformance
records. It never grants execution or production authority.

Important cost semantics:
local models currently have no external per-call API fee, therefore the
scheduler marginal external API cost is recorded as GBP 0.00. Total
infrastructure, electricity, depreciation, hosting and opportunity costs remain
explicitly unknown and must not be interpreted as zero.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
import json

from empire_os.node_economic_scheduler import NodePerformance


RECEIPT_SCHEMA_VERSION = (
    "empire-node-performance-receipt-v1"
)

DEFAULT_MAX_AGE_SECONDS = 7 * 24 * 60 * 60

MARGINAL_COST_BASIS = (
    "local_external_api_fee_zero;"
    "infrastructure_cost_excluded"
)


MODEL_NODE_IDS: dict[
    tuple[str, str],
    str,
] = {
    (
        "llamacpp",
        "qwen2.5-coder:1.5b",
    ): "qwen25-coder-1_5b",
    (
        "ollama",
        "qwen2.5-coder:7b",
    ): "ollama-qwen25-coder-7b",
    (
        "ollama",
        "qwen2.5-coder:14b",
    ): "ollama-qwen25-coder-14b",
    (
        "ollama",
        "qwen3-coder:30b",
    ): "ollama-qwen3-coder-30b",
}


@dataclass(frozen=True)
class NodePerformanceReceipt:
    receipt_schema_version: str

    node_id: str
    benchmark_candidate_id: str

    provider: str
    model: str

    workload_version: str

    source_sha256: str
    source_commit: str | None

    observed_at: str
    source_time_basis: str

    matched_sample_count: int

    quality: float
    reliability: float
    latency_ms: float

    marginal_cost_gbp: float
    marginal_cost_basis: str

    infrastructure_cost_known: bool

    benchmark_verified: bool

    verified_outcome_score: float | None
    economic_memory_verified: bool

    production_authority: bool
    execution_authority: str

    def to_node_performance(
        self,
    ) -> NodePerformance:
        return NodePerformance(
            node_id=self.node_id,
            quality=self.quality,
            reliability=self.reliability,
            latency_ms=self.latency_ms,
            marginal_cost_gbp=(
                self.marginal_cost_gbp
            ),
            verified_outcome_score=(
                self.verified_outcome_score
            ),
            matched_sample_count=(
                self.matched_sample_count
            ),
            benchmark_verified=(
                self.benchmark_verified
            ),
            economic_memory_verified=(
                self.economic_memory_verified
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_time(
    value: str,
) -> datetime:
    text = str(value or "").strip()

    if not text:
        raise ValueError(
            "benchmark observation timestamp required"
        )

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    dt = datetime.fromisoformat(text)

    if dt.tzinfo is None:
        raise ValueError(
            "benchmark timestamp must be timezone aware"
        )

    return dt.astimezone(timezone.utc)


def _source_time(
    *,
    payload: Mapping[str, Any],
    path: Path,
) -> tuple[datetime, str]:
    for key in (
        "observed_at",
        "updated_at",
        "completed_at",
    ):
        value = payload.get(key)

        if value:
            return (
                _parse_time(str(value)),
                key,
            )

    # File mtime is observable evidence, not an inferred
    # benchmark time. Preserve the basis explicitly.
    return (
        datetime.fromtimestamp(
            path.stat().st_mtime,
            tz=timezone.utc,
        ),
        "file_mtime",
    )


def _number(
    value: Any,
    *,
    name: str,
) -> float:
    if isinstance(value, bool):
        raise ValueError(
            f"{name} must be numeric"
        )

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{name} must be numeric"
        ) from exc

    return result


def load_benchmark_receipts(
    path: str | Path,
    *,
    source_commit: str | None = None,
    now: datetime | None = None,
    max_age_seconds: int = (
        DEFAULT_MAX_AGE_SECONDS
    ),
) -> dict[str, NodePerformanceReceipt]:
    source = Path(path)

    raw = source.read_bytes()

    payload = json.loads(
        raw.decode("utf-8")
    )

    if not isinstance(payload, Mapping):
        raise ValueError(
            "benchmark payload must be an object"
        )

    if payload.get("complete") is not True:
        raise ValueError(
            "benchmark evidence incomplete"
        )

    completed = int(
        payload.get(
            "completed_observation_count",
            -1,
        )
    )

    expected = int(
        payload.get(
            "expected_observation_count",
            -2,
        )
    )

    if completed <= 0 or completed != expected:
        raise ValueError(
            "benchmark observation count incomplete"
        )

    if (
        payload.get("production_authority")
        is not False
    ):
        raise ValueError(
            "benchmark authority boundary invalid"
        )

    if payload.get("route_changed") is not False:
        raise ValueError(
            "benchmark changed production routing"
        )

    if (
        payload.get("winner_promoted")
        is not False
    ):
        raise ValueError(
            "benchmark performed model promotion"
        )

    if (
        payload.get("execution_authority")
        != "none"
    ):
        raise ValueError(
            "benchmark execution authority invalid"
        )

    observed_at, time_basis = _source_time(
        payload=payload,
        path=source,
    )

    current = (
        now.astimezone(timezone.utc)
        if now is not None
        else datetime.now(timezone.utc)
    )

    age = (
        current - observed_at
    ).total_seconds()

    if age < -300:
        raise ValueError(
            "benchmark timestamp is in the future"
        )

    if age > max_age_seconds:
        raise ValueError(
            "benchmark evidence is stale"
        )

    reports = payload.get("reports")

    if not isinstance(reports, Mapping):
        raise ValueError(
            "benchmark reports required"
        )

    source_hash = sha256(raw).hexdigest()

    workload_version = str(
        payload.get("schema_version")
        or "empire-local-escalation-v2"
    )

    receipts: dict[
        str,
        NodePerformanceReceipt,
    ] = {}

    for candidate_id, report in (
        reports.items()
    ):
        if not isinstance(report, Mapping):
            raise ValueError(
                "benchmark report must be an object"
            )

        provider = str(
            report.get("provider")
            or ""
        ).strip()

        model = str(
            report.get("model")
            or ""
        ).strip()

        identity = (
            provider,
            model,
        )

        node_id = MODEL_NODE_IDS.get(
            identity
        )

        if node_id is None:
            raise ValueError(
                "unrecognized benchmark model identity: "
                f"{provider}:{model}"
            )

        quality = _number(
            report.get("mean_coverage"),
            name="mean_coverage",
        )

        reliability = _number(
            report.get("reliability"),
            name="reliability",
        )

        latency_ms = _number(
            report.get("mean_latency_ms"),
            name="mean_latency_ms",
        )

        sample_count = int(
            report.get("sample_count")
            or 0
        )

        benchmark_verified = (
            report.get("benchmark_verified")
            is True
        )

        if not 0 <= quality <= 1:
            raise ValueError(
                "quality outside [0,1]"
            )

        if not 0 <= reliability <= 1:
            raise ValueError(
                "reliability outside [0,1]"
            )

        if latency_ms < 0:
            raise ValueError(
                "latency must be nonnegative"
            )

        if sample_count <= 0:
            raise ValueError(
                "sample_count must be positive"
            )

        if not benchmark_verified:
            raise ValueError(
                "benchmark report not verified"
            )

        receipt = NodePerformanceReceipt(
            receipt_schema_version=(
                RECEIPT_SCHEMA_VERSION
            ),
            node_id=node_id,
            benchmark_candidate_id=str(
                candidate_id
            ),
            provider=provider,
            model=model,
            workload_version=(
                workload_version
            ),
            source_sha256=source_hash,
            source_commit=source_commit,
            observed_at=(
                observed_at.isoformat()
            ),
            source_time_basis=time_basis,
            matched_sample_count=(
                sample_count
            ),
            quality=quality,
            reliability=reliability,
            latency_ms=latency_ms,

            # This is specifically the external
            # API-call marginal fee.
            marginal_cost_gbp=0.0,
            marginal_cost_basis=(
                MARGINAL_COST_BASIS
            ),

            # Deliberately not invented.
            infrastructure_cost_known=False,

            benchmark_verified=True,

            # Benchmark success is NOT a verified
            # commercial/revenue outcome.
            verified_outcome_score=None,
            economic_memory_verified=False,

            production_authority=False,
            execution_authority="none",
        )

        if node_id in receipts:
            raise ValueError(
                f"duplicate receipt node: {node_id}"
            )

        receipts[node_id] = receipt

    if not receipts:
        raise ValueError(
            "no benchmark receipts produced"
        )

    return receipts


def performance_map(
    receipts: Mapping[
        str,
        NodePerformanceReceipt,
    ],
) -> dict[str, NodePerformance]:
    return {
        node_id: receipt.to_node_performance()
        for node_id, receipt
        in receipts.items()
    }


def receipt_snapshot(
    receipts: Mapping[
        str,
        NodePerformanceReceipt,
    ],
    *,
    source_path: str,
) -> dict[str, Any]:
    rows = [
        receipts[node_id].to_dict()
        for node_id in sorted(receipts)
    ]

    return {
        "schema_version":
            "empire-node-performance-snapshot-v1",
        "source_path": source_path,
        "receipt_count": len(rows),
        "receipts": rows,

        "cost_semantics": {
            "marginal_cost_gbp":
                "external per-call API fee only",
            "infrastructure_cost_known":
                False,
            "infrastructure_cost_inferred":
                False,
        },

        "economic_memory_verified": False,
        "verified_commercial_outcomes_used":
            False,

        "production_authority": False,
        "route_changed": False,
        "execution_authority": "none",
    }
