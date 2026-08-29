"""Empire Lead Generation System — backend orchestration glue.

Ties existing Empire modules into the 4-phase Lead Gen pipeline:
  P1 multi-niche satellite/market sweep  -> empire_os.sweep_ingest
  P2 audit generation (+ private portal) -> empire_os.audit_generator
  P3 lead capture (hub endpoints)        -> empire_os.hub / lead DB
  P4 cold email campaign                 -> empire_os.mail_sender

No new business logic invented here — this is orchestration over
battle-tested modules. Each phase is idempotent and re-runnable.
"""
from empire_os.leadgen.pipeline import run_pipeline, sweep_phase, audit_phase, campaign_phase

__all__ = ["run_pipeline", "sweep_phase", "audit_phase", "campaign_phase"]
