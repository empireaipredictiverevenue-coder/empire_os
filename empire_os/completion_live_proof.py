"""Read-only live proof engine for exact completion checklist items.

Rules are intentionally explicit. A rule may create an exact line-bound
LIVE_VERIFY_DONE checkpoint only when every configured local proof passes.
No external network, mutation, founder approval inference, payment, outbound,
or revenue recognition is allowed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Callable
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

from empire_os.master_execution_ledger import parse_checklist


SCHEMA_VERSION = "empire.completion-live-proof.v1"
OUTPUT = Path("runtime/execution_plane/completion_live_proof_latest.json")
CHECKPOINTS = Path("runtime/execution_plane/completion_checkpoints")


@dataclass(frozen=True)
class Rule:
    item: str
    probes: tuple[tuple[str, tuple[Any, ...]], ...]


RULES: tuple[Rule, ...] = (
    Rule(
        "Live EmpireOS verification of Quant endpoints and opportunity Quant Review",
        (
            ("http_json", ("http://127.0.0.1:8766/health", "ok", True)),
            (
                "http_json",
                (
                    "http://127.0.0.1:8766/v1/predictive-cloud/status",
                    "available",
                    True,
                ),
            ),
            (
                "json_file_key",
                (
                    "runtime/opportunity_factory/quant_review_latest.json",
                    "schema_version",
                    "empire.opportunity_quant_review.v1",
                ),
            ),
            (
                "json_file_key",
                (
                    "runtime/opportunity_factory/quant_review_latest.json",
                    "execution_authority",
                    "none",
                ),
            ),
        ),
    ),
    Rule(
        "Predictive Cloud API/read-model convergence",
        (
            (
                "http_json",
                (
                    "http://127.0.0.1:8766/v1/predictive-cloud/status",
                    "available",
                    True,
                ),
            ),
            (
                "json_counts_equal",
                (
                    "runtime/predictive_cloud/status_latest.json",
                    "available_component_count",
                    "component_count",
                ),
            ),
            (
                "json_list_empty",
                (
                    "runtime/predictive_cloud/status_latest.json",
                    "unavailable_components",
                ),
            ),
        ),
    ),
    Rule(
        "Predictive Cloud Founder Console surface",
        (
            ("http_status", ("http://127.0.0.1:3001/founder", 200)),
            (
                "http_contains",
                ("http://127.0.0.1:3001/founder", "Predictive"),
            ),
            (
                "http_json",
                (
                    "http://127.0.0.1:8766/v1/predictive-cloud/status",
                    "available",
                    True,
                ),
            ),
        ),
    ),
    Rule(
        "Install/enable autonomous Opportunity Loop timer if tests pass",
        (
            ("systemd_enabled", ("empire-opportunity-loop.timer",)),
            ("systemd_active", ("empire-opportunity-loop.timer",)),
            (
                "json_file_key",
                (
                    "runtime/opportunity_radar/loop_latest.json",
                    "automatic_quant_review",
                    True,
                ),
            ),
            (
                "json_file_key",
                (
                    "runtime/opportunity_radar/loop_latest.json",
                    "execution_authority",
                    "none",
                ),
            ),
        ),
    ),
    Rule(
        "Automatic Founder snapshot refresh",
        (
            ("systemd_active", ("empire-department-cycle.timer",)),
            ("systemd_enabled", ("empire-department-cycle.timer",)),
            ("json_file_recent", (
                "runtime/astra/executive_latest.json",
                "empire.astra.executive.v2", "generated_at", 20,
            )),
            ("json_file_key", (
                "runtime/astra/executive_latest.json",
                "execution_authority", "none",
            )),
            ("json_file_recent", (
                "runtime/execution_plane/empire_completion_program_progress.json",
                "empire.completion-program-progress.v1", "updated_at", 20,
            )),
        ),
    ),
    Rule(
        "Service/timer health",
        (
            ("systemd_active", ("empire-department-cycle.timer",)),
            ("systemd_enabled", ("empire-department-cycle.timer",)),
            ("json_file_recent", (
                "runtime/ops_control/latest.json",
                "empire.ops_control_cycle.v1", "observed_at", 20,
            )),
            ("json_file_key", (
                "runtime/ops_control/latest.json",
                "health_domains.services_and_timers", "HEALTHY",
            )),
        ),
    ),
    # Existing scheduled competitor->account research->brief chain.
    # A timer alone, stale artifacts or empty research is not proof.
    Rule(
        "Scheduled competitor sweeps",
        (
            ("systemd_enabled", ("empire-opportunity-brief.timer",)),
            ("systemd_active", ("empire-opportunity-brief.timer",)),
            ("json_file_recent", (
                "runtime/competitive_intelligence/competitor_audience_latest.json",
                "empire.competitor_audience_runtime.v1", "generated_at", 75,
            )),
            ("json_file_key", (
                "runtime/competitive_intelligence/competitor_audience_latest.json",
                "execution_authority", "none",
            )),
            ("json_int_min", (
                "runtime/competitive_intelligence/competitor_audience_latest.json",
                "competitor_count", 1,
            )),
            ("json_file_recent", (
                "runtime/competitive_intelligence/competitor_account_research_latest.json",
                "empire.competitor_account_research_batch.v1",
                "generated_at", 75,
            )),
            ("json_file_key", (
                "runtime/competitive_intelligence/competitor_account_research_latest.json",
                "execution_authority", "none",
            )),
            ("json_int_min", (
                "runtime/competitive_intelligence/competitor_account_research_latest.json",
                "observation_count", 1,
            )),
            ("json_file_recent", (
                "runtime/competitive_intelligence/competitor_account_briefs_latest.json",
                "empire.account_intelligence_brief_batch.v1", "generated_at", 75,
            )),
            ("json_file_key", (
                "runtime/competitive_intelligence/competitor_account_briefs_latest.json",
                "execution_authority", "none",
            )),
            ("json_int_min", (
                "runtime/competitive_intelligence/competitor_account_briefs_latest.json",
                "brief_count", 1,
            )),
        ),
    ),
)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _default_http_get(url: str) -> tuple[int, str]:
    try:
        with urlopen(url, timeout=3) as response:
            return int(response.status), response.read().decode(
                "utf-8",
                errors="replace",
            )
    except HTTPError as exc:
        return int(exc.code), ""
    except (URLError, OSError):
        return 0, ""


def _default_systemd(unit: str, mode: str) -> bool:
    proc = subprocess.run(
        ["systemctl", f"is-{mode}", unit],
        capture_output=True,
        text=True,
        check=False,
        timeout=4,
    )
    return proc.returncode == 0 and proc.stdout.strip() in {
        "active",
        "enabled",
        "static",
    }


def _nested(data: dict[str, Any], key: str) -> Any:
    current: Any = data
    for part in key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _probe(
    root: Path,
    kind: str,
    args: tuple[Any, ...],
    *,
    http_get: Callable[[str], tuple[int, str]],
    systemd_probe: Callable[[str, str], bool],
    now: datetime | None = None,
) -> dict[str, Any]:
    if kind == "http_status":
        url, expected = args
        code, _ = http_get(str(url))
        return {
            "kind": kind,
            "target": url,
            "passed": code == int(expected),
            "observed": code,
            "expected": expected,
        }

    if kind == "http_contains":
        url, needle = args
        code, body = http_get(str(url))
        passed = code == 200 and str(needle).lower() in body.lower()
        return {
            "kind": kind,
            "target": url,
            "passed": passed,
            "observed_status": code,
            "expected_contains": needle,
        }

    if kind == "http_json":
        url, key, expected = args
        code, body = http_get(str(url))
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}
        observed = _nested(data, str(key))
        return {
            "kind": kind,
            "target": url,
            "key": key,
            "passed": code == 200 and observed == expected,
            "observed_status": code,
            "observed": observed,
            "expected": expected,
        }

    if kind == "json_file_recent":
        rel, schema, timestamp_key, max_age_minutes = args
        data = _read_json(root / str(rel)) or {}
        observed_schema = data.get("schema_version")
        raw_stamp = _nested(data, str(timestamp_key))
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            return {"kind": kind, "target": rel, "passed": False,
                    "reason": "naive_verification_clock"}
        current = current.astimezone(timezone.utc)
        timestamp = None
        if isinstance(raw_stamp, str):
            try:
                parsed = datetime.fromisoformat(
                    raw_stamp.replace("Z", "+00:00")
                )
                if parsed.tzinfo is not None:
                    timestamp = parsed.astimezone(timezone.utc)
            except ValueError:
                pass
        age = ((current - timestamp).total_seconds() / 60
               if timestamp is not None else None)
        try:
            age_limit = int(max_age_minutes)
        except (TypeError, ValueError):
            age_limit = -1
        return {
            "kind": kind, "target": str(rel),
            "timestamp_key": str(timestamp_key),
            "expected_schema": str(schema),
            "observed_schema": observed_schema,
            "age_minutes": round(age, 3) if age is not None else None,
            "passed": (
                observed_schema == schema
                and age_limit > 0
                and age is not None
                and -2 <= age <= age_limit
            ),
        }

    if kind == "json_file_key":
        rel, key, expected = args
        data = _read_json(root / str(rel)) or {}
        observed = _nested(data, str(key))
        return {
            "kind": kind,
            "target": rel,
            "key": key,
            "passed": observed == expected,
            "observed": observed,
            "expected": expected,
        }

    if kind == "json_counts_equal":
        rel, left_key, right_key = args
        data = _read_json(root / str(rel)) or {}
        left = _nested(data, str(left_key))
        right = _nested(data, str(right_key))
        return {
            "kind": kind,
            "target": rel,
            "passed": (
                isinstance(left, int)
                and isinstance(right, int)
                and left == right
                and right > 0
            ),
            "observed": {str(left_key): left, str(right_key): right},
        }

    if kind == "json_int_min":
        rel, key, minimum = args
        data = _read_json(root / str(rel)) or {}
        observed = _nested(data, str(key))
        # bool is an int subclass in Python: do not admit True as a count.
        passed = (
            type(observed) is int
            and type(minimum) is int
            and minimum >= 1
            and observed >= minimum
        )
        return {
            "kind": kind,
            "target": str(rel),
            "key": str(key),
            "observed": observed,
            "minimum": minimum,
            "passed": passed,
        }

    if kind == "json_list_empty":
        rel, key = args
        data = _read_json(root / str(rel)) or {}
        observed = _nested(data, str(key))
        return {
            "kind": kind,
            "target": rel,
            "key": key,
            "passed": isinstance(observed, list) and len(observed) == 0,
            "observed_count": (
                len(observed) if isinstance(observed, list) else None
            ),
        }

    if kind == "systemd_enabled":
        (unit,) = args
        passed = systemd_probe(str(unit), "enabled")
        return {
            "kind": kind,
            "target": unit,
            "passed": passed,
        }

    if kind == "systemd_active":
        (unit,) = args
        passed = systemd_probe(str(unit), "active")
        return {
            "kind": kind,
            "target": unit,
            "passed": passed,
        }

    return {
        "kind": kind,
        "passed": False,
        "reason": "unsupported_probe_kind",
    }


def run_completion_live_proof(
    repo_root: str | Path,
    *,
    now: datetime | None = None,
    http_get: Callable[[str], tuple[int, str]] | None = None,
    systemd_probe: Callable[[str, str], bool] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    checklist = root / "docs/MASTER_REMAINING_CHECKLIST.md"
    if not checklist.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "UNAVAILABLE",
            "reason": "canonical_checklist_missing",
            "execution_authority": "none",
        }

    get = http_get or _default_http_get
    systemd = systemd_probe or _default_systemd
    pending_rows: dict[str, list[Any]] = {}
    for row in parse_checklist(checklist):
        if row.status == "PENDING":
            pending_rows.setdefault(row.item, []).append(row)
    # Duplicate checklist names must never silently pick the last line.
    pending = {
        item: rows[0]
        for item, rows in pending_rows.items()
        if len(rows) == 1
    }

    results: list[dict[str, Any]] = []
    checkpoints_written: list[str] = []
    checkpoints_invalidated: list[str] = []

    for rule in RULES:
        row = pending.get(rule.item)
        if row is None:
            # A previously unique title might become ambiguous after a
            # checklist change. Revoke any checkpoint generated by this
            # exact verifier rather than closing either duplicate line.
            duplicates = pending_rows.get(rule.item) or []
            if len(duplicates) > 1:
                for duplicate in duplicates:
                    checkpoint = (
                        root / CHECKPOINTS
                        / f"auto_live_checklist_line_{str(duplicate.line).zfill(4)}.json"
                    )
                    existing = _read_json(checkpoint)
                    if (
                        existing is not None
                        and existing.get("scope") == "automated_exact_checklist_live_proof"
                        and existing.get("checklist_lines") == [duplicate.line]
                        and existing.get("checklist_items") == [rule.item]
                    ):
                        checkpoint.unlink()
                        checkpoints_invalidated.append(
                            str(checkpoint.relative_to(root))
                        )
            continue
        probes = [
            _probe(
                root,
                kind,
                args,
                http_get=get,
                systemd_probe=systemd,
                now=current,
            )
            for kind, args in rule.probes
        ]
        passed = bool(probes) and all(p.get("passed") is True for p in probes)
        checkpoint_ref = None
        safe = str(row.line).zfill(4)
        checkpoint = (
            root
            / CHECKPOINTS
            / f"auto_live_checklist_line_{safe}.json"
        )
        if not passed:
            # Do not leave an earlier auto-proof checkpoint actionable
            # after current health, schema or freshness verification fails.
            earlier = _read_json(checkpoint)
            if (
                earlier is not None
                and earlier.get("scope") == "automated_exact_checklist_live_proof"
                and earlier.get("checklist_lines") == [row.line]
                and earlier.get("checklist_items") == [row.item]
            ):
                checkpoint.unlink()
                checkpoints_invalidated.append(str(checkpoint.relative_to(root)))
        if passed:
            packet = {
                "schema_version": "empire.completion-checkpoint.v1",
                "program": "empire_os_full_completion",
                "scope": "automated_exact_checklist_live_proof",
                "stage": "LIVE_VERIFY_DONE",
                "state": "DONE",
                "recorded_at": current.isoformat(),
                "checklist_lines": [row.line],
                "checklist_items": [row.item],
                "evidence_refs": [
                    f"live_probe:{rule.item}:{index}"
                    for index, _ in enumerate(probes, start=1)
                ],
                "probes": probes,
                "read_only": True,
                "synthetic_evidence_used": False,
                "founder_approval_inferred": False,
                "external_action_performed": False,
                "execution_authority": "none",
            }
            _atomic_write(checkpoint, packet)
            checkpoint_ref = str(checkpoint.relative_to(root))
            checkpoints_written.append(checkpoint_ref)

        results.append({
            "line": row.line,
            "item": row.item,
            "passed": passed,
            "checkpoint_ref": checkpoint_ref,
            "probes": probes,
        })

    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "AVAILABLE",
        "generated_at": current.isoformat(),
        "configured_rule_count": len(RULES),
        "pending_rule_match_count": len(results),
        "live_proof_pass_count": sum(r["passed"] for r in results),
        "live_proof_blocked_count": sum(not r["passed"] for r in results),
        "checkpoints_written": checkpoints_written,
        "checkpoints_invalidated": checkpoints_invalidated,
        "results": results,
        "network_scope": "localhost_only",
        "read_only": True,
        "synthetic_evidence_used": False,
        "founder_approval_inferred": False,
        "external_action_performed": False,
        "execution_authority": "none",
    }
    _atomic_write(root / OUTPUT, payload)
    return payload
