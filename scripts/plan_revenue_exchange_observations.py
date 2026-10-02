#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from empire_os.revenue_exchange_observation_planner import plan_from_runtime_artifacts

ROOT=Path('/srv/empire_os')
OUT=ROOT/'runtime/revenue_exchange/observation_plan_latest.json'

def read(path: Path):
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else {}
    except (OSError,json.JSONDecodeError):
        return {}

def main() -> int:
    payload=plan_from_runtime_artifacts(
        commercial_exchange=read(ROOT/'runtime/commercial_exchange/latest.json'),
        buyer_capacity_readiness=read(ROOT/'runtime/buyer_capacity_readiness/latest.json'),
        commercial_catalog=read(ROOT/'runtime/commercial_catalog/latest.json'),
    )
    OUT.parent.mkdir(parents=True,exist_ok=True)
    tmp=OUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    tmp.replace(OUT)
    print(json.dumps({
        'proposal_ready_count':payload['proposal_ready_count'],
        'market_candidate_count':payload['market_candidate_count'],
        'global_blockers':payload['global_blockers'],
        'database_write':payload['database_write'],
        'execution_authority':payload['execution_authority'],
    },indent=2,sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
