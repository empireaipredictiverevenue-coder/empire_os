"""Runtime executor for Autonomous Commercial Progression.

Only reversible internal commercial progression is permitted here.

Explicitly excluded:
- outbound email
- LinkedIn send
- phone calls
- binding terms
- payment/funds
- revenue recognition
"""

from __future__ import annotations

from empire_os.outbound_runtime_bridge import outbound_advisory_from_progression

from collections import defaultdict
from datetime import datetime, timezone
from functools import partial
import json
from pathlib import Path
from typing import Any, Mapping
import urllib.parse

from empire_os.autonomous_commercial_progression import (
    AUTO_INTERNAL_ACTIONS,
    ExecutionAuthority,
    authority_state,
    authority_blocker,
    build_progression_plan,
    execute_one_internal_progression,
    write_progression_plan,
)
from empire_os.buyer_review_materializer import (
    run_buyer_review_materializer,
)
from empire_os.buyer_scout_canonical_person_bridge import materialize_buyer_scout_identity
from empire_os.buyer_scout_acp_adapter import (
    run_precanonical_admission,
)
from empire_os.source_buyer_review_bridge import (
    _source_probe,
)
from empire_os.sb import request_json


ROOT = Path("/srv/empire_os")

RUNTIME = (
    ROOT
    / "runtime"
    / "autonomous_commercial_progression"
)

LATEST_RECEIPT = (
    RUNTIME
    / "receipt_latest.json"
)

ATTEMPT_LOG = (
    RUNTIME
    / "attempts.jsonl"
)

STRATEGY_MEMORY = (
    RUNTIME
    / "strategy_performance_latest.json"
)

BLOCKED_COOLDOWN_SECONDS = 6 * 60 * 60
ADVANCED_COOLDOWN_SECONDS = 30 * 60


def _now() -> datetime:
    return datetime.now(
        timezone.utc
    )


def _text(value: Any) -> str:
    return str(
        value or ""
    ).strip()


