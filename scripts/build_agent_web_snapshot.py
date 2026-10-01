#!/usr/bin/env python3
"""Regenerate the canonical Agent Web snapshot from current observations."""
import json
from empire_os.agent_web_runtime import SNAPSHOT_PATH
from empire_os.agent_web_snapshot import (
    FreshPublicSearchUnavailable, MarketObservationsUnavailable, refresh_snapshot,
)
from empire_os.intelligence_materializer_transport import PostgresIntelligenceMaterializer
from empire_os.intelligence_materializer_env import load_materializer_env


def _unavailable(reason: str) -> int:
    print(json.dumps({'ok': False, 'status': 'producer_unavailable',
                      'snapshot_replaced': False, 'reason': reason}))
    return 1


def main() -> int:
    try:
        env = load_materializer_env()
        writer = PostgresIntelligenceMaterializer(env['EMPIRE_INTELLIGENCE_MATERIALIZER_DSN'])
    except Exception:
        return _unavailable('dedicated_empiredb_unavailable')
    try:
        payload = refresh_snapshot(SNAPSHOT_PATH, writer)
    except MarketObservationsUnavailable:
        return _unavailable('dedicated_empiredb_unavailable')
    except FreshPublicSearchUnavailable:
        return _unavailable('fresh_public_search_unavailable')
    except Exception:
        return _unavailable('snapshot_production_failed')
    print(json.dumps({'ok': True, 'counts': payload['counts'], 'generated_at': payload['generated_at']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
