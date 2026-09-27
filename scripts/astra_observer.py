#!/usr/bin/env python3
"""CLI wrapper for the read-only Phase 4 Astra observer."""
from __future__ import annotations

import argparse
import json
import os
import sys

from empire_os.astra_observer import (
    AstraObserverError,
    run_observer_cycle,
)
from empire_os.astra_token_transport import SupabaseTokenAstraRpc
from empire_os.outcome_role_transport import OutcomeTransportError


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Empire Phase 4 Astra observer")
    p.add_argument("--limit", type=int, default=_env_int("EMPIRE_ASTRA_FEEDBACK_LIMIT", 100))
    p.add_argument("--min-samples", type=int, default=_env_int("EMPIRE_ASTRA_MIN_OUTCOME_SAMPLES", 20))
    p.add_argument("--min-conversions", type=int, default=_env_int("EMPIRE_ASTRA_MIN_CONVERSIONS", 5))
    p.add_argument(
        "--mode",
        default=os.getenv("EMPIRE_ASTRA_MODE", "OBSERVE"),
    )
    p.add_argument(
        "--output",
        default=os.getenv(
            "EMPIRE_ASTRA_OUTPUT_PATH",
            "/srv/empire_os/runtime/astra/latest.json",
        ),
    )
    return p


def _rpc_config():
    url = os.getenv("EMPIRE_ASTRA_SUPABASE_URL", "").strip()
    key = os.getenv("EMPIRE_ASTRA_SUPABASE_PUBLISHABLE_KEY", "").strip()
    token_file = os.getenv("EMPIRE_ASTRA_OBSERVER_TOKEN_FILE", "").strip()
    if url or key or token_file:
        if not (url and key and token_file):
            raise AstraObserverError("incomplete token-authenticated Astra RPC config")
        def factory(_dsn, _role):
            return SupabaseTokenAstraRpc(url, key, token_file)
        return "token-rpc", factory
    return os.getenv("EMPIRE_ASTRA_OBSERVER_DSN", ""), None


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    dsn, rpc_factory = _rpc_config()
    payload = run_observer_cycle(
        dsn=dsn,
        mode=args.mode,
        feedback_limit=args.limit,
        min_samples=args.min_samples,
        min_conversions=args.min_conversions,
        operational_snapshot_json=os.getenv(
            "EMPIRE_ASTRA_OPERATIONAL_SNAPSHOT_JSON"
        ),
        output_path=args.output,
        **({"rpc_factory": rpc_factory} if rpc_factory is not None else {}),
    )
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AstraObserverError, OutcomeTransportError, ValueError) as exc:
        print(
            json.dumps({"ok": False, "error": str(exc)}),
            file=sys.stderr,
        )
        raise SystemExit(2)
