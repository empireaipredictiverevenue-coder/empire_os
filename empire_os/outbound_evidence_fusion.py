"""Fuse independent deliverability evidence with conflict and staleness handling."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping


CRITICAL_BOOLEAN_SIGNALS = {
    "spf_aligned",
    "dkim_aligned",
    "dmarc_valid",
    "tls_ready",
    "dns_authority_owned",
}


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fuse_evidence(
    rows: Iterable[Mapping[str, Any]],
    *,
    now: datetime | None = None,
    max_age_hours: int = 24,
    numeric_tolerance: float = 0.05,
) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = current - timedelta(hours=max_age_hours)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stale: dict[str, int] = defaultdict(int)

    for raw in rows:
        row = dict(raw)
        signal = str(row.get("signal") or "").strip()
        source = str(row.get("source") or "").strip()
        observed_at = _parse_time(row.get("observed_at"))
        if not signal or not source or observed_at is None:
            continue

        if observed_at < cutoff:
            stale[signal] += 1
            continue

        confidence = max(
            0.0,
            min(1.0, float(row.get("confidence") if row.get("confidence") is not None else 1.0)),
        )
        grouped[signal].append({
            "value": row.get("value"),
            "source": source,
            "confidence": confidence,
            "observed_at": observed_at.isoformat(),
        })

    signals: dict[str, dict[str, Any]] = {}
    conflicts: list[str] = []
    unknown: list[str] = []

    all_signals = set(grouped) | set(stale)
    for signal in sorted(all_signals):
        evidence = grouped.get(signal, [])
        if not evidence:
            signals[signal] = {
                "status": "STALE",
                "value": None,
                "sources": [],
                "stale_observations": stale.get(signal, 0),
                "confidence": 0.0,
            }
            unknown.append(signal)
            continue

        values = [item["value"] for item in evidence]
        sources = sorted({item["source"] for item in evidence})
        weights = [item["confidence"] for item in evidence]
        total_weight = sum(weights) or 1.0

        if all(isinstance(value, bool) for value in values):
            unique = set(values)
            if len(unique) == 1:
                status = "CONSENSUS"
                value = values[0]
                confidence = sum(weights) / len(weights)
            else:
                status = "CONFLICT"
                true_weight = sum(
                    item["confidence"]
                    for item in evidence
                    if item["value"] is True
                )
                false_weight = sum(
                    item["confidence"]
                    for item in evidence
                    if item["value"] is False
                )
                value = True if true_weight > false_weight else False if false_weight > true_weight else None
                confidence = abs(true_weight - false_weight) / total_weight
                conflicts.append(signal)

        elif all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
            weighted = sum(
                float(item["value"]) * item["confidence"]
                for item in evidence
            ) / total_weight
            spread = max(float(v) for v in values) - min(float(v) for v in values)
            if spread > numeric_tolerance:
                status = "CONFLICT"
                conflicts.append(signal)
            else:
                status = "CONSENSUS"
            value = weighted
            confidence = sum(weights) / len(weights)

        else:
            normalized = {str(value) for value in values}
            if len(normalized) == 1:
                status = "CONSENSUS"
                value = values[0]
                confidence = sum(weights) / len(weights)
            else:
                status = "CONFLICT"
                value = None
                confidence = 0.0
                conflicts.append(signal)

        signals[signal] = {
            "status": status,
            "value": value,
            "sources": sources,
            "stale_observations": stale.get(signal, 0),
            "confidence": round(confidence, 4),
        }

    critical_conflicts = sorted(
        set(conflicts).intersection(CRITICAL_BOOLEAN_SIGNALS)
    )

    return {
        "signals": signals,
        "conflicts": sorted(conflicts),
        "critical_conflicts": critical_conflicts,
        "unknown_or_stale": sorted(unknown),
        "posture": "INVESTIGATE" if critical_conflicts else "OBSERVE" if conflicts else "CONSENSUS",
        "mutation_authorized": False,
    }
