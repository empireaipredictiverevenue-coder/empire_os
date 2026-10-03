"""Matched shadow benchmarking for Empire Hybrid Compute.

This module executes only explicitly supplied benchmark candidates. It does not
modify ModelRouter policy, production model health, Economic Memory or business
state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import inspect
import json
from time import perf_counter
from typing import Any, Iterable, Mapping

from empire_os.model_matched_benchmark import score_case


SCHEMA_VERSION = "empire.hybrid_compute.benchmark.v3"


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    task: str
    prompt: str
    required_groups: tuple[tuple[str, ...], ...]
    max_tokens: int = 192

    def fingerprint(self) -> str:
        payload = {
            "case_id": self.case_id,
            "task": self.task,
            "prompt": self.prompt,
            "required_groups": self.required_groups,
            "max_tokens": self.max_tokens,
        }

        return sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True)
class CandidateIdentity:
    model_id: str
    provider: str
    model: str
    deployment: str
    cost_known: bool
    estimated_cost: float | None


def candidate_identity(
    spec: Any,
    *,
    estimated_cost: float | None = None,
) -> CandidateIdentity:
    cost_known_method = getattr(
        spec,
        "cost_known",
        None,
    )

    cost_known = False

    if callable(cost_known_method):
        try:
            cost_known = (
                cost_known_method() is True
            )
        except Exception:
            cost_known = False

    return CandidateIdentity(
        model_id=str(
            getattr(spec, "model_id", "")
            or "unknown"
        ),
        provider=str(
            getattr(spec, "provider", "")
            or "unknown"
        ),
        model=str(
            getattr(spec, "model", "")
            or "unknown"
        ),
        deployment=str(
            getattr(spec, "deployment", "")
            or "unknown"
        ),
        cost_known=cost_known,
        estimated_cost=(
            float(estimated_cost)
            if cost_known
            and isinstance(
                estimated_cost,
                (int, float),
            )
            else None
        ),
    )


def _provider_error(output: str) -> str | None:
    text = str(output or "").strip()

    if not text:
        return "empty_response"

    try:
        payload = json.loads(text)
    except (
        json.JSONDecodeError,
        TypeError,
    ):
        return None

    if (
        isinstance(payload, Mapping)
        and payload.get("error")
    ):
        return str(payload["error"])

    return None


def _chat_kwargs(
    client: Any,
    *,
    messages: list[dict[str, str]],
    system: str,
    max_tokens: int,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "messages": messages,
        "system": system,
        "temperature": 0.0,
    }

    try:
        signature = inspect.signature(
            client.chat
        )
    except (
        TypeError,
        ValueError,
    ):
        signature = None

    if (
        signature is not None
        and "max_tokens"
        in signature.parameters
    ):
        kwargs["max_tokens"] = max_tokens

    return kwargs


def execute_candidate(
    *,
    client: Any,
    candidate: CandidateIdentity,
    case: BenchmarkCase,
) -> dict[str, Any]:
    """Run one candidate on one safe benchmark case."""

    system = (
        "EmpireOS internal matched benchmark only. "
        "Do not use external tools. "
        "Do not invent performed actions. "
        "Answer concisely using the supplied task only."
    )

    messages = [
        {
            "role": "user",
            "content": case.prompt,
        }
    ]

    started = perf_counter()

    try:
        output = client.chat(
            **_chat_kwargs(
                client,
                messages=messages,
                system=system,
                max_tokens=case.max_tokens,
            )
        )

        latency_ms = (
            perf_counter() - started
        ) * 1000

    except Exception as exc:
        latency_ms = (
            perf_counter() - started
        ) * 1000

        return {
            "schema_version": SCHEMA_VERSION,
            "case_id": case.case_id,
            "case_fingerprint": (
                case.fingerprint()
            ),
            "candidate": asdict(candidate),
            "ok": False,
            "failure": (
                f"{type(exc).__name__}:"
                f"{str(exc)[:160]}"
            ),
            "latency_ms": round(
                latency_ms,
                3,
            ),
            "coverage": 0.0,
            "covered_groups": 0,
            "total_groups": len(
                case.required_groups
            ),
            "output_nonempty": False,
            "output_chars": 0,
            "output_sha256": None,
            "raw_output_persisted": False,
        }

    output = str(output or "")
    failure = _provider_error(output)

    score = score_case(
        case_id=case.case_id,
        output=output,
        required_groups=(
            case.required_groups
        ),
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case.case_id,
        "case_fingerprint": (
            case.fingerprint()
        ),
        "candidate": asdict(candidate),
        "ok": failure is None,
        "failure": failure,
        "latency_ms": round(
            latency_ms,
            3,
        ),
        "coverage": score.coverage,
        "covered_groups": (
            score.covered_groups
        ),
        "total_groups": (
            score.total_groups
        ),
        "output_nonempty": (
            score.output_nonempty
        ),
        "output_chars": len(output),
        "output_sha256": (
            sha256(
                output.encode("utf-8")
            ).hexdigest()
            if output
            else None
        ),
        "raw_output_persisted": False,
    }


def summarize_runs(
    runs: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = [
        dict(row)
        for row in runs
    ]

    if not rows:
        return {
            "sample_count": 0,
            "successful_calls": 0,
            "mean_coverage": None,
            "mean_latency_ms": None,
        }

    successful = [
        row
        for row in rows
        if row.get("ok") is True
    ]

    return {
        "sample_count": len(rows),
        "successful_calls": len(
            successful
        ),
        "mean_coverage": round(
            sum(
                float(
                    row.get(
                        "coverage",
                        0.0,
                    )
                )
                for row in rows
            )
            / len(rows),
            6,
        ),
        "mean_latency_ms": round(
            sum(
                float(
                    row["latency_ms"]
                )
                for row in rows
            )
            / len(rows),
            3,
        ),
        "all_successful": (
            len(successful)
            == len(rows)
        ),
    }
