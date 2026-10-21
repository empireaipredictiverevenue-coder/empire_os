"""Private proof of one ACTUAL Jev shadow decision. Never invokes a model.

A validated owner receipt is different from JEV readiness's zero evaluated
*labelled cases*. This reader cannot send an API call or change permissions.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

from .jev_live_pilot import LABELS, MAX_COST_USD, MAX_INPUT_TOKENS

RECEIPT = Path(
    "/home/ubuntu/empire_releases/search_jev_owner_receipts_20261021/"
    "seo_jev_one_shot_receipt_v1.json"
)
SCHEMA = "empire.search.jev_one_shot_private_receipt_review.v1"


class JevReceiptUnavailable(ValueError):
    pass


def _prob(v: Any) -> bool:
    return type(v) in (float, int) and math.isfinite(v) and 0 <= v <= 1


def review_jev_private_pilot_receipt(path: Path = RECEIPT) -> dict[str, Any]:
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_size > 16000
            or path.stat().st_size < 160
            or path.stat().st_mode & 0o077):
        raise JevReceiptUnavailable("OWNER_JEV_RECEIPT_MISSING_OR_UNSAFE")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError, OSError) as exc:
        raise JevReceiptUnavailable("OWNER_JEV_RECEIPT_UNREADABLE") from exc
    if (not isinstance(raw, Mapping)
            or raw.get("schema_version") != "empire.search.jev_real_one_shot_result.v1"
            or raw.get("provider_key") != "openrouter_typesafe_jev"
            or not isinstance(raw.get("model"), str)
            or not raw["model"].startswith("typesafe/jev-1.13")
            or raw.get("actual_jev_inference_calls") != 1
            or raw.get("jev_decision_observed") is not True
            or raw.get("decision_label") not in LABELS
            or not _prob(raw.get("decision_confidence"))
            or not _prob(raw.get("review_priority_confidence"))
            or not _prob(raw.get("human_review_yes_probability"))
            or type(raw.get("review_priority_score")) not in (int, float)
            or not math.isfinite(raw["review_priority_score"])
            or not 0 <= raw["review_priority_score"] <= 3
            or type(raw.get("input_tokens")) is not int
            or not 0 < raw["input_tokens"] <= MAX_INPUT_TOKENS
            or type(raw.get("cost_usd_reported")) not in (int, float)
            or not math.isfinite(raw["cost_usd_reported"])
            or not 0 <= raw["cost_usd_reported"] <= MAX_COST_USD
            or not isinstance(raw.get("source_sha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", raw["source_sha256"])
            or raw.get("ground_truth_or_accuracy_verified") is not False
            or raw.get("decision_controls_live_traffic") is not False
            or raw.get("buyer_or_personal_data_sent") is not False
            or raw.get("database_writes") is not False
            or raw.get("publishing_authorized") is not False
            or raw.get("buyer_routing_authorized") is not False
            or raw.get("execution_authority") != "NONE"):
        raise JevReceiptUnavailable("OWNER_JEV_RECEIPT_INCONSISTENT")
    probabilities = raw.get("decision_probabilities")
    if (not isinstance(probabilities, Mapping)
            or set(probabilities) != set(LABELS)
            or any(not _prob(v) for v in probabilities.values())
            or abs(sum(probabilities.values()) - 1) > 0.03):
        raise JevReceiptUnavailable("OWNER_JEV_PROBABILITIES_INVALID")
    # Only explicit scalar allowlist; never expose arbitrary future receipt keys.
    return {
        "schema_version": SCHEMA,
        "mode": "ONE_SHOT_SHADOW_ONLY",
        "provider_key": "openrouter_typesafe_jev",
        "model": raw["model"],
        "actual_jev_inference_calls_observed": 1,
        "decision_label": raw["decision_label"],
        "decision_confidence": raw["decision_confidence"],
        "human_review_yes_probability": raw["human_review_yes_probability"],
        "investigation_priority_score": raw["review_priority_score"],
        "usage_input_tokens": raw["input_tokens"],
        "usage_cost_usd": raw["cost_usd_reported"],
        "source_sha256": raw["source_sha256"],
        "receipt_filesystem_timestamp_utc": datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc).isoformat(),
        "source_scope": "FIRST_PARTY_GSC_PAGE_SAMPLE_AGGREGATES_ONLY",
        "accuracy_or_ground_truth_verified": False,
        "independent_eval_cases_ready": 0,
        "provider_enabled_for_unattended_runs": False,
        "new_provider_calls_triggered": 0,
        "replay_billing_authorized": False,
        "publication_authorized": False,
        "outreach_or_payment_authorized": False,
        "external_requests_performed_by_review": False,
        "database_writes": False,
        "execution_authority": "NONE",
    }
