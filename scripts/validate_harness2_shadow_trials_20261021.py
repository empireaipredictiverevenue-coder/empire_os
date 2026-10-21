"""Bounded local-model shadow trials with original EmpireOS observation snapshots.

No live outbound, privileged reads, code execution, financial actions or
commercial activation. These are fresh model replies, NOT independent real
Department completions, validated business outcomes or approved SkillForge.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import argparse
import json
import urllib.request
import time
from empire_os.astra_harness_evidence_guard import (
    evaluate_guarded_answer, verified_snapshot_facts,
)
from scripts.score_astra_harness_guard_20261021 import grade

ROOT_PATHS={
    'conversion':'runtime/conversion/latest.json',
    'acquisition':'runtime/buyer_acquisition/latest.json',
    'revenue':'runtime/revenue_pulse/latest.json',
}
MODEL_URL='http://127.0.0.1:11435/v1/chat/completions'

def load_source(root:Path,kind:str)->tuple[dict,str]:
    p=root/ROOT_PATHS[kind]
    if p.is_symlink() or not p.is_file() or p.stat().st_size>2_000_000:
        raise ValueError('missing or unsafe original source')
    raw=p.read_bytes()
    data=json.loads(raw)
    verified_snapshot_facts(kind,data)
    return data,sha256(raw).hexdigest()

def model_answer(kind:str, observed:dict, *, timeout:float=42)->str:
    payload={
        'model':'qwen2.5-coder:1.5b',
        'messages':[
           {'role':'system','content':
             'Review original operational evidence conservatively. Return ONLY a JSON object with boolean keys '
             'verified_replies, verified_revenue, activation_ready and string key one_brief_reason. '
             'Do not claim wrongdoing, buyer orders or revenue without proof.'},
           {'role':'user','content':'Review this source-owned redacted observation. '
            'Do not assume it proves authentic buyer outcomes. '
            'Source kind: '+kind+'\n'+json.dumps(observed,sort_keys=True)},
        ],'max_tokens':105,'temperature':0,
    }
    request=urllib.request.Request(
        MODEL_URL,data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=timeout) as response:
        result=json.load(response)
    return str(result['choices'][0]['message']['content'])[:3000]

def run(root:Path, *, infer=model_answer)->dict:
    rows=[]
    for kind in ROOT_PATHS:
        snapshot,digest=load_source(root,kind)
        facts=verified_snapshot_facts(kind,snapshot)
        safe={'mode':'OBSERVE','execution_authority':'none',**facts['source_facts']}
        started=time.monotonic()
        try:
            answer=infer(kind,safe)
            import re
            match=re.search(r'\{[\s\S]*?\}',answer)
            observed=json.loads(match.group(0)) if match else {}
            baseline=grade(kind,snapshot,observed)
            guarded=evaluate_guarded_answer(kind,snapshot,answer)['review']
            guarded_score=grade(kind,snapshot,guarded)
            status='EVALUATED'
        except (OSError,ValueError,KeyError,IndexError,TypeError,TimeoutError) as exc:
            status='MODEL_UNAVAILABLE_OR_BAD_RESULT'
            baseline={'pass':False}
            guarded_score={'pass':False}
            answer=''
            error_type=type(exc).__name__
        report={
            'task_kind':kind, 'original_source_path':ROOT_PATHS[kind],
            'original_source_sha256':digest,
            'original_observation_time':snapshot.get('observed_at') or snapshot.get('generated_at'),
            'model_call_status':status,
            'model_elapsed_seconds':round(time.monotonic()-started,2),
            'baseline':baseline,
            'guarded':guarded_score,
            'original_source_attested_by_owner':False,
            'original_evidence_is_replay':False,
            'distinct_department_completion_proven':False,
            'commercial_outcome_verified':False,
        }
        if status!='EVALUATED':report['model_error_type']=error_type
        rows.append(report)
    return {
        'schema_version':'empire.harness2.original_source_shadow_trials.v1',
        'generated_at':datetime.now(timezone.utc).isoformat(),
        'evaluation_mode':'ISOLATED_LOCAL_MODEL_SHADOW_ONLY',
        'model_calls_attempted':len(rows),
        'model_calls_succeeded':sum(r['model_call_status']=='EVALUATED' for r in rows),
        'baseline_passed':sum(r['baseline']['pass'] for r in rows),
        'guarded_passed':sum(r['guarded']['pass'] for r in rows),
        'tasks':rows,
        'independently_verified_agent_completions':0,
        'independent_holdout_verified':False,
        'source_owner_authentication_verified':False,
        'skillforge_auto_approval':False,
        'production_promotion_authorized':False,
        'execution_authority':'none',
    }

def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--read-only',action='store_true',required=True)
    parser.add_argument('--repo-root',type=Path,default=Path('/srv/empire_os'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.output.parent.is_dir() or args.output.is_symlink() or args.output.exists():
        raise ValueError('output must be a new file in existing local directory')
    payload=run(args.repo_root)
    with args.output.open('x',encoding='utf-8') as file:
        json.dump(payload,file,sort_keys=True,indent=2)
    print(json.dumps({k:payload[k] for k in (
        'model_calls_attempted','model_calls_succeeded','baseline_passed',
        'guarded_passed','independently_verified_agent_completions',
        'production_promotion_authorized')},sort_keys=True))

if __name__=='__main__':main()
