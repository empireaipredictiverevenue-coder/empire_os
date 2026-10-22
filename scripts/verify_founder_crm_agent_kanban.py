#!/usr/bin/env python3
"""Founder-only SSH TTY canary for the EXISTING CRM's authenticated Kanban.

Uses existing local password login once. Does not log/store password, bearer,
tenant identifiers, task details, buyer data, private keys or raw replies.
No new accounts, tasks, emails, databases, token issuers or scopes.
"""
from __future__ import annotations

import getpass
import json
import os
import pwd
import sys
from http.client import HTTPConnection
from typing import Any, Mapping

from scripts.redeem_founder_crm_invitation_local import EMAIL, TENANT, post

KANBAN_PATH = "/v1/revenue-crm/department-kanban"
HOST = "127.0.0.1"
PORT = 8783
LANES = ("ready", "running", "review", "blocked", "done", "failed")


def _read_board(*, token: str | None, spoof: bool = False) -> tuple[int, Any]:
    path = KANBAN_PATH + "?max_cards_per_lane=10"
    headers = {"Accept": "application/json"}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    if spoof:
        # The server MUST disregard caller-supplied tenant claims.
        headers["X-Tenant-ID"] = "00000000-0000-0000-0000-000000000999"
        headers["X-Role"] = "founder"
        path += "&tenant_id=00000000-0000-0000-0000-000000000999"
    connection = HTTPConnection(HOST, PORT, timeout=12)
    try:
        connection.request("GET", path, headers=headers)
        response = connection.getresponse()
        payload = response.read(65_537)
        if len(payload) > 65_536:
            raise ValueError("oversized_CRM_kanban_reply")
        parsed = json.loads(payload) if response.status == 200 else None
        return response.status, parsed
    finally:
        connection.close()


def _validate_board(board: Any) -> tuple[int, ...]:
    if not isinstance(board, dict):
        raise ValueError("invalid_authenticated_board")
    if (
        board.get("schema_version") != "empire.departments.kanban.v1"
        or board.get("tenant_scope") != "explicit_tenant"
        or board.get("source") != "canonical_department_work_queue"
        or board.get("read_only") is not True
        or board.get("execution_authority") != "none"
    ):
        raise ValueError("authenticated_board_contract_mismatch")
    lanes = board.get("lanes")
    if not isinstance(lanes, dict) or set(lanes) != set(LANES):
        raise ValueError("incomplete_canonical_queue_lanes")
    counts = []
    for lane in LANES:
        data = lanes[lane]
        if not isinstance(data, dict) or type(data.get("total")) is not int:
            raise ValueError("invalid_canonical_lane_total")
        if data["total"] < 0 or not isinstance(data.get("cards"), list):
            raise ValueError("invalid_canonical_lane_cards")
        if len(data["cards"]) > min(data["total"], 10):
            raise ValueError("overlarge_canonical_lane_cards")
        for card in data["cards"]:
            if not isinstance(card, dict) or not set(card).issubset({
                "work_id", "goal_key", "department_keys", "target_component",
                "priority", "status", "has_result_evidence", "has_active_lease",
            }):
                raise ValueError("unapproved_canonical_card_field")
        counts.append(data["total"])
    return tuple(counts)


def verify_authenticated_board() -> int:
    """Run with human-owned password on TTY. Statuses printed, never bearer."""
    guest_status, _ = _read_board(token=None)
    print("KANBAN_ANONYMOUS_HTTP=" + str(guest_status))
    forged_status, _ = _read_board(token=None, spoof=True)
    print("KANBAN_FORGED_TENANT_HTTP=" + str(forged_status))
    if guest_status != 401 or forged_status != 401:
        print("KANBAN_CANARY=FAILED_ANONYMOUS_SCOPE_DENIAL")
        return 4

    password = getpass.getpass("Existing EmpireOS CRM founder password: ")
    if not 14 <= len(password) <= 256:
        password = ""
        print("KANBAN_CANARY=INVALID_PASSWORD_LENGTH")
        return 2
    status, credentials = post(
        "/v1/revenue-crm/auth/login",
        {"email": EMAIL, "password": password, "tenant_id": TENANT},
    )
    password = ""
    if status != 200 or not isinstance(credentials.get("access_token"), str):
        print("KANBAN_CANARY=EXISTING_CRM_LOGIN_NOT_VERIFIED")
        return 4

    token = credentials["access_token"]
    credentials.clear()
    try:
        normal_status, normal = _read_board(token=token)
        spoof_status, spoofed = _read_board(token=token, spoof=True)
    finally:
        token = ""
    print("KANBAN_AUTHENTICATED_HTTP=" + str(normal_status))
    print("KANBAN_AUTHENTICATED_WITH_SPOOFED_TENANT_HTTP=" + str(spoof_status))
    if normal_status != 200 or spoof_status != 200:
        print("KANBAN_CANARY=AUTHENTICATED_READ_NOT_VERIFIED")
        return 4
    normal_totals = _validate_board(normal)
    spoof_totals = _validate_board(spoofed)
    if normal != spoofed or normal_totals != spoof_totals:
        print("KANBAN_CANARY=SNAPSHOT_CHANGED_OR_TENANT_SCOPE_MISMATCH")
        return 4
    print("KANBAN_BOARD_LANE_TOTALS=" + ",".join(
        f"{lane}:{total}" for lane, total in zip(LANES, normal_totals)
    ))
    print("KANBAN_CANARY=EXISTING_FOUNDER_TENANT_READ_VERIFIED")
    print("KANBAN_NOTE=ONLY_CURRENT_FOUNDER_TENANT_TESTED")
    return 0


def main() -> int:
    if sys.argv[1:] != ["--interactive-founder-read-only"]:
        print("KANBAN_CANARY=EXACT_INTERACTIVE_FLAG_REQUIRED")
        return 3
    if not sys.stdin.isatty() or os.geteuid() != pwd.getpwnam("ubuntu").pw_uid:
        print("KANBAN_CANARY=SSH_TTY_AND_OWNER_REQUIRED")
        return 3
    try:
        return verify_authenticated_board()
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError):
        print("KANBAN_CANARY=READ_FAILED_CLOSED")
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
