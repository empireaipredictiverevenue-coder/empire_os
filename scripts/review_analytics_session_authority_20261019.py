#!/usr/bin/env python3
"""Read-only local session/consent lifecycle validation for Empire Analytics.

Executes only SYNTHETIC in-memory records. Never creates a web session,
sets a cookie, reads visitors, contacts the web, or touches EmpireDB.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

from empire_os.analytics.first_party_event_contract import (
    EventContractHeld, simulate_verified_batch,
)
from empire_os.analytics.offline_session_authority import (
    OfflineSessionAuthority, ORIGIN,
)
from empire_os.analytics.measurement_readiness import review_existing_monitor


def inspect() -> dict[str, object]:
    static = review_existing_monitor()
    clock = lambda: datetime(2026, 10, 19, 11, 0, tzinfo=timezone.utc)
    policy = "draft-analytics-prototype"
    ledger = OfflineSessionAuthority(
        policy_revision=policy,
        resolve_trusted_acquisition=lambda: (
            "organic_search", "server_verified_referral"),
        clock=clock,
        enable_offline_simulation=True,
    )
    nonce = ledger.open_session(site=ORIGIN)
    raw = [{
        "event_nonce": "a" * 32,
        "session_nonce": nonce,
        "event_type": "page_view",
        "occurred_at": "2026-10-19T11:00:00Z",
        "page_path": "/",
    }]
    def simulate():
        return simulate_verified_batch(
            raw, approved_paths=["/"],
            resolve_server_consent=ledger.resolve_consent,
            resolve_server_channel=ledger.resolve_acquisition,
            now=clock(),
        )
    default_denied = False
    try:
        simulate()
    except EventContractHeld:
        default_denied = True
    ledger.decide(session_nonce=nonce, decision="granted",
                  trusted_server_decision=True, policy_revision=policy)
    candidate = simulate()
    simulated_accepted = (
        candidate["status"] == "OFFLINE_CONSENT_GATED_CONTRACT_SIMULATION"
        and candidate["simulated_sessions"] == 1
        and candidate["real_visitors_verified"] is False
        and candidate["realised_revenue_verified"] is False
    )
    ledger.revoke(session_nonce=nonce, trusted_server_decision=True,
                  policy_revision=policy)
    revoked_denied = False
    try:
        simulate()
    except EventContractHeld:
        revoked_denied = True

    valid = default_denied and simulated_accepted and revoked_denied
    return {
        "schema_version": "empire.analytics.session_authority_readiness.v1",
        "status": "OFFLINE_SESSION_CONSENT_AND_HTTP_CONTRACT_VERIFIED"
                  if valid else "HELD_OFFLINE_SESSION_LIFECYCLE",
        "source": "local_synthetic_nonpersistent_evidence",
        "mode": "READ_ONLY",
        "existing_tag_intelligence_status": static["status"],
        "default_consent_denial_test_passed": default_denied,
        "simulated_server_consent_grant_test_passed": simulated_accepted,
        "revocation_blocks_repeated_event_test_passed": revoked_denied,
        "server_acquisition_resolver_test_passed": simulated_accepted,
        "production_consent_authority_active": False,
        "real_website_analytics_consent_verified": False,
        "public_analytics_collector_active": False,
        "persistent_empiredb_analytics_ledger_active": False,
        "real_sessions_observed": False,
        "revenue_verified": False,
        "database_writes": False,
        "live_service_changed": False,
        "tracking_added": False,
        "execution_authority": "NONE",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only", required=True, action="store_true")
    parser.parse_args(argv)
    report = inspect()
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "OFFLINE_SESSION_CONSENT_AND_HTTP_CONTRACT_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
