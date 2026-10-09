#!/usr/bin/env python3
"""Optional loopback-only local-model SkillForge sandbox demonstration."""
from __future__ import annotations
import json
from urllib.request import Request, urlopen
from empire_os.skillforge_sandbox import run_synthetic_ab

BASE='http://127.0.0.1:11435'


def local_completion(messages: list[dict[str,str]]) -> str:
    """Fixed loopback address, bounded timeout; never supplies tools or secrets."""
    model_request=Request(BASE+'/v1/models',method='GET')
    with urlopen(model_request,timeout=3) as response:
        model_data=json.loads(response.read(8_000).decode('utf-8'))
    model=(model_data.get('data') or [{}])[0].get('id')
    if not isinstance(model,str) or not model:
        raise ValueError('local_model_unavailable')
    payload=json.dumps({
        'model':model, 'messages':messages, 'temperature':0,
        'max_tokens':80, 'stream':False,
    }).encode()
    request=Request(BASE+'/v1/chat/completions',data=payload,
                    headers={'Content-Type':'application/json'},method='POST')
    with urlopen(request,timeout=18) as response:
        answer=json.loads(response.read(16_000).decode('utf-8'))
    return answer['choices'][0]['message']['content']


def main() -> int:
    examples=[
        {'case_id':'identity_unknown','classification':'synthetic_non_sensitive',
         'scenario':'A reply arrived with no stable thread ID and no canonical contact identity. Should it be admitted to the buyer-conversation evidence ledger?',
         'expected_decision':'block'},
        {'case_id':'payment_not_verified','classification':'synthetic_non_sensitive',
         'scenario':'A merchant created a BSC USDT payment request but there is no verified transaction, delivery or recognized accounting event. Is realized revenue verified?',
         'expected_decision':'block'},
    ]
    try:
        result=run_synthetic_ab('empire-evidence-verification',examples,inference=local_completion)
    except Exception as exc:
        print(json.dumps({'status':'UNAVAILABLE','reason':type(exc).__name__,
                          'authority':'none','approved':False}))
        return 2
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