def _write_json(
    path: Path,
    payload: Mapping[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = path.with_suffix(
        path.suffix + ".tmp"
    )

    tmp.write_text(
        json.dumps(
            dict(payload),
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    tmp.replace(path)


def _read_attempts(
    *,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    if not ATTEMPT_LOG.exists():
        return []

    rows = []

    for raw in ATTEMPT_LOG.read_text(
        encoding="utf-8"
    ).splitlines()[-limit:]:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue

        if isinstance(
            value,
            dict,
        ):
            rows.append(value)

    return rows


def _append_attempt(
    payload: Mapping[str, Any],
) -> None:
    ATTEMPT_LOG.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with ATTEMPT_LOG.open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(
            json.dumps(
                dict(payload),
                sort_keys=True,
                default=str,
            )
            + "\n"
        )


def _same_action(
    attempt: Mapping[str, Any],
    action: Mapping[str, Any],
) -> bool:
    return (
        _text(
            attempt.get("action")
        )
        == _text(
            action.get(
                "recommended_action"
            )
        )
        and _text(
            attempt.get("prospect_id")
        )
        == _text(
            action.get("prospect_id")
        )
        and _text(
            attempt.get("entity_id")
        )
        == _text(
            action.get("entity_id")
        )
    )


def _cooldown_active(
    action: Mapping[str, Any],
    attempts: list[dict[str, Any]],
) -> bool:
    matches = [
        row
        for row in attempts
        if _same_action(
            row,
            action,
        )
    ]

    if not matches:
        return False

    last = matches[-1]

    timestamp = _text(
        last.get("generated_at")
    )

    if not timestamp:
        return False

    try:
        observed = (
            datetime.fromisoformat(
                timestamp.replace(
                    "Z",
                    "+00:00",
                )
            )
        )
    except ValueError:
        return False

    age = (
        _now() - observed
    ).total_seconds()

    status = _text(
        last.get("status")
    ).upper()

    if status.startswith(
        "ADVANCED"
    ):
        return (
            age
            < ADVANCED_COOLDOWN_SECONDS
        )

    if status in {
        "BLOCKED",
        "ERROR",
        "ALREADY_PROGRESSING",
    }:
        return (
            age
            < BLOCKED_COOLDOWN_SECONDS
        )

    return False


def filter_cooldowns(
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    attempts = _read_attempts()

    output = dict(snapshot)
    actions = []

    for raw in (
        snapshot.get("actions")
        or []
    ):
        if not isinstance(
            raw,
            Mapping,
        ):
            continue

        action = dict(raw)

        if _cooldown_active(
            action,
            attempts,
        ):
            continue

        actions.append(action)

    output["actions"] = actions

    return output



def _fetch_canonical_prospect(
    prospect_id: str,
) -> dict[str, Any] | None:
    """Fetch exactly one canonical prospect for bounded internal research."""

    query = urllib.parse.urlencode({
        "select": (
            "id,business_name,niche,metro,address,phone,"
            "website,buy_signal_score,status,notes,"
            "contact_name,contact_title,contact_source,"
            "contacted_status,created_at"
        ),
        "id": f"eq.{prospect_id}",
        "limit": 1,
    })

    rows = request_json(
        "GET",
        f"/rest/v1/prospects?{query}",
    ) or []

    if not isinstance(rows, list):
        raise ValueError(
            "canonical prospect projection must be list"
        )

    for row in rows:
        if isinstance(row, Mapping):
            return dict(row)

    return None


def _targeted_research_progression(
    action: Mapping[str, Any],
    *, mode: str = "AUTO_INTERNAL",
    execution_authority: ExecutionAuthority | None = None,
) -> dict[str, Any]:
    """Perform bounded first-party research without pretending review ran."""

    state = authority_state(mode, execution_authority)
    if not state["internal_mutation_authorized"]:
        return authority_blocker(mode, execution_authority)

    prospect_id = _text(
        action.get("prospect_id")
    )

    if not prospect_id:
        return {
            "status": "BLOCKED",
            "blocker":
                "canonical_prospect_id_missing",
            "recovery_strategy":
                "targeted_first_party_research_probe",
            "executor":
                "first_party_research",
            "internal_mutation_performed":
                False,
            "outbound_sent": False,
            "call_placed": False,
            "binding_terms_action": False,
            "payment_action": False,
            "verified_commercial_outcome":
                False,
        }

    row = _fetch_canonical_prospect(
        prospect_id
    )

    if row is None:
        return {
            "status": "BLOCKED",
            "blocker":
                "canonical_prospect_not_found",
            "recovery_strategy":
                "targeted_first_party_research_probe",
            "executor":
                "first_party_research",
            "internal_mutation_performed":
                False,
            "outbound_sent": False,
            "call_placed": False,
            "binding_terms_action": False,
            "payment_action": False,
            "verified_commercial_outcome":
                False,
        }

    identity = materialize_buyer_scout_identity(
        prospect_id=prospect_id, write_authorized=False,
        request_factory=request_json,
    )
    if identity.get("status") != "NO_BUYER_SCOUT_ACQUISITION":
        return _targeted_review_progression(action, mode=mode, execution_authority=execution_authority)

    probe = _source_probe(row)

    reason = _text(
        probe.get("rejection_reason")
    )

    review_ready = (
        probe.get("review_ready") is True
    )

    outreach_ready = (
        probe.get("outreach_ready") is True
    )

    # If bounded research discovers enough evidence,
    # reuse the canonical review materializer for the actual
    # governed internal write.
    if review_ready and outreach_ready:
        result = run_buyer_review_materializer(
            probe=lambda _row: probe,
            prospect_ids=[prospect_id],
            scan_limit=1,
            proposal_limit=1,
            probe_workers=1,
        )

        data = result.as_dict()

        proposed = int(
            data.get("proposed")
            or 0
        )

        if proposed > 0:
            return {
                "status":
                    "ADVANCED_REVIEW_PROPOSED",
                "blocker": None,
                "recovery_strategy":
                    "targeted_first_party_research_probe",
                "executor":
                    "first_party_research_then_review",
                "internal_mutation_performed":
                    True,
                "probe": probe,
                "materializer": data,
                "outbound_sent": False,
                "call_placed": False,
                "binding_terms_action": False,
                "payment_action": False,
                "verified_commercial_outcome":
                    False,
            }

        return {
            "status":
                "ADVANCED_EVIDENCE_DISCOVERED",
            "blocker": None,
            "recovery_strategy":
                "targeted_first_party_research_probe",
            "executor":
                "first_party_research",
            "internal_mutation_performed":
                False,
            "probe": probe,
            "materializer": data,
            "outbound_sent": False,
            "call_placed": False,
            "binding_terms_action": False,
            "payment_action": False,
            "verified_commercial_outcome":
                False,
        }

    blocker = (
        reason
        or "research_evidence_not_yet_sufficient"
    )

    return {
        "status": "BLOCKED",
        "blocker": blocker,
        "recovery_strategy":
            "targeted_first_party_research_probe",
        "executor":
            "first_party_research",
        "internal_mutation_performed":
            False,
        "probe": probe,
        "outbound_sent": False,
        "call_placed": False,
        "binding_terms_action": False,
        "payment_action": False,
        "verified_commercial_outcome":
            False,
    }


def _targeted_review_progression(
    action: Mapping[str, Any],
    *, mode: str = "AUTO_INTERNAL",
    execution_authority: ExecutionAuthority | None = None,
) -> dict[str, Any]:
    """Advance one existing canonical prospect through evidence/review."""

    state = authority_state(mode, execution_authority)
    if not state["internal_mutation_authorized"]:
        return authority_blocker(mode, execution_authority)

    prospect_id = _text(
        action.get("prospect_id")
    )

    if not prospect_id:
        return {
            "status": "BLOCKED",
            "blocker":
                "canonical_prospect_id_missing",
            "recovery_strategy":
                "targeted_source_probe_review",
            "internal_mutation_performed":
                False,
            "outbound_sent": False,
            "call_placed": False,
            "binding_terms_action": False,
            "payment_action": False,
        }

    bridge = materialize_buyer_scout_identity(
        prospect_id=prospect_id, write_authorized=state["internal_mutation_authorized"],
        request_factory=request_json,
    )
    # A non-Scout prospect keeps its existing research pathway. A Scout
    # blocker must never fall through to crawling or arbitrary selection.
    scout = bridge.get("status") != "NO_BUYER_SCOUT_ACQUISITION"
    if scout and (bridge.get("ok") is not True or bridge.get("decision_status") != "RESOLVED"):
        return {
            "status": "BLOCKED", "blocker": bridge.get("blocker") or bridge.get("decision_status"),
            "prospect_id": prospect_id, "identity_bridge": bridge,
            "retryable": bridge.get("retryable", False),
            "recovery_strategy": "buyer_scout_canonical_person_bridge",
            "internal_mutation_performed": bridge.get("internal_mutation_performed", False),
            "outbound_sent": False, "call_placed": False,
            "binding_terms_action": False, "payment_action": False,
        }

    def review_probe(row):
        if not scout:
            return _source_probe(row)
        if _text(row.get("id")) != prospect_id:
            raise ValueError("canonical person review prospect mismatch")
        return bridge["review_input"]

    result = run_buyer_review_materializer(
        probe=review_probe,
        prospect_ids=[
            prospect_id
        ],
        scan_limit=1,
        proposal_limit=1,
        probe_workers=1,
    )

    data = result.as_dict()

    rejection_counts = (
        data.get("rejection_counts")
        or {}
    )

    blocker = None

    if isinstance(
        rejection_counts,
        Mapping,
    ):
        blocker = next(
            iter(rejection_counts),
            None,
        )

    proposed = int(
        data.get("proposed")
        or 0
    )

    ready = int(
        data.get("review_ready")
        or 0
    )

    existing = int(
        data.get("skipped_existing")
        or 0
    )

    errors = list(
        data.get("errors")
        or []
    )

    if proposed > 0:
        status = (
            "ADVANCED_REVIEW_PROPOSED"
        )
        mutated = True
        blocker = None

    elif existing > 0:
        status = (
            "ALREADY_PROGRESSING"
        )
        mutated = False
        blocker = None

    elif ready > 0:
        status = (
            "ADVANCED_REVIEW_READY"
        )
        mutated = False

    elif errors:
        status = "ERROR"
        mutated = False
        blocker = (
            blocker
            or "review_materializer_error"
        )

    else:
        status = "BLOCKED"
        mutated = False
        blocker = (
            blocker
            or "targeted_progression_no_advance"
        )

    return {
        "status": status,
        "blocker": blocker,
        "recovery_strategy": (
            "targeted_source_probe_"
            "identity_recovery_review"
        ),
        "identity_bridge": bridge,
        "executor":
            "buyer_review_materializer",
        "internal_mutation_performed":
            mutated or bool(bridge.get("internal_mutation_performed")),
        "materializer": data,
        "outbound_sent": False,
        "call_placed": False,
        "binding_terms_action": False,
        "payment_action": False,
        "verified_commercial_outcome":
            False,
    }


def build_handlers(*, mode: str = "AUTO_INTERNAL", execution_authority: ExecutionAuthority | None = None):
    """Map recommendation semantics to the correct internal executor."""

    review_actions = {
        "prepare_buyer_review",
        "verify_decision_maker",
        "enrich_identity",
        "refresh_buyer_review",
        "recover_contact_evidence",
        "reconcile_identity",
    }

    research_actions = {
        "research_more",
        "refresh_evidence",
    }

    handlers = {
        action:
            partial(_targeted_review_progression, mode=mode, execution_authority=execution_authority)
        for action in review_actions
    }

    handlers.update({
        action:
            partial(_targeted_research_progression, mode=mode, execution_authority=execution_authority)
        for action in research_actions
    })

    unexpected = (
        set(AUTO_INTERNAL_ACTIONS)
        - set(handlers)
    )

    if unexpected:
        raise RuntimeError(
            "AUTO_INTERNAL action has no executor: "
            + ",".join(sorted(unexpected))
        )

    return handlers


def _strategy_memory(
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    groups = defaultdict(
        lambda: {
            "attempts": 0,
            "advanced": 0,
            "blocked": 0,
            "errors": 0,
        }
    )

    excluded_attempts = 0

    for row in attempts:
        action = _text(
            row.get("action")
        )

        strategy = _text(
            row.get(
                "recovery_strategy"
            )
        ) or "unknown"

        if not action:
            continue

        # Historical ACP Slice-2 bug:
        # research_more was incorrectly routed through the
        # buyer-review materializer before action-specific
        # executors were introduced. Preserve the raw attempt
        # log for auditability but do not let that invalid
        # executor/action pairing train strategy performance.
        legacy_misroute = (
            action in {
                "research_more",
                "refresh_evidence",
            }
            and strategy
            == (
                "targeted_source_probe_"
                "identity_recovery_review"
            )
        )

        if legacy_misroute:
            excluded_attempts += 1
            continue

        bucket = groups[
            (
                action,
                strategy,
            )
        ]

        bucket["attempts"] += 1

        status = _text(
            row.get("status")
        ).upper()

        if status.startswith(
            "ADVANCED"
        ):
            bucket[
                "advanced"
            ] += 1

        elif status == "BLOCKED":
            bucket[
                "blocked"
            ] += 1

        elif status == "ERROR":
            bucket[
                "errors"
            ] += 1

    strategies = []

    for (
        action,
        strategy,
    ), values in sorted(
        groups.items()
    ):
        attempts_count = (
            values["attempts"]
        )

        rate = (
            values["advanced"]
            / attempts_count
            if attempts_count
            else 0.0
        )

        strategies.append({
            "action": action,
            "recovery_strategy":
                strategy,
            **values,
            "advance_rate":
                round(
                    rate,
                    4,
                ),
            "verified_commercial_outcome":
                False,
            "economic_memory_outcome_write":
                False,
        })

    return {
        "schema_version": (
            "empire.autonomous-commercial-"
            "progression-learning.v1"
        ),
        "generated_at":
            _now().isoformat(),
        "attempt_count":
            len(attempts),
        "learning_eligible_attempt_count":
            len(attempts) - excluded_attempts,
        "excluded_attempt_count":
            excluded_attempts,
        "strategy_count":
            len(strategies),
        "strategies":
            strategies,
        "learning_scope":
            "internal_progression_efficiency",
        "commercial_outcome_learning":
            False,
        "synthetic_revenue_allowed":
            False,
    }


def refresh_strategy_memory():
    payload = _strategy_memory(
        _read_attempts()
    )

    _write_json(
        STRATEGY_MEMORY,
        payload,
    )

    return payload



def _precanonical_cooldown_ids() -> set[str]:
    attempts = _read_attempts()
    excluded = set()

    for row in attempts:
        if (
            _text(
                row.get("action")
            )
            != "canonicalize_buyer_scout_candidate"
        ):
            continue

        candidate_id = _text(
            row.get("entity_id")
        )

        if not candidate_id:
            continue

        action = {
            "recommended_action":
                "canonicalize_buyer_scout_candidate",
            "entity_id":
                candidate_id,
            "prospect_id":
                _text(
                    row.get("prospect_id")
                ),
        }

        if _cooldown_active(
            action,
            attempts,
        ):
            excluded.add(
                candidate_id
            )

    return excluded


def _normalise_precanonical_receipt(
    admission: Mapping[str, Any],
    *, mode: str, execution_authority: ExecutionAuthority | None,
) -> dict[str, Any]:
    return {
        "schema_version":
            "empire.autonomous-commercial-progression.v1",
        "generated_at":
            admission.get("generated_at")
            or _now().isoformat(),
        "action":
            "canonicalize_buyer_scout_candidate",
        "company_name":
            admission.get(
                "company_name"
            ),
        "entity_id":
            admission.get(
                "candidate_id"
            ),
        "prospect_id":
            admission.get(
                "canonical_prospect_id"
            ),
        **authority_state(mode, execution_authority),
        "selected_action": "canonicalize_buyer_scout_candidate",
        "retryable": admission.get("retryable", False),
        "status":
            admission.get(
                "status"
            ),
        "blocker":
            admission.get(
                "blocker"
            ),
        "recovery_strategy":
            admission.get(
                "recovery_strategy"
            ),
        "result":
            dict(admission),
        "internal_mutation_performed":
            admission.get(
                "internal_mutation_performed"
            )
            is True,
        "external_execution_performed":
            False,
        "outbound_sent":
            False,
        # This is Buyer Scout admission, not a review-ready ACP action.
        # Preserve the receipt schema without inventing an advisory.
        "outbound_advisory": None,
        "call_placed":
            False,
        "payment_action":
            False,
        "binding_terms_action":
            False,
        "learning_event": {
            "blocker":
                admission.get(
                    "blocker"
                ),
            "recovery_strategy":
                admission.get(
                    "recovery_strategy"
                ),
            "result_status":
                admission.get(
                    "status"
                ),
            "verified_commercial_outcome":
                False,
            "eligible_for_outcome_conditioned_economic_memory":
                False,
        },
    }


def run_internal_cycle(
    snapshot: Mapping[str, Any],
    *,
    execute: bool = False,
    mode: str = "AUTO_INTERNAL",
    execution_authority: ExecutionAuthority | None = None,
) -> dict[str, Any]:
    filtered = filter_cooldowns(
        snapshot
    )

    plan = build_progression_plan(
        filtered, mode=mode, execution_authority=execution_authority,
    )

    write_progression_plan(
        plan
    )

    output = {
        **authority_state(mode, execution_authority),
        "selected_action": plan["selected_action"],
        "internal_mutation_performed": False,
        "external_execution_performed": False,
        "plan": plan,
        "execution_requested":
            execute,
    }

    if not execute:
        output["receipt"] = None
        output["strategy_memory"] = (
            refresh_strategy_memory()
        )
        return output

    # Canonical opportunities always get first priority.
    # Only when none is currently actionable do we consume
    # a REVIEW_READY pre-canonical Buyer Scout holding.
    if (
        plan.get(
            "safe_internal_action_available"
        )
        is not True
        and output["internal_mutation_authorized"]
    ):
        admission = run_precanonical_admission(
            mode=mode, execution_authority=execution_authority,
            excluded_candidate_ids=(
                _precanonical_cooldown_ids()
            ),
        )

        if (
            admission.get("status")
            != "NO_ELIGIBLE_PRECANONICAL_CANDIDATE"
        ):
            payload = (
                _normalise_precanonical_receipt(
                    admission, mode=mode, execution_authority=execution_authority,
                )
            )

            _write_json(
                LATEST_RECEIPT,
                payload,
            )

            _append_attempt(
                payload
            )

            output["receipt"] = payload
            output["selected_action"] = payload["selected_action"]
            output["internal_mutation_performed"] = payload["internal_mutation_performed"]

            output[
                "precanonical_admission"
            ] = admission

            output[
                "strategy_memory"
            ] = refresh_strategy_memory()

            return output

    receipt = (
        execute_one_internal_progression(
            filtered,
            handlers=build_handlers(mode=mode, execution_authority=execution_authority),
            mode=mode, execution_authority=execution_authority,
        )
    )

    payload = receipt.as_dict()

    # ACP remains the sole owner of the internal mutation above.
    # Outbound receives the resulting state as a side-effect-free advisory.
    # Any bridge failure is fail-closed and cannot change ACP's receipt truth.
    try:
        payload["outbound_advisory"] = outbound_advisory_from_progression(
            payload
        )
    except Exception as exc:
        payload["outbound_advisory"] = {
            "schema_version": "empire.outbound_runtime_bridge.v1",
            "advisory_only": True,
            "status": "BLOCKED",
            "blocker": "outbound_advisory_bridge_error",
            "error_type": type(exc).__name__,
            "outbound_sent": False,
            "send_enabled": False,
            "execution_authority": "none",
        }

    _write_json(
        LATEST_RECEIPT,
        payload,
    )

    if payload.get("action"):
        _append_attempt(
            payload
        )

    output["receipt"] = payload
    output["internal_mutation_performed"] = payload["internal_mutation_performed"]
    output["strategy_memory"] = (
        refresh_strategy_memory()
    )

    return output
