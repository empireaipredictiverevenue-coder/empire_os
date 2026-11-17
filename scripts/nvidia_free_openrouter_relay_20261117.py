"""Fail-closed, synthetic-only OpenRouter free NVIDIA inference for existing gateway.

No new daemon. Called ONLY by EmpireOS's existing NVIDIA private Docker
model gateway. Keeps the existing OpenRouter key on host; never in Compose.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REMOTE_MODEL="nvidia/nemotron-3.5-super-vl:free"
GATEWAY_ALIAS="openai/"+REMOTE_MODEL
SECRET=Path("/etc/empire_os/llm_secrets/openrouter.env")
CATALOG="https://openrouter.ai/api/v1/models"
INFERENCE="https://openrouter.ai/api/v1/chat/completions"
MAX_RESPONSE=8_388_608

class HostedUnavailable(RuntimeError):
    """No free authorized route available; fail closed."""


def available():
    return os.environ.get("EMPIRE_NVIDIA_EVAL_FREE_HOSTED_ENABLED")=="1"


def existing_key():
    meta=SECRET.stat()
    if stat.S_IMODE(meta.st_mode)!=0o600 or meta.st_uid!=os.getuid():
        raise HostedUnavailable("private key file ownership or mode mismatch")
    key=""
    for line in SECRET.read_text().splitlines():
        line=line.strip().removeprefix("export ")
        if line.startswith("OPENROUTER_API_KEY="):
            if key:
                raise HostedUnavailable("ambiguous credential")
            key=line.partition("=")[2].strip().strip('"').strip("'")
    if not key:
        raise HostedUnavailable("existing OpenRouter key unavailable")
    return key


def check_free_model():
    with urlopen(Request(CATALOG,headers={"Accept":"application/json"}),timeout=9) as response:
        info=json.load(response)
    matching=[x for x in info.get("data",[]) if x.get("id")==REMOTE_MODEL]
    if len(matching)!=1:
        raise HostedUnavailable("no uniquely matched free NVIDIA model")
    model=matching[0]
    price=model.get("pricing") or {}
    if price.get("prompt")!="0" or price.get("completion")!="0":
        raise HostedUnavailable("free price not confirmed")
    features=set(model.get("supported_parameters") or [])
    if not {"response_format","structured_outputs","tools"}.issubset(features):
        raise HostedUnavailable("NVIDIA model capabilities changed")


def send(payload):
    if not available():
        raise HostedUnavailable("hosted inference not enabled")
    if not isinstance(payload,dict) or payload.get("model")!=GATEWAY_ALIAS:
        raise HostedUnavailable("unapproved model")
    if payload.get("stream",False):
        raise HostedUnavailable("streaming unsupported by gated relay")
    tokens=payload.get("max_tokens",8192)
    if not isinstance(tokens,int) or isinstance(tokens,bool) or tokens<1 or tokens>8192:
        raise HostedUnavailable("response token cap invalid")
    if not isinstance(payload.get("messages"),list) or len(payload["messages"])>60:
        raise HostedUnavailable("invalid conversation")
    check_free_model() # Revalidate exact zero-price status before EVERY call.
    key=existing_key()
    request=dict(payload)
    request["model"]=REMOTE_MODEL
    request["provider"]={"allow_fallbacks":False}
    request["stream"]=False
    body=json.dumps(request).encode()
    if len(body)>1_048_576:
        raise HostedUnavailable("prompt too large")
    headers={
        "Authorization":"Bearer "+key,
        "Content-Type":"application/json",
        "Accept":"application/json",
        "X-Title":"EmpireOS isolated NVIDIA ontology synthetic evaluation",
    }
    req=Request(INFERENCE,data=body,method="POST",headers=headers)
    with urlopen(req,timeout=175) as response:
        data=response.read(MAX_RESPONSE+1)
        if len(data)>MAX_RESPONSE:
            raise HostedUnavailable("response too large")
    result=json.loads(data)
    if result.get("model")!=REMOTE_MODEL or not isinstance(result.get("choices"),list):
        raise HostedUnavailable("unexpected remote model or response")
    return json.dumps(result,separators=(",",":")).encode()
