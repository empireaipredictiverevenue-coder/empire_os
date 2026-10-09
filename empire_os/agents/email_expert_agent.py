"""
Empire OS v3 - Email Expert Agent
==================================

Legacy email composition helper. Compliance and outbound permission are
independent operational gates, not guaranteed by generated copy.

Consults:
  - skills-library at /tmp/repo_skills/skills/:
    claude-api / brand-guidelines / internal-comms / doc-coauthoring
  - /root/empire_os/empire_os/agents/souls/legal_compliance_SOUL.md
    for the live compliance gate.

Pipeline:
  1. inbound brief (audience, niche, metro, tier, intent)
  2. compose via Ollama(qwen2.5:7b) using the skills' brand voice
  3. compliance pre-check via /v1/compliance/check (or fallback)
  4. emit a "safe" or "blocked" result with audit trail
  5. never send without a verifyable unsubscribe - injected in
     every message

Run:  python3 /root/empire_os/empire_os/agents/email_expert_agent.py
"""
from __future__ import annotations
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
import requests
from empire_os.skills_library import load_skills_for_role, available_skills

HUB      = os.environ.get("HUB_URL", "http://127.0.0.1:8000")
OLLAMA   = os.environ.get("OLLAMA_URL", "http://10.218.156.211:11434")
LLM_MODEL= os.environ.get("LLM_MODEL", "qwen2.5:7b")
FB       = Path("/root/feedback")
LOG      = FB / "email_expert.jsonl"
SOUL_DIR  = Path(__file__).resolve().parent / "souls"
INTERVAL = int(os.environ.get("INTERVAL_SEC", "30"))


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(),
         "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "EVENT"):
        print(json.dumps(e), flush=True)


def load_skill_text(name: str) -> str:
    """Only digest-approved Empire commercial-copy guidance can enter prompts."""
    if name != 'empire-commercial-email-copy':
        return ''
    return next((row['body'] for row in load_skills_for_role('email')
                 if row['name'] == name), '')


UNSUBSCRIBE_MARKER = "\n\n---\nYou received this because of your prior inquiry. Unsubscribe: https://empire-ai.co.uk/unsub/{tenant_id}\n"

PROMPT_template = (
    "You are an expert outbound copywriter.\n"
    "Skill context (read for tone):\n"
    "{skill_excerpt}\n"
    "Compliance context (CRITICAL):\n"
    "{compliance_excerpt}\n"
    "Brief:\n"
    "{brief}\n"
    "Return ONLY a JSON object with keys subject, body. No commentary. "
    "The body MUST end with an unsubscribe link and a contact line."
)


def compose(brief: dict) -> dict:
    skill_text = load_skill_text('empire-commercial-email-copy')
    compliance_text = ""
    p = SOUL_DIR / "legal_compliance_SOUL.md"
    if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(SOUL_DIR.resolve()) and p.stat().st_size <= 24000:
        compliance_text = p.read_text(encoding='utf-8')[:1200]
    prompt = PROMPT_template.format(
        skill_excerpt=skill_text,
        compliance_excerpt=compliance_text,
        brief=json.dumps(brief))
    try:
        r = requests.post(f"{OLLAMA}/api/generate",
                          json={"model": LLM_MODEL, "prompt": prompt,
                                "stream": False}, timeout=180)
        raw = r.json().get("response", "")
    except Exception as e:
        log("ERROR", "ollama_fail", err=str(e)[:150])
        raw = ""
    # parse JSON out of model output if possible
    subject, body = "(no subject)", "(model unavailable)"
    try:
        if "{" in raw:
            j = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
            subject = j.get("subject", subject)
            body    = j.get("body", body)
        else:
            body = raw.strip()[:4000]
    except Exception:
        pass
    return {"subject": subject, "body": body + UNSUBSCRIBE_MARKER}


def compliance_check(brief: dict, body: str) -> dict:
    try:
        r = requests.post(f"{HUB}/v1/compliance/check",
                          json={"to_email": brief.get("email", ""),
                                "phone":    brief.get("phone", ""),
                                "state":    brief.get("state", ""),
                                "intent":   "marketing"},
                          timeout=8).json()
    except Exception:
        r = {"ok": False, "issues": ["compliance_remote_unavailable"]}
    body_lc = body.lower()
    if "unsubscribe" not in body_lc:
        r.setdefault("issues", []).append("missing_unsubscribe_link")
        r["ok"] = False
    if "empire-ai.co.uk" not in body_lc and "empireos" not in body_lc and "empire ai" not in body_lc:
        r.setdefault("issues", []).append("missing_business_id")
        # not a blocker - flag only
    return r


def cycle():
    # Heartbeat - the hub calls this agent via /v1/email/compose. We
    # don't generate proactively; we just confirm readiness + skills
    # available.
    ready_skills = available_skills()
    log("INFO", "agent_ready",
        skills=ready_skills,
        legal_compliance_loaded=(SOUL_DIR / "legal_compliance_SOUL.md").exists(),
        ollama=OLLAMA[:30])


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] email-expert online - {INTERVAL}s",
          flush=True)
    while True:
        try:
            cycle()
        except Exception as e:
            log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)
