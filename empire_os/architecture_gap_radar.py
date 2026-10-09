from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from empire_os.detection_fusion import (
    ControlSignal,
    duplicate_keys,
    entity_risk,
    fuse_signals,
    lane_verdict,
)

from empire_os.control_state_reconciliation import (
    active_entity_set,
    entity_generation_id,
    partition_control_signals,
    stale_entity_counts,
)


ROOT = Path("/srv/empire_os")

BUYER = (
    ROOT
    / "runtime"
    / "buyer_network_intelligence"
)

QUALITY = (
    ROOT
    / "runtime"
    / "truth_quality_control"
)

IDENTITY = (
    ROOT
    / "runtime"
    / "identity_resolution"
)

CONTROL = (
    ROOT
    / "runtime"
    / "control_plane"
)


ARTIFACTS = {
    "entity_types":
        QUALITY
        / "entity_type_latest.json",

    "quality_input":
        QUALITY
        / "buyer_input_latest.json",

    "quality_output":
        QUALITY
        / "buyer_output_latest.json",

    "quarantine":
        QUALITY
        / "buyer_quarantine_latest.json",

    "identity":
        IDENTITY
        / "buyer_identity_latest.json",

    "discovery":
        BUYER
        / "discovery_latest.json",

    "verification":
        BUYER
        / "verification_latest.json",

    "queue":
        BUYER
        / "candidate_queue_latest.json",

    "backlog":
        BUYER
        / "verification_backlog_latest.json",

    "founder_review":
        BUYER
        / "founder_review_packets_latest.json",
}


REQUIRED_CONTROLS = {
    "semantic_entity_detection":
        "entity_types",

    "input_quality_detection":
        "quality_input",

    "output_quality_detection":
        "quality_output",

    "quarantine":
        "quarantine",

    "canonical_identity_resolution":
        "identity",

    "source_discovery":
        "discovery",

    "active_verification":
        "verification",

    "ranked_queue":
        "queue",

    "verification_backlog":
        "backlog",

    "founder_review_gate":
        "founder_review",
}


DROPIN_DIR = Path(
    "/etc/systemd/system/"
    "empire-department-cycle.service.d"
)


def now_iso():

    return datetime.now(
        timezone.utc
    ).isoformat()


def read_json(
    path: Path,
) -> dict[str, Any]:

    if not path.exists():
        return {}

    try:

        return json.loads(
            path.read_text()
        )

    except Exception:

        return {}


def signals_from_quality(
    artifact_name: str,
    payload: dict[str, Any],
) -> list[ControlSignal]:

    signals = []

    for decision in payload.get(
        "decisions",
        [],
    ):

        entity = str(
            decision.get(
                "canonical_identity"
            )
            or decision.get(
                "raw_identity"
            )
            or "__unknown__"
        )

        for detection in decision.get(
            "detections",
            [],
        ):

            severity = str(
                detection.get(
                    "severity"
                )
                or "LOW"
            ).upper()

            signals.append(
                ControlSignal(
                    code=
                        str(
                            detection.get(
                                "detection_type"
                            )
                            or "QUALITY_DETECTION"
                        ),

                    severity=
                        severity,

                    entity=
                        entity,

                    source=
                        artifact_name,

                    reason=
                        str(
                            detection.get(
                                "reason"
                            )
                            or "quality detector signal"
                        ),

                    evidence=[
                        str(value)
                        for value
                        in detection.get(
                            "evidence",
                            [],
                        )
                    ],

                    recommendation=
                        str(
                            detection.get(
                                "recommended_action"
                            )
                            or "VERIFY"
                        ),

                    blocks_entity=
                        not bool(
                            detection.get(
                                "action_allowed",
                                False,
                            )
                        ),
                )
            )

    return signals


