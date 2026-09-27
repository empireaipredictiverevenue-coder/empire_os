"""Read-only Founder Console commercial funnel snapshot."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from empire_os.runtime_env import load_runtime_env


SNAPSHOT_PATH = Path(
    "/srv/empire_os/runtime/commercial_funnel/latest.json"
)


def _clean_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, int] = {}
    for key, raw in value.items():
        try:
            out[str(key)] = int(raw or 0)
        except (TypeError, ValueError):
            out[str(key)] = 0
    return out


def _commercial_stage(
    counts: Mapping[str, int],
) -> tuple[str, str]:
    if int(counts.get("recognized_revenue_events", 0)) > 0:
        return "recognized_revenue", "revenue_observed"
    if int(counts.get("verified_payment_evidence", 0)) > 0:
        return "verified_payment", "await_fulfilment_or_recognition"
    if int(counts.get("payment_requests", 0)) > 0:
        return "payment_request", "await_verified_payment"
    if int(counts.get("commercial_terms_approved", 0)) > 0:
        return "terms_approved", "await_buyer_acceptance_or_payment"
    if int(counts.get("commercial_terms_reviews", 0)) > 0:
        return "terms_review", "terms_governance"
    if int(counts.get("closer_cases", 0)) > 0:
        return "closer", "advance_genuine_conversation"
    if int(counts.get("commercial_replies", 0)) > 0:
        return "buyer_conversation", "open_or_advance_closer"
    if int(counts.get("outbound_delivered", 0)) > 0:
        return "outbound_delivered", "await_genuine_buyer_reply"
    if int(counts.get("buyer_reviews_approved", 0)) > 0:
        return "approved_buyer", "propose_governed_outbound"
    if int(counts.get("prospect_acquisitions", 0)) > 0:
        return "acquisition", "qualify_and_review"
    return "empty", "acquire_real_prospects"


def normalize_funnel_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    counts = _clean_counts(raw.get("counts"))
    stage, next_event = _commercial_stage(counts)
    return {
        "schema_version": str(
            raw.get("schema_version")
            or "empire.founder_commercial_funnel.v1"
        ),
        "mode": "OBSERVE",
        "generated_at": raw.get("generated_at"),
        "counts": counts,
        "outbound_status_counts": _clean_counts(
            raw.get("outbound_status_counts")
        ),
        "reply_classification_counts": _clean_counts(
            raw.get("reply_classification_counts")
        ),
        "current_stage": stage,
        "next_event": next_event,
        "recognized_revenue_cents": int(
            raw.get("recognized_revenue_cents") or 0
        ),
        "realized_margin_cents": int(
            raw.get("realized_margin_cents") or 0
        ),
        "actual_revenue": raw.get("actual_revenue") is True,
        "execution_authority": "none",
    }


def fetch_founder_commercial_funnel_postgres(
    dsn: str,
    *,
    connect_factory: Callable | None = None,
) -> dict[str, Any]:
    clean = str(dsn or "").strip()
    if not clean:
        raise ValueError("materializer database dsn required")
    if connect_factory is None:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is required for commercial funnel refresh"
            ) from exc
        connect_factory = psycopg.connect

    try:
        with connect_factory(clean) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET LOCAL ROLE empire_intelligence_materializer"
                )
                cursor.execute(
                    "SELECT public.get_founder_commercial_funnel()"
                )
                row = cursor.fetchone()
    except Exception as exc:
        raise RuntimeError(
            "restricted commercial funnel read failed"
        ) from exc

    raw = row[0] if row else {}
    if not isinstance(raw, Mapping):
        raise ValueError("commercial funnel RPC returned invalid payload")
    return normalize_funnel_payload(raw)


def write_funnel_snapshot(
    payload: Mapping[str, Any],
    path: str | Path | None = None,
) -> Path:
    target = Path(path or SNAPSHOT_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(tmp, 0o600)
    tmp.replace(target)
    os.chmod(target, 0o600)
    return target


def build_funnel_runtime(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "runtime/commercial_funnel/latest.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "available": False,
            "schema_version": "empire.founder_commercial_funnel.v1",
            "mode": "OBSERVE",
            "counts": {},
            "current_stage": "unavailable",
            "next_event": "refresh_commercial_funnel",
            "recognized_revenue_cents": 0,
            "realized_margin_cents": 0,
            "actual_revenue": False,
            "execution_authority": "none",
        }
    return {"available": True, **normalize_funnel_payload(raw)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        default=os.getenv("EMPIRE_REPO_ROOT", "/srv/empire_os"),
    )
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    if not args.refresh:
        print(json.dumps(
            build_funnel_runtime(root),
            indent=2,
            sort_keys=True,
        ))
        return 0

    env = load_runtime_env(
        root / "runtime/secrets/intelligence_materializer.env",
        required=("EMPIRE_INTELLIGENCE_MATERIALIZER_DSN",),
    )
    payload = fetch_founder_commercial_funnel_postgres(
        env["EMPIRE_INTELLIGENCE_MATERIALIZER_DSN"]
    )
    path = write_funnel_snapshot(
        payload,
        root / "runtime/commercial_funnel/latest.json",
    )
    print(json.dumps(
        {**payload, "snapshot_path": str(path)},
        indent=2,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
