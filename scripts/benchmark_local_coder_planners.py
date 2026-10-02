#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from empire_os.coder.context import ContextPack
from empire_os.coder.llama_cpp_provider import LlamaCppProvider
from empire_os.coder.models import ModelRoute
from empire_os.coder.ollama_provider import OllamaProvider
from empire_os.coder.provider import ModelRequest
from empire_os.model_matched_benchmark import score_case, summarize_model

ROOT=Path('/srv/empire_os')
DEFAULT_CASES=ROOT/'benchmarks/coder_planner_matched_cases.json'
DEFAULT_OUTPUT=ROOT/'runtime/llm/coder_planner_matched_benchmark.json'


def _context(objective: str) -> ContextPack:
    return ContextPack(
        objective=objective,
        task_state={"benchmark_only":True,"execution_authority":"none"},
        documents=(),
        symbols=(),
        token_budget_chars=4000,
    )


def _run_case(provider, provider_key: str, model: str, case):
    route=ModelRoute(provider_key,model,'matched_pair_benchmark',local=True,cost_tier=0)
    req=ModelRequest(
        task_id=f"benchmark:{case['case_id']}",
        instruction=case['instruction'],
        context=_context(case['instruction']),
        route=route,
        max_output_chars=500,
    )
    started=perf_counter()
    response=provider.complete(req)
    latency=(perf_counter()-started)*1000
    score=score_case(
        case_id=case['case_id'],
        output=response.text,
        required_groups=case['required_groups'],
    )
    return {
        **score.as_dict(),
        "provider":provider_key,
        "model":model,
        "latency_ms":round(latency,3),
        "ok":response.error is None and score.output_nonempty,
        "error":response.error,
        "usage":response.usage,
        "output_excerpt":response.text[:500],
    }


def _write_checkpoint(out: Path, *, cases, candidates, results, complete: bool):
    reports={}
    for provider_key,model,_ in candidates:
        rows=[r for r in results if r['provider']==provider_key and r['model']==model]
        reports[f'{provider_key}:{model}']=summarize_model(rows)
    payload={
        'schema_version':'empire.model_matched_benchmark.v1',
        'benchmark_only':True,
        'complete':complete,
        'matched_case_count':len(cases),
        'completed_observation_count':len(results),
        'expected_observation_count':len(cases)*len(candidates),
        'models':[f'{p}:{m}' for p,m,_ in candidates],
        'results':results,
        'reports':reports,
        'winner_selected':False,
        'production_routing_changed':False,
        'execution_authority':'none',
        'quality_promotion_authorized':False,
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
    tmp.replace(out)
    return payload


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--cases',default=str(DEFAULT_CASES))
    parser.add_argument('--output',default=str(DEFAULT_OUTPUT))
    parser.add_argument('--timeout-seconds',type=int,default=45)
    args=parser.parse_args()
    cases=json.loads(Path(args.cases).read_text())
    timeout=max(10,min(int(args.timeout_seconds),90))

    candidates=[
        (
            'llama_cpp','qwen2.5-coder:1.5b',
            LlamaCppProvider(base_url='http://127.0.0.1:11435',timeout_seconds=timeout),
        ),
        (
            'ollama','qwen2.5-coder:7b',
            OllamaProvider(base_url='http://127.0.0.1:11434',timeout_seconds=timeout,context_length=8192,think=False),
        ),
    ]
    results=[]
    out=Path(args.output)
    _write_checkpoint(out,cases=cases,candidates=candidates,results=results,complete=False)
    for provider_key,model,provider in candidates:
        for case in cases:
            results.append(_run_case(provider,provider_key,model,case))
            _write_checkpoint(out,cases=cases,candidates=candidates,results=results,complete=False)
    payload=_write_checkpoint(out,cases=cases,candidates=candidates,results=results,complete=True)
    reports=payload['reports']
    print(json.dumps({
        'output':str(out),
        'matched_case_count':len(cases),
        'reports':reports,
        'winner_selected':False,
        'execution_authority':'none',
    },indent=2,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