def signals_from_identity(
    identity: dict[str, Any],
) -> list[ControlSignal]:

    signals = []

    for pair in identity.get(
        "uncertain_pairs",
        [],
    ):

        left = str(
            pair.get(
                "left"
            )
            or ""
        )

        right = str(
            pair.get(
                "right"
            )
            or ""
        )

        confidence = pair.get(
            "confidence"
        )

        reason = (
            "Identity relationship is unresolved "
            f"between {left} and {right}."
        )

        evidence = [
            f"peer={right}",
            f"confidence={confidence}",
        ]

        evidence.extend(
            str(value)
            for value
            in pair.get(
                "reasons",
                [],
            )
        )

        signals.append(
            ControlSignal(
                code=
                    "IDENTITY_UNCERTAIN",

                severity=
                    "MEDIUM",

                entity=
                    left,

                source=
                    "identity_resolution",

                reason=
                    reason,

                evidence=
                    evidence,

                recommendation=
                    "RESOLVE_IDENTITY",

                blocks_entity=
                    True,
            )
        )

        signals.append(
            ControlSignal(
                code=
                    "IDENTITY_UNCERTAIN",

                severity=
                    "MEDIUM",

                entity=
                    right,

                source=
                    "identity_resolution",

                reason=
                    (
                        "Identity relationship is unresolved "
                        f"between {right} and {left}."
                    ),

                evidence=[
                    f"peer={left}",
                    f"confidence={confidence}",
                ]
                +
                [
                    str(value)
                    for value
                    in pair.get(
                        "reasons",
                        [],
                    )
                ],

                recommendation=
                    "RESOLVE_IDENTITY",

                blocks_entity=
                    True,
            )
        )

    return signals


def active_verified_domains(
    discovery: dict[str, Any],
) -> set[str]:

    result = set()

    for run in discovery.get(
        "runs",
        [],
    ):

        if (
            run.get(
                "query"
            )
            != "buyer-network-active-verification"
        ):
            continue

        for domain in (
            run.get(
                "domains"
            )
            or []
        ):

            domain = str(
                domain
            ).lower()

            if domain:
                result.add(
                    domain
                )

    return result


