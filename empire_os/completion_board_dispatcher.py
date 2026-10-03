"""Batch the passive completion board into governed internal review work."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from empire_os.completion_capability_registry import WORKSTREAMS
from empire_os.department_work_queue import DepartmentWorkQueue
from empire_os.founder_directives import classify_authority
from empire_os.master_execution_ledger import parse_checklist


SCHEMA_VERSION = "empire.completion_board_dispatch.v3"
SOURCE = Path("docs/MASTER_REMAINING_CHECKLIST.md")
OUTPUT = Path("runtime/execution_plane/business_completion_dispatch_latest.json")
OWNER_MAP = {
    "engineering": "engineering",
    "data_quant": "data_quant",
    "market_intelligence": "market_intelligence",
    "sales_revenue": "sales_revenue",
    "product": "product",
    "marketing_growth": "marketing_growth",
    "operations_fulfilment": "operations_fulfilment",
    "rd_innovation": "rd_innovation",
    "strategy": "strategy_executive",
    "finance": "finance_capital",
}
CLASS_PRIORITY = {
    "founder_gate": 100,
    "builder_required": 96,
    "safe_internal": 92,
    "evidence_required": 88,
}


def _text(value: Any) -> str:
    return str(value or "").strip()


EVIDENCE_TERMS = (
    "verified outcome",
    "real production evidence",
    "real-world",
    "live verification",
    "calibrated",
    "cohort",
    "actual revenue",
    "actual outcome",
    "proof",
)
BUILDER_RE = re.compile(
    r"\b(add|build|connect|converge|enable|expose|implement|install|"
    r"integrate|migrate|persist|retire|route|wire)\b",
    re.I,
)


def _owner_for_section(section: str) -> tuple[str | None, str | None]:
    lower = section.lower()
    candidates: list[tuple[int, int, str, str]] = []
    for index, spec in enumerate(WORKSTREAMS):
        for term in spec.checklist_terms:
            term_lower = term.lower()
            if term_lower in lower or lower in term_lower:
                candidates.append((
                    len(term_lower),
                    -index,
                    OWNER_MAP.get(spec.owner, spec.owner),
                    spec.key,
                ))
    if not candidates:
        return "strategy_executive", "unmapped_completion_scope"
    _, _, owner, workstream = max(candidates)
    return owner, workstream


def _execution_class(section: str, item: str) -> str:
    combined = f"{section} {item}"
    authority, _ = classify_authority(combined)
    lower = combined.lower()
    if (
        authority == "founder_gate"
        or "founder gate" in lower
        or "founder approval" in lower
    ):
        return "founder_gate"
    if any(term in lower for term in EVIDENCE_TERMS):
        return "evidence_required"
    if BUILDER_RE.search(item):
        return "builder_required"
    return "safe_internal"


def _live_rows(path: Path) -> tuple[list[dict[str, Any]], int, int]:
    items = parse_checklist(path)
    done = sum(row.status == "DONE" for row in items)
    pending = [row for row in items if row.status == "PENDING"]
    rows: list[dict[str, Any]] = []
    for row in pending:
        department, workstream = _owner_for_section(row.section)
        material = f"{row.line}|{row.section}|{row.item}"
        rows.append({
            "id": "check_" + sha256(material.encode("utf-8")).hexdigest()[:16],
            "line": row.line,
            "section": row.section,
            "task": row.item,
            "department": department,
            "workstream": workstream,
            "execution_class": _execution_class(row.section, row.item),
        })
    return rows, done, len(items)


def _source_ref(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return f"{path.as_posix()}#sha256={sha256(data).hexdigest()}"


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _chunks(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[index:index + size] for index in range(0, len(rows), size)]


def _verification_contract(
    root: Path,
    workstreams: list[str],
) -> dict[str, Any] | None:
    specs = {spec.key: spec for spec in WORKSTREAMS}
    modules: list[str] = []
    tests: list[str] = []
    for key in workstreams:
        spec = specs.get(key)
        if spec is None:
            continue
        for pattern in spec.module_patterns:
            for path in sorted((root / "empire_os").glob(pattern)):
                if not path.is_file() or path.suffix != ".py":
                    continue
                rel = str(path.relative_to(root))
                if rel not in modules:
                    modules.append(rel)
                test = root / "tests" / f"test_{path.stem}.py"
                if test.exists():
                    test_rel = str(test.relative_to(root))
                    if test_rel not in tests:
                        tests.append(test_rel)
    if not modules or not tests:
        return None
    return {
        "kind": "VERIFY",
        "changed_files": modules[:24],
        "tests": tests[:16],
    }


def _rationale(
    department: str,
    execution_class: str,
    rows: list[dict[str, Any]],
) -> str:
    items = " | ".join(
        f"{_text(row.get('task'))} [{_text(row.get('section'))}]"
        for row in rows
    )
    if execution_class == "founder_gate":
        return (
            f"Completion owner for {department}. "
            "Prepare founder-gate prerequisites only for remaining items. "
            f"Items: {items}. Stop before any gated action. "
            "Do not infer approval."
        )
    return (
        f"Completion owner for {department}. "
        "Produce an evidence-backed PLAN ONLY for remaining items. "
        f"Classify each {items}. Execution class={execution_class}. "
        "No deploy/send/payment/DB mutation steps and do not infer founder approval."
    )


def dispatch_completion_board(
    repo_root: str | Path,
    *,
    max_rows_per_packet: int = 40,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create idempotent department review packets, never checklist actions."""
    if max_rows_per_packet <= 0:
        raise ValueError("max_rows_per_packet must be positive")

    root = Path(repo_root).resolve()
    source_path = root / SOURCE
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    queue = DepartmentWorkQueue(root)

    if not source_path.exists():
        payload = {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "canonical_checklist_unavailable",
            "generated_at": current.isoformat(),
            "queued_packet_count": 0,
            "existing_packet_count": 0,
            "execution_authority": "none",
        }
        _atomic_write(root / OUTPUT, payload)
        return payload

    rows, done_count, total_count = _live_rows(source_path)
    source_ref = _source_ref(source_path)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    held_unknown: list[dict[str, Any]] = []

    for row in rows:
        department = _text(row.get("department"))
        execution_class = _text(row.get("execution_class"))
        if not department:
            held_unknown.append(row)
            continue
        grouped.setdefault((department, execution_class), []).append(row)

    queued = 0
    existing = 0
    packets: list[dict[str, Any]] = []
    plan_id = "completion_board_live_v3"

    for (department, execution_class), group in sorted(grouped.items()):
        ordered = sorted(
            group,
            key=lambda row: (
                _text(row.get("section")),
                int(row.get("line") or 0),
            ),
        )
        for chunk_index, chunk in enumerate(
            _chunks(ordered, max_rows_per_packet),
            start=1,
        ):
            identity = "|".join(_text(row.get("id")) for row in chunk)
            digest = sha256(identity.encode("utf-8")).hexdigest()[:14]
            step_id = (
                f"completion_{department}_{execution_class}_"
                f"{chunk_index}_{digest}"
            )
            priority = CLASS_PRIORITY[execution_class]
            action = (
                "prepare_to_gate_and_verify_prerequisites"
                if execution_class == "founder_gate"
                else "completion_review_then_implement_or_verify"
            )
            evidence_refs = [ref for ref in (source_ref,) if ref]
            evidence_refs.extend(
                f"checklist_line:{int(row.get('line') or 0)}:{_text(row.get('id'))}"
                for row in chunk
            )
            workstreams = sorted({
                _text(row.get("workstream"))
                for row in chunk
                if _text(row.get("workstream"))
            })
            promotion_contract = _verification_contract(
                root,
                workstreams,
            )
            step = {
                "step_id": step_id,
                "goal_key": "converge_master_remaining_checklist",
                "department_keys": [department],
                "target_component": "empire_coder",
                "action": action,
                "authority": "observe",
                "auto_dispatch_eligible": True,
                "founder_gate_required": False,
                "intelligence_request": {
                    "task": "completion_review",
                    "execution_class": execution_class,
                    "source": str(SOURCE),
                    "item_ids": [_text(row.get("id")) for row in chunk],
                    "checklist_lines": [
                        int(row.get("line") or 0) for row in chunk
                    ],
                    "workstreams": workstreams,
                    "promotion_contract": promotion_contract,
                    "review_only": True,
                },
                "memory_query": {
                    "retrieval_only": True,
                    "completion_board": True,
                },
                "evidence_refs": evidence_refs,
                "success_condition": (
                    "Every item is independently classified as VERIFIED_DONE, "
                    "NEEDS_WIRING, NEEDS_LIVE_PROOF, FOUNDER_GATE, "
                    "REAL_WORLD_EVIDENCE_REQUIRED or LEGACY_RETIRED with "
                    "exact evidence/blockers. Code existence alone is not DONE."
                ),
                "rationale": _rationale(
                    department,
                    execution_class,
                    chunk,
                ),
            }
            work, created = queue.enqueue_step(
                plan_id=plan_id,
                step=step,
                priority=priority,
                reopen_blocked_reasons=("specialist_adapter_required",),
            )
            queued += int(created)
            existing += int(not created)
            packets.append({
                "work_id": work.id,
                "step_id": step_id,
                "department": department,
                "execution_class": execution_class,
                "priority": priority,
                "item_count": len(chunk),
                "item_ids": [_text(row.get("id")) for row in chunk],
                "workstreams": workstreams,
                "verification_contract_ready": (
                    promotion_contract is not None
                ),
                "created": created,
                "action": action,
                "external_execution_allowed": False,
            })

    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "mode": "OBSERVE",
        "generated_at": current.isoformat(),
        "source": str(SOURCE),
        "source_ref": source_ref,
        "canonical_total_count": total_count,
        "canonical_done_count": done_count,
        "source_pending_count": len(rows),
        "packet_count": len(packets),
        "queued_packet_count": queued,
        "existing_packet_count": existing,
        "held_unowned_row_count": len(held_unknown),
        "queue_counts": queue.counts(),
        "packets": packets,
        "batching_enabled": True,
        "max_rows_per_packet": max_rows_per_packet,
        "legacy_allocation_snapshot_used": False,
        "consequential_actions_dispatched": False,
        "founder_gates_preserved": True,
        "evidence_gates_preserved": True,
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
        "execution_authority": "none",
    }
    _atomic_write(root / OUTPUT, payload)
    return payload
