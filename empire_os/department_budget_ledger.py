"""Durable resource-budget ledger for Astra department work.

This module accounts for model-token / external-cost reservations only. It never
authorizes company cash spend or any external/commercial action.
"""
from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from empire_os.department_work_queue import DepartmentWorkQueue


POLICY_RELATIVE_PATH = Path("config/department_budgets.json")
RUNTIME_RELATIVE_ROOT = Path("runtime/departments/budget")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _nonnegative_int(value: Any, field: str) -> int:
    if value in (None, ""):
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if number < 0:
        raise ValueError(f"{field} must be nonnegative")
    return number


def _limit(value: Any) -> int | None:
    if value is None:
        return None
    return _nonnegative_int(value, "budget limit")


@dataclass(frozen=True)
class BudgetDecision:
    allowed: bool
    reason: str
    period: str
    reservation_id: str | None
    requested_model_tokens: int
    requested_external_cost_cents: int
    department_keys: tuple[str, ...]
    cash_spend_authority: bool = False
    external_execution_authority: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["department_keys"] = list(self.department_keys)
        return data


class DepartmentBudgetLedger:
    def __init__(self, repo_root: str | Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.root = self.repo_root / RUNTIME_RELATIVE_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        self.ledger_path = self.root / "reservations.jsonl"
        self.snapshot_path = self.root / "latest.json"
        self.lock_path = self.root / ".budget.lock"
        self.lock_path.touch(exist_ok=True)
        os.chmod(self.lock_path, 0o600)

    @contextmanager
    def _locked(self):
        with self.lock_path.open("r+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _policy(self) -> dict[str, Any]:
        path = self.repo_root / POLICY_RELATIVE_PATH
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {
                "schema_version": "empire.department-budget-policy.v1",
                "period": "monthly",
                "company": {},
                "departments": {},
                "configured": False,
            }
        if not isinstance(value, dict):
            return {
                "schema_version": "empire.department-budget-policy.v1",
                "period": "monthly",
                "company": {},
                "departments": {},
                "configured": False,
            }
        return {
            **value,
            "configured": True,
        }

    @staticmethod
    def _request(item: Any) -> tuple[int, int]:
        intelligence = (
            item.intelligence_request
            if isinstance(getattr(item, "intelligence_request", None), dict)
            else {}
        )
        raw = intelligence.get("budget")
        budget = raw if isinstance(raw, Mapping) else {}
        return (
            _nonnegative_int(
                budget.get("requested_model_tokens"),
                "requested_model_tokens",
            ),
            _nonnegative_int(
                budget.get("requested_external_cost_cents"),
                "requested_external_cost_cents",
            ),
        )

    def _events(self, *, period: str | None = None) -> list[dict[str, Any]]:
        target_period = period or _period()
        try:
            lines = self.ledger_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        events: list[dict[str, Any]] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            if str(row.get("period") or "") != target_period:
                continue
            events.append(row)
        return events

    @staticmethod
    def _usage(events: list[dict[str, Any]]) -> dict[str, Any]:
        company_tokens = 0
        company_cost = 0
        departments: dict[str, dict[str, int]] = {}
        for row in events:
            tokens = int(row.get("requested_model_tokens") or 0)
            cost = int(row.get("requested_external_cost_cents") or 0)
            company_tokens += tokens
            company_cost += cost
            for department in row.get("department_keys") or []:
                key = str(department).strip()
                if not key:
                    continue
                bucket = departments.setdefault(
                    key,
                    {"model_tokens": 0, "external_cost_cents": 0},
                )
                bucket["model_tokens"] += tokens
                bucket["external_cost_cents"] += cost
        return {
            "company": {
                "model_tokens": company_tokens,
                "external_cost_cents": company_cost,
            },
            "departments": departments,
        }

    @staticmethod
    def _policy_limits(
        policy: Mapping[str, Any],
        department: str,
    ) -> dict[str, int | None]:
        departments = policy.get("departments")
        rows = departments if isinstance(departments, Mapping) else {}
        raw = rows.get(department)
        row = raw if isinstance(raw, Mapping) else {}
        return {
            "model_tokens": _limit(row.get("model_tokens")),
            "external_cost_cents": _limit(row.get("external_cost_cents")),
        }

    @staticmethod
    def _company_limits(policy: Mapping[str, Any]) -> dict[str, int | None]:
        raw = policy.get("company")
        row = raw if isinstance(raw, Mapping) else {}
        return {
            "model_tokens": _limit(row.get("model_tokens")),
            "external_cost_cents": _limit(row.get("external_cost_cents")),
        }

    def reserve(self, item: Any) -> BudgetDecision:
        requested_tokens, requested_cost = self._request(item)
        departments = tuple(
            str(value).strip()
            for value in (getattr(item, "department_keys", ()) or ())
            if str(value).strip()
        )
        period = _period()
        if requested_tokens == 0 and requested_cost == 0:
            return BudgetDecision(
                allowed=True,
                reason="no_explicit_resource_budget_required",
                period=period,
                reservation_id=None,
                requested_model_tokens=0,
                requested_external_cost_cents=0,
                department_keys=departments,
            )
        if not departments:
            return BudgetDecision(
                allowed=False,
                reason="department_budget_owner_required",
                period=period,
                reservation_id=None,
                requested_model_tokens=requested_tokens,
                requested_external_cost_cents=requested_cost,
                department_keys=(),
            )

        work_id = str(getattr(item, "id", "")).strip()
        attempt = max(1, int(getattr(item, "attempts", 1) or 1))
        reservation_id = f"{work_id}:{attempt}"

        with self._locked():
            events = self._events(period=period)
            for row in events:
                if str(row.get("reservation_id") or "") == reservation_id:
                    return BudgetDecision(
                        allowed=True,
                        reason="reservation_already_exists",
                        period=period,
                        reservation_id=reservation_id,
                        requested_model_tokens=requested_tokens,
                        requested_external_cost_cents=requested_cost,
                        department_keys=departments,
                    )

            policy = self._policy()
            usage = self._usage(events)
            for department in departments:
                limits = self._policy_limits(policy, department)
                current = (usage["departments"].get(department) or {})
                if requested_tokens > 0 and limits["model_tokens"] is None:
                    return BudgetDecision(
                        False,
                        "department_token_budget_unconfigured",
                        period,
                        None,
                        requested_tokens,
                        requested_cost,
                        departments,
                    )
                if requested_cost > 0 and limits["external_cost_cents"] is None:
                    return BudgetDecision(
                        False,
                        "department_cost_budget_unconfigured",
                        period,
                        None,
                        requested_tokens,
                        requested_cost,
                        departments,
                    )
                if (
                    requested_tokens > 0
                    and int(current.get("model_tokens") or 0) + requested_tokens
                    > int(limits["model_tokens"] or 0)
                ):
                    return BudgetDecision(
                        False,
                        "department_token_budget_exhausted",
                        period,
                        None,
                        requested_tokens,
                        requested_cost,
                        departments,
                    )
                if (
                    requested_cost > 0
                    and int(current.get("external_cost_cents") or 0) + requested_cost
                    > int(limits["external_cost_cents"] or 0)
                ):
                    return BudgetDecision(
                        False,
                        "department_cost_budget_exhausted",
                        period,
                        None,
                        requested_tokens,
                        requested_cost,
                        departments,
                    )

            company_limits = self._company_limits(policy)
            company_usage = usage["company"]
            if (
                requested_tokens > 0
                and company_limits["model_tokens"] is not None
                and int(company_usage["model_tokens"]) + requested_tokens
                > int(company_limits["model_tokens"])
            ):
                return BudgetDecision(
                    False,
                    "company_token_budget_exhausted",
                    period,
                    None,
                    requested_tokens,
                    requested_cost,
                    departments,
                )
            if (
                requested_cost > 0
                and company_limits["external_cost_cents"] is not None
                and int(company_usage["external_cost_cents"]) + requested_cost
                > int(company_limits["external_cost_cents"])
            ):
                return BudgetDecision(
                    False,
                    "company_cost_budget_exhausted",
                    period,
                    None,
                    requested_tokens,
                    requested_cost,
                    departments,
                )

            event = {
                "schema_version": "empire.department-budget-reservation.v1",
                "reservation_id": reservation_id,
                "period": period,
                "reserved_at": _now(),
                "work_id": work_id,
                "plan_id": str(getattr(item, "plan_id", "") or ""),
                "step_id": str(getattr(item, "step_id", "") or ""),
                "attempt": attempt,
                "department_keys": list(departments),
                "requested_model_tokens": requested_tokens,
                "requested_external_cost_cents": requested_cost,
                "cash_spend_authority": False,
                "external_execution_authority": False,
                "execution_authority": "none",
            }
            with self.ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, sort_keys=True) + "\n")
            os.chmod(self.ledger_path, 0o600)

        return BudgetDecision(
            True,
            "budget_reserved",
            period,
            reservation_id,
            requested_tokens,
            requested_cost,
            departments,
        )

    def _work_index(self) -> dict[str, dict[str, Any]]:
        queue = DepartmentWorkQueue(self.repo_root)
        rows: dict[str, dict[str, Any]] = {}
        for state, directory in (
            ("READY", queue.ready),
            ("RUNNING", queue.running),
            ("REVIEW", queue.review),
            ("DONE", queue.done),
            ("BLOCKED", queue.blocked),
            ("FAILED", queue.failed),
        ):
            for path in directory.glob("*.json"):
                try:
                    row = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if isinstance(row, dict):
                    rows[str(row.get("id") or path.stem)] = {
                        **row,
                        "queue_state": state,
                    }
        return rows

    @staticmethod
    def _status_for(
        limit: int | None,
        accounted: int,
    ) -> str:
        if limit is None:
            return "UNCONFIGURED"
        if accounted >= limit:
            return "EXHAUSTED"
        return "WITHIN_BUDGET"

    def build_snapshot(self) -> dict[str, Any]:
        period = _period()
        policy = self._policy()
        events = self._events(period=period)
        work_index = self._work_index()
        department_names: set[str] = set()
        work_attempts: dict[str, int] = {}
        for row in work_index.values():
            attempts = max(0, int(row.get("attempts") or 0))
            for department in row.get("department_keys") or []:
                key = str(department).strip()
                if not key:
                    continue
                department_names.add(key)
                work_attempts[key] = work_attempts.get(key, 0) + attempts
        policy_departments = policy.get("departments")
        if isinstance(policy_departments, Mapping):
            department_names.update(str(key) for key in policy_departments)

        dept_reserved: dict[str, dict[str, int]] = {}
        dept_consumed: dict[str, dict[str, int]] = {}
        company_reserved = {"model_tokens": 0, "external_cost_cents": 0}
        company_consumed = {"model_tokens": 0, "external_cost_cents": 0}

        for event in events:
            work = work_index.get(str(event.get("work_id") or ""), {})
            state = str(work.get("queue_state") or "UNKNOWN")
            attempt_matches = int(work.get("attempts") or 0) == int(event.get("attempt") or 0)
            active = state == "RUNNING" and attempt_matches
            requested_tokens = int(event.get("requested_model_tokens") or 0)
            requested_cost = int(event.get("requested_external_cost_cents") or 0)
            result = work.get("result") if isinstance(work.get("result"), Mapping) else {}
            resource_usage = result.get("resource_usage") if isinstance(result, Mapping) else {}
            resource_usage = resource_usage if isinstance(resource_usage, Mapping) else {}
            observed_tokens = _nonnegative_int(
                resource_usage.get("model_tokens"),
                "resource_usage.model_tokens",
            )
            observed_cost = _nonnegative_int(
                resource_usage.get("external_cost_cents"),
                "resource_usage.external_cost_cents",
            )
            accounted_tokens = max(requested_tokens, observed_tokens)
            accounted_cost = max(requested_cost, observed_cost)
            company_bucket = company_reserved if active else company_consumed
            company_bucket["model_tokens"] += accounted_tokens
            company_bucket["external_cost_cents"] += accounted_cost
            for department in event.get("department_keys") or []:
                key = str(department).strip()
                if not key:
                    continue
                department_names.add(key)
                target = dept_reserved if active else dept_consumed
                bucket = target.setdefault(
                    key,
                    {"model_tokens": 0, "external_cost_cents": 0},
                )
                bucket["model_tokens"] += accounted_tokens
                bucket["external_cost_cents"] += accounted_cost

        departments_payload: dict[str, Any] = {}
        for department in sorted(department_names):
            limits = self._policy_limits(policy, department)
            reserved = dept_reserved.get(
                department,
                {"model_tokens": 0, "external_cost_cents": 0},
            )
            consumed = dept_consumed.get(
                department,
                {"model_tokens": 0, "external_cost_cents": 0},
            )
            accounted = {
                key: int(reserved[key]) + int(consumed[key])
                for key in ("model_tokens", "external_cost_cents")
            }
            headroom = {
                key: (
                    max(0, int(limits[key]) - accounted[key])
                    if limits[key] is not None
                    else None
                )
                for key in ("model_tokens", "external_cost_cents")
            }
            states = [
                self._status_for(limits[key], accounted[key])
                for key in ("model_tokens", "external_cost_cents")
            ]
            state = (
                "EXHAUSTED"
                if "EXHAUSTED" in states
                else "WITHIN_BUDGET"
                if "WITHIN_BUDGET" in states
                else "UNCONFIGURED"
            )
            departments_payload[department] = {
                "limits": limits,
                "reserved": reserved,
                "consumed": consumed,
                "accounted": accounted,
                "headroom": headroom,
                "work_attempts": work_attempts.get(department, 0),
                "state": state,
            }

        company_limits = self._company_limits(policy)
        company_accounted = {
            key: company_reserved[key] + company_consumed[key]
            for key in ("model_tokens", "external_cost_cents")
        }
        company_states = [
            self._status_for(company_limits[key], company_accounted[key])
            for key in ("model_tokens", "external_cost_cents")
        ]
        company_state = (
            "EXHAUSTED"
            if "EXHAUSTED" in company_states
            else "WITHIN_BUDGET"
            if "WITHIN_BUDGET" in company_states
            else "UNCONFIGURED"
        )
        payload = {
            "schema_version": "empire.department-budget-ledger.v1",
            "generated_at": _now(),
            "period": period,
            "review_cadence": "monthly",
            "policy_ref": str(POLICY_RELATIVE_PATH),
            "policy_configured": bool(policy.get("configured")),
            "reservation_count": len(events),
            "company": {
                "limits": company_limits,
                "reserved": company_reserved,
                "consumed": company_consumed,
                "accounted": company_accounted,
                "headroom": {
                    key: (
                        max(0, int(company_limits[key]) - company_accounted[key])
                        if company_limits[key] is not None
                        else None
                    )
                    for key in ("model_tokens", "external_cost_cents")
                },
                "state": company_state,
            },
            "departments": departments_payload,
            "budget_override_authority": "founder_gate",
            "cash_spend_authority": False,
            "payment_authority": False,
            "external_execution_authority": False,
            "execution_authority": "none",
        }
        tmp = self.snapshot_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.chmod(tmp, 0o600)
        tmp.replace(self.snapshot_path)
        os.chmod(self.snapshot_path, 0o600)
        return payload


def build_department_budget_snapshot(repo_root: str | Path) -> dict[str, Any]:
    return DepartmentBudgetLedger(repo_root).build_snapshot()