def state_signals(
    queue: dict[str, Any],
    backlog: dict[str, Any],
    founder: dict[str, Any],
    identity: dict[str, Any],
    discovery: dict[str, Any],
    quality_output: dict[str, Any],
) -> list[ControlSignal]:

    signals = []

    queue_records = queue.get(
        "candidates",
        [],
    )

    backlog_records = backlog.get(
        "candidates",
        [],
    )

    founder_records = founder.get(
        "packets",
        [],
    )

    queue_domains = {
        str(
            item.get(
                "domain"
            )
            or ""
        ).lower():
            item

        for item
        in queue_records
    }

    backlog_domains = {
        str(
            item.get(
                "domain"
            )
            or ""
        ).lower():
            item

        for item
        in backlog_records
    }

    founder_domains = {
        str(
            item.get(
                "domain"
            )
            or ""
        ).lower():
            item

        for item
        in founder_records
    }

    active = active_verified_domains(
        discovery
    )

    alias_map = identity.get(
        "alias_map",
        {},
    )

    for alias, canonical in alias_map.items():

        if alias in queue_domains:

            signals.append(
                ControlSignal(
                    code=
                        "CANONICAL_ALIAS_LEAK",

                    severity=
                        "HIGH",

                    entity=
                        alias,

                    source=
                        "candidate_queue",

                    reason=
                        (
                            "Confirmed alias still exists "
                            "as an independent queue identity."
                        ),

                    evidence=[
                        f"canonical={canonical}"
                    ],

                    recommendation=
                        "APPLY_CANONICAL_OVERLAY",

                    blocks_entity=
                        True,
                )
            )

        if alias in backlog_domains:

            signals.append(
                ControlSignal(
                    code=
                        "CANONICAL_ALIAS_LEAK",

                    severity=
                        "HIGH",

                    entity=
                        alias,

                    source=
                        "verification_backlog",

                    reason=
                        (
                            "Confirmed alias still exists "
                            "as an independent verification target."
                        ),

                    evidence=[
                        f"canonical={canonical}"
                    ],

                    recommendation=
                        "APPLY_CANONICAL_OVERLAY",

                    blocks_entity=
                        True,
                )
            )

    for domain, candidate in queue_domains.items():

        status = candidate.get(
            "status"
        )

        if (
            status == "READY_TO_APPROACH"
            and domain not in active
        ):

            signals.append(
                ControlSignal(
                    code=
                        "READY_WITHOUT_ACTIVE_VERIFICATION",

                    severity=
                        "CRITICAL",

                    entity=
                        domain,

                    source=
                        "state_consistency",

                    reason=
                        (
                            "Candidate is READY_TO_APPROACH "
                            "without active verification provenance."
                        ),

                    evidence=[
                        str(status)
                    ],

                    recommendation=
                        "DEMOTE_AND_VERIFY",

                    blocks_entity=
                        True,
                )
            )

        if (
            status == "READY_TO_APPROACH"
            and domain not in founder_domains
        ):

            signals.append(
                ControlSignal(
                    code=
                        "READY_WITHOUT_FOUNDER_PACKET",

                    severity=
                        "HIGH",

                    entity=
                        domain,

                    source=
                        "state_consistency",

                    reason=
                        (
                            "READY candidate has no trusted "
                            "founder-review packet."
                        ),

                    evidence=[
                        str(status)
                    ],

                    recommendation=
                        "BLOCK_COMMERCIAL_PROGRESSION",

                    blocks_entity=
                        True,
                )
            )

    for domain in founder_domains:

        candidate = queue_domains.get(
            domain
        )

        if (
            not candidate
            or candidate.get(
                "status"
            )
            != "READY_TO_APPROACH"
        ):

            signals.append(
                ControlSignal(
                    code=
                        "FOUNDER_PACKET_STATE_CONFLICT",

                    severity=
                        "CRITICAL",

                    entity=
                        domain,

                    source=
                        "state_consistency",

                    reason=
                        (
                            "Founder review packet exists "
                            "without corresponding READY queue state."
                        ),

                    evidence=[
                        str(
                            candidate.get(
                                "status"
                            )
                            if candidate
                            else "missing"
                        )
                    ],

                    recommendation=
                        "REBUILD_FOUNDER_REVIEW",

                    blocks_entity=
                        True,
                )
            )

    for domain, candidate in backlog_domains.items():

        queue_candidate = queue_domains.get(
            domain
        )

        if (
            queue_candidate
            and queue_candidate.get(
                "status"
            )
            == "READY_TO_APPROACH"
            and candidate.get(
                "status"
            )
            in (
                "WATCH",
                "VERIFY_REQUIREMENTS",
            )
        ):

            signals.append(
                ControlSignal(
                    code=
                        "QUEUE_BACKLOG_STATE_CONFLICT",

                    severity=
                        "HIGH",

                    entity=
                        domain,

                    source=
                        "state_consistency",

                    reason=
                        (
                            "Same canonical identity is READY "
                            "in queue but unresolved in backlog."
                        ),

                    evidence=[
                        (
                            "queue="
                            + str(
                                queue_candidate.get(
                                    "status"
                                )
                            )
                        ),
                        (
                            "backlog="
                            + str(
                                candidate.get(
                                    "status"
                                )
                            )
                        ),
                    ],

                    recommendation=
                        "RECONCILE_STATE",

                    blocks_entity=
                        True,
                )
            )

    blocked_output = {
        str(
            item.get(
                "canonical_identity"
            )
            or item.get(
                "raw_identity"
            )
            or ""
        ).lower()

        for item
        in quality_output.get(
            "decisions",
            [],
        )

        if item.get(
            "verdict"
        )
        in (
            "CONFLICT",
            "HOLD_FOR_VERIFICATION",
        )
    }

    for domain in founder_domains:

        if domain in blocked_output:

            signals.append(
                ControlSignal(
                    code=
                        "QUALITY_BLOCKED_BUT_FOUNDER_READY",

                    severity=
                        "CRITICAL",

                    entity=
                        domain,

                    source=
                        "output_quality_consistency",

                    reason=
                        (
                            "Founder-ready identity is blocked "
                            "by the output quality detector."
                        ),

                    evidence=[
                        domain
                    ],

                    recommendation=
                        "BLOCK_COMMERCIAL_PROGRESSION",

                    blocks_entity=
                        True,
                )
            )

    for domain, count in duplicate_keys(
        queue_records,
        key="domain",
    ).items():

        signals.append(
            ControlSignal(
                code=
                    "DUPLICATE_QUEUE_IDENTITY",

                severity=
                    "HIGH",

                entity=
                    domain,

                source=
                    "candidate_queue",

                reason=
                    (
                        "Canonical identity occurs multiple "
                        "times in the ranked queue."
                    ),

                evidence=[
                    f"count={count}"
                ],

                recommendation=
                    "DEDUPLICATE_QUEUE",

                blocks_entity=
                    True,
            )
        )

    for domain, count in duplicate_keys(
        backlog_records,
        key="domain",
    ).items():

        signals.append(
            ControlSignal(
                code=
                    "DUPLICATE_BACKLOG_IDENTITY",

                severity=
                    "HIGH",

                entity=
                    domain,

                source=
                    "verification_backlog",

                reason=
                    (
                        "Canonical identity occurs multiple "
                        "times in verification backlog."
                    ),

                evidence=[
                    f"count={count}"
                ],

                recommendation=
                    "DEDUPLICATE_BACKLOG",

                blocks_entity=
                    True,
            )
        )

    return signals


