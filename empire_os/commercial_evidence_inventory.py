"""Read-only canonical qualification/Omega inventory for commercial-loop evidence."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Callable

from empire_os.commercial_loop_observer import CommercialLoopObservation
from empire_os.intelligence.omega import MODEL_VERSION
from empire_os.qualification_worker_v2 import SCORING_ENGINE, SCORING_VERSION

Reader = Callable[[str, dict[str, str]], Any]


def fetch_qualification_omega_inventory(reader: Reader, *, now: datetime | None = None, max_age_days: int = 7) -> dict[str, CommercialLoopObservation]:
    """Bounded read of verified, recent canonical evidence; stale is unknown."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or max_age_days < 1:
        raise ValueError("timezone-aware now and positive max_age_days required")
    specs = (
        ('qualification_v2', '/rest/v1/prospect_qualifications', {
            'select': 'id,prospect_id,entity_id,scored_at',
            'scoring_engine': f'eq.{SCORING_ENGINE}',
            'scoring_version': f'eq.{SCORING_VERSION}',
            'status': 'eq.scored',
            'entity_id': 'not.is.null',
            'order': 'scored_at.desc', 'limit': '1',
        }),
        ('omega_projection', '/rest/v1/intelligence_scores', {
            'select': 'id,entity_id,scored_at',
            'entity_type': 'eq.company',
            'score_type': 'eq.omega_opportunity',
            'model_key': f'eq.{MODEL_VERSION}',
            'order': 'scored_at.desc', 'limit': '1',
        }),
    )
    result = {}
    for stage, path, params in specs:
        try:
            rows = reader(path, params)
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise ValueError('invalid canonical inventory response')
            verified = bool(rows) and all(row.get('id') and row.get('entity_id') and row.get('scored_at') for row in rows)
            observed = None if rows else False
            detail = 'canonical record invalid' if rows else 'no matching canonical record'
            if verified:
                timestamp = datetime.fromisoformat(str(rows[0]['scored_at']).replace('Z', '+00:00'))
                if timestamp.tzinfo is None:
                    raise ValueError('naive canonical timestamp')
                age = current.astimezone(timezone.utc) - timestamp.astimezone(timezone.utc)
                if timedelta(0) <= age <= timedelta(days=max_age_days):
                    observed = True
                    detail = 'recent canonical persisted record observed'
                else:
                    detail = 'canonical evidence stale or future-dated'
        except (ValueError, OSError, RuntimeError, TypeError) as exc:
            observed = None
            detail = 'canonical inventory read unavailable:' + type(exc).__name__
        result[stage] = CommercialLoopObservation(stage, observed, evidence_ref='canonical:' + path.rsplit('/',1)[-1], detail=detail)
    return result
