"""Persistent model/provider health derived from LLM gateway receipts."""
from __future__ import annotations

import json
import math
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any


RECEIPT_PATH = Path(os.environ.get(
    "LLM_RECEIPT_PATH",
    "/srv/empire_os/runtime/llm/receipts.jsonl",
))

HEALTH_PATH = Path(os.environ.get(
    "LLM_HEALTH_PATH",
    "/srv/empire_os/runtime/llm/model_health.json",
))

WINDOW = int(os.environ.get("LLM_HEALTH_WINDOW", "50"))


class ModelHealth:
    """Track recent success/failure/latency per provider/model."""

    def __init__(self) -> None:
        self.samples: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=WINDOW)
        )
        self.state: dict[str, dict[str, Any]] = {}

    def _key(self, provider: str, model: str) -> str:
        return f"{provider}:{model}"

    def load_receipts(self) -> None:
        if not RECEIPT_PATH.exists():
            return

        try:
            with RECEIPT_PATH.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    provider = str(event.get("provider") or "")
                    model = str(event.get("model") or "")
                    if not provider or not model:
                        continue

                    key = self._key(provider, model)
                    self.samples[key].append(event)
        except OSError:
            return

    def calculate(self) -> dict[str, dict[str, Any]]:
        now = time.time()
        result = {}

        for key, samples in self.samples.items():
            total = len(samples)
            successes = sum(1 for x in samples if x.get("ok") is True)
            failures = total - successes

            latencies = [
                float(x["latency_ms"])
                for x in samples
                if isinstance(x.get("latency_ms"), (int, float))
                and math.isfinite(float(x["latency_ms"]))
            ]

            success_rate = successes / total if total else 0.0
            failure_rate = failures / total if total else 0.0
            avg_latency = (
                sum(latencies) / len(latencies)
                if latencies else None
            )

            recent = list(samples)[-10:]
            recent_failures = sum(
                1 for x in recent if x.get("ok") is not True
            )

            # Temporary circuit-breaker state.
            if total == 0:
                status = "unknown"
            elif recent_failures >= 5:
                status = "degraded"
            elif success_rate < 0.80:
                status = "degraded"
            elif success_rate >= 0.95:
                status = "healthy"
            else:
                status = "warning"

            result[key] = {
                "provider": key.split(":", 1)[0],
                "model": key.split(":", 1)[1],
                "samples": total,
                "successes": successes,
                "failures": failures,
                "success_rate": round(success_rate, 4),
                "failure_rate": round(failure_rate, 4),
                "avg_latency_ms": (
                    round(avg_latency, 1)
                    if avg_latency is not None else None
                ),
                "recent_failures_10": recent_failures,
                "status": status,
                "updated_at": now,
            }

        self.state = result
        return result

    def save(self) -> None:
        HEALTH_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = HEALTH_PATH.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "schema_version": "model_health.v1",
                    "generated_at": time.time(),
                    "models": self.state,
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        tmp.replace(HEALTH_PATH)


if __name__ == "__main__":
    h = ModelHealth()
    h.load_receipts()
    state = h.calculate()
    h.save()

    print("MODEL HEALTH: OK")
    print("TRACKED:", len(state))

    for value in state.values():
        print(
            f'{value["provider"]}/{value["model"]} '
            f'status={value["status"]} '
            f'success={value["success_rate"]:.2f} '
            f'failures={value["failures"]} '
            f'latency_ms={value["avg_latency_ms"]}'
        )