def artifact_control_gaps():

    gaps = []

    controls = {}

    for (
        control,
        artifact_name,
    ) in REQUIRED_CONTROLS.items():

        path = ARTIFACTS[
            artifact_name
        ]

        present = (
            path.exists()
            and path.stat().st_size > 0
        )

        controls[
            control
        ] = {
            "artifact":
                str(
                    path.relative_to(
                        ROOT
                    )
                ),

            "present":
                present,
        }

        if not present:

            gaps.append(
                {
                    "code":
                        "MISSING_CONTROL",

                    "severity":
                        "CRITICAL",

                    "control":
                        control,

                    "reason":
                        (
                            f"Required control artifact "
                            f"{artifact_name} is missing."
                        ),

                    "recommendation":
                        "RESTORE_CONTROL",

                    "blocks_lane":
                        True,
                }
            )

    return controls, gaps


def exec_order():

    lines = []

    if not DROPIN_DIR.exists():

        return lines

    for path in sorted(
        DROPIN_DIR.glob(
            "*.conf"
        )
    ):

        try:
            text = path.read_text()

        except Exception:
            continue

        for raw in text.splitlines():

            raw = raw.strip()

            if raw.startswith(
                "ExecStartPost="
            ):

                lines.append(
                    {
                        "dropin":
                            path.name,

                        "command":
                            raw.split(
                                "=",
                                1,
                            )[1],
                    }
                )

    return lines


def pipeline_order_gaps():

    execution = exec_order()

    commands = [
        item[
            "command"
        ]
        for item
        in execution
    ]

    gaps = []

    def indexes(
        token: str,
    ):

        return [
            index
            for index, command
            in enumerate(
                commands
            )
            if token in command
        ]

    input_quality = indexes(
        "run_truth_quality_control.py --stage input"
    )

    identity = indexes(
        "run_canonical_identity_resolution.py"
    )

    direct = indexes(
        "probe_buyer_network_direct_sites.py"
    )

    queue = indexes(
        "materialize_buyer_network_candidate_queue.py"
    )

    overlay_queue = indexes(
        "apply_canonical_identity_overlay.py --target queue"
    )

    shortlist = indexes(
        "materialize_buyer_network_founder_shortlist.py"
    )

    founder = indexes(
        "materialize_buyer_network_founder_review_packets.py"
    )

    output_quality = indexes(
        "run_truth_quality_control.py --stage output"
    )

    required = {
        "input_quality":
            input_quality,

        "identity":
            identity,

        "direct_verification":
            direct,

        "queue":
            queue,

        "canonical_queue_overlay":
            overlay_queue,

        "shortlist":
            shortlist,

        "founder_review":
            founder,

        "output_quality":
            output_quality,
    }

    for name, positions in required.items():

        if not positions:

            gaps.append(
                {
                    "code":
                        "MISSING_PIPELINE_CONTROL",

                    "severity":
                        "CRITICAL",

                    "control":
                        name,

                    "reason":
                        (
                            f"Expected Department Cycle "
                            f"control {name} is absent."
                        ),

                    "recommendation":
                        "RESTORE_PIPELINE_CONTROL",

                    "blocks_lane":
                        True,
                }
            )

    if gaps:
        return execution, gaps

    # Identity must exist both before and after
    # direct-site evidence.
    before_identity = [
        pos
        for pos
        in identity
        if pos < direct[0]
    ]

    after_identity = [
        pos
        for pos
        in identity
        if pos > direct[0]
    ]

    if not before_identity:

        gaps.append(
            {
                "code":
                    "IDENTITY_ORDER_GAP",

                "severity":
                    "HIGH",

                "control":
                    "identity_pre_verification",

                "reason":
                    (
                        "No identity-resolution pass occurs "
                        "before direct-site verification."
                    ),

                "recommendation":
                    "REORDER_PIPELINE",

                "blocks_lane":
                    True,
            }
        )

    if not after_identity:

        gaps.append(
            {
                "code":
                    "IDENTITY_REFRESH_ORDER_GAP",

                "severity":
                    "HIGH",

                "control":
                    "identity_post_verification",

                "reason":
                    (
                        "Identity graph is not refreshed "
                        "after new direct-site evidence."
                    ),

                "recommendation":
                    "REORDER_PIPELINE",

                "blocks_lane":
                    True,
            }
        )

    expected = [
        input_quality[0],
        min(
            before_identity
            or identity
        ),
        direct[0],
        max(
            after_identity
            or identity
        ),
        queue[0],
        overlay_queue[0],
        shortlist[0],
        founder[0],
        output_quality[0],
    ]

    if expected != sorted(
        expected
    ):

        gaps.append(
            {
                "code":
                    "PIPELINE_ORDER_CONFLICT",

                "severity":
                    "CRITICAL",

                "control":
                    "department_cycle",

                "reason":
                    (
                        "Detection / identity / verification / "
                        "queue / review controls execute in an "
                        "unsafe order."
                    ),

                "recommendation":
                    "REORDER_PIPELINE",

                "blocks_lane":
                    True,
            }
        )

    return execution, gaps



def semantic_pipeline_gaps():

    execution = exec_order()

    commands = [
        item[
            "command"
        ]
        for item
        in execution
    ]

    def positions(
        token: str,
    ):

        return [
            index
            for index, command
            in enumerate(
                commands
            )
            if token in command
        ]

    semantic = positions(
        "run_entity_type_detection.py"
    )

    input_quality = positions(
        "run_truth_quality_control.py --stage input"
    )

    direct = positions(
        "probe_buyer_network_direct_sites.py"
    )

    identity = positions(
        "run_canonical_identity_resolution.py"
    )

    queue = positions(
        "materialize_buyer_network_candidate_queue.py"
    )

    semantic_queue = positions(
        "apply_entity_type_overlay.py --target queue"
    )

    canonical_queue = positions(
        "apply_canonical_identity_overlay.py --target queue"
    )

    gaps = []

    required = {
        "semantic_detection":
            semantic,

        "input_quality":
            input_quality,

        "direct_site_verification":
            direct,

        "identity_resolution":
            identity,

        "candidate_queue":
            queue,

        "semantic_queue_gate":
            semantic_queue,

        "canonical_queue_gate":
            canonical_queue,
    }

    for name, found in required.items():

        if found:
            continue

        gaps.append(
            {
                "code":
                    "SEMANTIC_CONTROL_MISSING",

                "severity":
                    "CRITICAL",

                "control":
                    name,

                "reason":
                    (
                        "Semantic detection pipeline "
                        f"control {name} is missing."
                    ),

                "recommendation":
                    "RESTORE_SEMANTIC_CONTROL",

                "blocks_lane":
                    True,
            }
        )

    if gaps:
        return (
            execution,
            gaps,
        )

    pre_semantic = [
        pos
        for pos
        in semantic
        if pos < input_quality[0]
    ]

    post_direct_semantic = [
        pos
        for pos
        in semantic
        if (
            pos > direct[0]
            and pos < queue[0]
        )
    ]

    post_semantic_identity = []

    if post_direct_semantic:

        last_semantic = max(
            post_direct_semantic
        )

        post_semantic_identity = [
            pos
            for pos
            in identity
            if (
                pos > last_semantic
                and pos < queue[0]
            )
        ]

    if not pre_semantic:

        gaps.append(
            {
                "code":
                    "SEMANTIC_PRE_QUALITY_ORDER_GAP",

                "severity":
                    "HIGH",

                "control":
                    "semantic_entity_detection",

                "reason":
                    (
                        "Semantic entity detection does "
                        "not execute before input quality."
                    ),

                "recommendation":
                    "REORDER_PIPELINE",

                "blocks_lane":
                    True,
            }
        )

    if not post_direct_semantic:

        gaps.append(
            {
                "code":
                    "SEMANTIC_REFRESH_ORDER_GAP",

                "severity":
                    "HIGH",

                "control":
                    "semantic_entity_refresh",

                "reason":
                    (
                        "Semantic entity detection is not "
                        "refreshed after direct-site evidence."
                    ),

                "recommendation":
                    "ADD_POST_VERIFICATION_REFRESH",

                "blocks_lane":
                    True,
            }
        )

    if (
        post_direct_semantic
        and not post_semantic_identity
    ):

        gaps.append(
            {
                "code":
                    "IDENTITY_AFTER_SEMANTIC_GAP",

                "severity":
                    "HIGH",

                "control":
                    "canonical_identity_resolution",

                "reason":
                    (
                        "Canonical identity is not refreshed "
                        "after the semantic detector receives "
                        "new direct-site evidence."
                    ),

                "recommendation":
                    "REORDER_PIPELINE",

                "blocks_lane":
                    True,
            }
        )

    if not (
        queue[0]
        < semantic_queue[0]
        < canonical_queue[0]
    ):

        gaps.append(
            {
                "code":
                    "SEMANTIC_QUEUE_ORDER_CONFLICT",

                "severity":
                    "CRITICAL",

                "control":
                    "buyer_queue",

                "reason":
                    (
                        "Fresh candidate queue is not "
                        "semantic-gated before canonical "
                        "queue consolidation."
                    ),

                "recommendation":
                    "REORDER_PIPELINE",

                "blocks_lane":
                    True,
            }
        )

    return (
        execution,
        gaps,
    )


def architecture_radar():

    payloads = {
        name:
            read_json(
                path
            )

        for name, path
        in ARTIFACTS.items()
    }

    raw_signals = []

    raw_signals.extend(
        signals_from_quality(
            "input_quality",
            payloads[
                "quality_input"
            ],
        )
    )

    raw_signals.extend(
        signals_from_quality(
            "output_quality",
            payloads[
                "quality_output"
            ],
        )
    )

    raw_signals.extend(
        signals_from_identity(
            payloads[
                "identity"
            ]
        )
    )

    raw_signals.extend(
        state_signals(
            payloads[
                "queue"
            ],
            payloads[
                "backlog"
            ],
            payloads[
                "founder_review"
            ],
            payloads[
                "identity"
            ],
            payloads[
                "discovery"
            ],
            payloads[
                "quality_output"
            ],
        )
    )

    current_entities = active_entity_set(
        payloads[
            "entity_types"
        ]
    )

    current_signals, historical_signals = (
        partition_control_signals(
            raw_signals,
            current_entities,
        )
    )

    stale_counts = stale_entity_counts(
        raw_signals,
        current_entities,
    )

    fused = fuse_signals(
        current_signals
    )

    historical_fused = fuse_signals(
        historical_signals
    )

    risks = entity_risk(
        fused
    )

    controls, artifact_gaps = (
        artifact_control_gaps()
    )

    execution_order, order_gaps = (
        pipeline_order_gaps()
    )

    _, semantic_order_gaps = (
        semantic_pipeline_gaps()
    )

    gaps = (
        artifact_gaps
        + order_gaps
        + semantic_order_gaps
    )

    critical_entities = [
        item
        for item in risks
        if item[
            "max_severity"
        ] == "CRITICAL"
    ]

    high_entities = [
        item
        for item in risks
        if item[
            "max_severity"
        ] == "HIGH"
    ]

    # Entity-specific problems hold the entity.
    # Architectural problems can hold the whole lane.
    verdict = lane_verdict(
        gaps
    )

    return {
        "schema_version":
            "empire-architecture-gap-radar-v1",

        "generated_at":
            now_iso(),

        "lane":
            "buyer_network",

        "authority":
            "OBSERVE",

        "lane_verdict":
            verdict,

        "lane_action_allowed":
            False,

        "control_contract":
            controls,

        "architecture_gap_count":
            len(
                gaps
            ),

        "architecture_gaps":
            gaps,

        "active_entity_count":
            len(
                current_entities
            ),

        "entity_generation_id":
            (
                payloads[
                    "entity_types"
                ].get(
                    "generation_id"
                )
                or entity_generation_id(
                    payloads[
                        "entity_types"
                    ]
                )
            ),

        "raw_signal_count":
            len(
                current_signals
            ),

        "historical_stale_signal_count":
            len(
                historical_signals
            ),

        "historical_stale_fused_count":
            len(
                historical_fused
            ),

        "historical_stale_entities":
            stale_counts,

        "fused_signal_count":
            len(
                fused
            ),

        "fused_signals":
            fused,

        "entity_risk_count":
            len(
                risks
            ),

        "critical_entity_count":
            len(
                critical_entities
            ),

        "high_entity_count":
            len(
                high_entities
            ),

        "held_entity_count":
            sum(
                bool(
                    item.get(
                        "held"
                    )
                )
                for item
                in risks
            ),

        "entity_risk":
            risks,

        "department_cycle_order":
            execution_order,

        "governance": {
            "db_write":
                False,

            "outbound":
                False,

            "traffic":
                False,

            "funds":
                False,

            "automatic_destructive_remediation":
                False,
        },
    }
