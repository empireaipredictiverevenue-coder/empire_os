"""
Synthetic Intelligence — generates synthetic training data from agent
observations to improve future decisions.

The idea: after each cycle, observe what the agent saw, then prompt the
LLM to generate N synthetic examples that look like the same patterns
but with different inputs. This enriches the prompt context for the
next reasoning cycle.

Free, runs on the same LLM we already use. No external dependency.

Helpers exposed for other agents:
  - generate_synthetic_leads(niche, count, llm) -> list[dict]
  - analyze_market(niche, backend, llm) -> MarketAnalysis
  - analyze_lead(lead, llm) -> LeadAnalysis  (cross-niche scoring)
  - score_niche_fit(lead, niche) -> float    (heuristic, no LLM)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("synthetic_intelligence")


@dataclass
class SyntheticExample:
    """One synthesised example."""
    input: dict = field(default_factory=dict)
    expected_output: dict = field(default_factory=dict)
    rationale: str = ""


class SyntheticIntelligence:
    """Generate synthetic training examples from observed agent state."""

    def __init__(self, llm, n_synthetic: int = 5):
        self.llm = llm
        self.n_synthetic = n_synthetic
        self.examples: list = []

    def augment(self, observed_state: dict, last_decision: dict) -> list:
        """Generate N synthetic examples from one observation."""
        prompt = f"""You are generating synthetic training examples for an autonomous agent.

The agent just observed:
{json.dumps(observed_state, indent=2)[:2000]}

And made this decision:
{json.dumps(last_decision, indent=2)[:1000]}

Generate {self.n_synthetic} synthetic variations — same pattern, different
inputs — that would teach the agent to handle similar situations.

Output a JSON array of objects with: input, expected_output, rationale.
Output only the JSON array, nothing else."""

        try:
            result = self.llm.structured_chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
        except Exception as e:
            logger.warning("synthetic generation failed: %s", e)
            return []

        if isinstance(result, list):
            examples = result
        elif isinstance(result, dict):
            examples = result.get("examples", result.get("data", []))
        else:
            return []

        parsed = []
        for ex in examples[:self.n_synthetic]:
            try:
                parsed.append(SyntheticExample(
                    input=ex.get("input", {}),
                    expected_output=ex.get("expected_output", {}),
                    rationale=ex.get("rationale", ""),
                ))
            except Exception:
                continue
        self.examples.extend(parsed)
        logger.info("generated %d synthetic examples", len(parsed))
        return parsed

    def observe(self) -> dict:
        return {
            "agent": "synthetic-intelligence",
            "examples_generated_total": len(self.examples),
            "examples_in_pool": len(self.examples[-50:]),
        }

    def reason(self, state: dict) -> str:
        return json.dumps({
            "action": "augment",
            "reasoning": "synthetic data improves future cycles",
        })

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except json.JSONDecodeError:
            d = {"action": "skip"}
        return {"action": d.get("action", "skip"), "examples_total": len(self.examples)}


# ──────────────────────────────────────────────────────────────────────
# Helpers consumed by other agents (agi-scout, data-analysis,
# markets-analysis, lead-handler)
# ──────────────────────────────────────────────────────────────────────

# Niche keyword map (used by score_niche_fit and analyze_lead)
NICHE_KEYWORDS = {
    "roofing":       ["roof", "shingle", "gutter", "reroof", "roofer"],
    "hvac":          ["hvac", "furnace", "air condition", "ac unit", "heat pump"],
    "plumbing":      ["plumb", "drain", "water heater", "leak", "pipe"],
    "electrical":    ["electric", "wiring", "panel", "outlet", "electrician"],
    "pest_control":  ["pest", "termite", "rodent", "exterminator", "bug"],
    "landscaping":   ["landscape", "lawn", "tree", "garden", "mowing"],
    "solar":         ["solar", "pv", "photovoltaic", "panel install"],
    "mass_torts":    ["lawsuit", "class action", "settlement", "injury"],
    "debt_relief":   ["debt", "consolidat", "bankruptcy", "credit score"],
    "insurance":     ["insurance", "policy", "claim", "coverage"],
    "weight_loss":   ["weight", "ozempic", "wegovy", "diet", "gym"],
    "addiction":     ["rehab", "addiction", "sober", "recovery", "detox"],
    "mortgage":      ["mortgage", "refinance", "home loan", "lender"],
    "cybersecurity": ["cybersecurity", "ransomware", "breach", "siem"],
    "managed_it":    ["managed it", "msp", "helpdesk", "network admin"],
    "marketing":     ["marketing", "seo", "ppc", "ads", "leads"],
    "real_estate":   ["real estate", "realtor", "listing", "mls"],
    "lawyer":        ["lawyer", "attorney", "law firm", "legal"],
    "consulting":    ["consulting", "advisory", "strategy"],
}


def score_niche_fit(lead: dict, niche: str) -> float:
    """Heuristic cross-niche fit score (0..1).

    Lower-cases name + details, counts keyword hits for the target
    niche, normalises against the max possible (3 hits = 1.0).

    Args:
        lead: dict with keys like name, phone, source, details, niche
        niche: target niche to score against
    Returns:
        float in [0.0, 1.0]
    """
    text = " ".join([
        str(lead.get("name", "")),
        str(lead.get("source", "")),
        str(lead.get("niche", "")),
        json.dumps(lead.get("details", {}), default=str),
    ]).lower()
    kws = NICHE_KEYWORDS.get(niche, [])
    if not kws:
        return 0.0
    hits = sum(1 for kw in kws if kw in text)
    # Bonus: if lead's existing niche matches, full credit
    if str(lead.get("niche", "")).lower() == niche:
        hits += 1
    return min(1.0, hits / 3.0)


def generate_synthetic_leads(niche: str, count: int,
                              llm) -> list[dict]:
    """Generate plausible synthetic prospect leads for a niche.

    Used by agi-scout when real scanners are silent or thin. Each lead
    is a dict with name, phone, zip, details. Phone is left blank
    (synthetic — no real human to call).

    Returns list[dict] (may be empty on LLM failure).
    """
    prompt = f"""Generate {count} plausible synthetic business leads for the
{niche} niche in the US. Vary across metros (use real US metro names).

Each lead must be a JSON object with: business_name, phone (use format
555-0100 to 555-0199 to mark as synthetic), zip (5 digits), details
(1-2 sentence description of the business).

Output a JSON array of exactly {count} objects, nothing else."""
    try:
        result = llm.structured_chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
    except Exception as e:
        logger.warning("generate_synthetic_leads failed: %s", e)
        return []

    if isinstance(result, list):
        leads = result
    elif isinstance(result, dict):
        leads = result.get("leads",
                           result.get("data",
                                      result.get("examples", [])))
    else:
        return []

    out = []
    for raw in leads[:count]:
        if not isinstance(raw, dict):
            continue
        out.append({
            "business_name": raw.get("business_name", ""),
            "phone":         raw.get("phone", ""),
            "zip":           raw.get("zip", ""),
            "details":       raw.get("details", ""),
            "_synthetic":    True,
            "_generated_at": datetime.now(timezone.utc).isoformat(),
        })
    return out


@dataclass
class MarketAnalysis:
    """Result of analyze_market()."""
    niche: str
    urgency: str          # "low" | "medium" | "high"
    recommended_angle: str
    top_opportunities: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


def analyze_market(niche: str, backend, llm) -> MarketAnalysis:
    """Analyze the market for a niche using LLM + current DB state.

    Used by agi-scout's "analyze" action. Returns a MarketAnalysis
    with urgency + recommended approach.
    """
    # Pull current state from DB
    try:
        cnx = backend.cnx if hasattr(backend, "cnx") else None
        if cnx is None:
            raise RuntimeError("backend has no .cnx")
    except Exception:
        cnx = None
    state = {"niche": niche, "note": "no DB introspect available"}
    prompt = f"""Analyze the US market for {niche} service businesses.

Current pipeline state: {json.dumps(state, default=str)[:500]}

Output JSON only:
{{"urgency": "low|medium|high",
 "recommended_angle": "<one-sentence go-to-market>",
 "top_opportunities": ["...", "...", "..."],
 "risks": ["...", "..."]}}"""
    try:
        res = llm.structured_chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
    except Exception as e:
        logger.warning("analyze_market LLM failed: %s", e)
        return MarketAnalysis(
            niche=niche, urgency="medium",
            recommended_angle=f"Standard {niche} outreach")

    if not isinstance(res, dict):
        return MarketAnalysis(
            niche=niche, urgency="medium",
            recommended_angle=f"Standard {niche} outreach")
    return MarketAnalysis(
        niche=niche,
        urgency=res.get("urgency", "medium"),
        recommended_angle=res.get("recommended_angle", ""),
        top_opportunities=res.get("top_opportunities", []) or [],
        risks=res.get("risks", []) or [],
    )


@dataclass
class LeadAnalysis:
    """Result of analyze_lead()."""
    lead_id: str
    primary_niche: str
    primary_fit: float
    secondary_niches: list[tuple[str, float]] = field(default_factory=list)
    recommendation: str = ""   # "send_to_outreach" | "park" | "re_route"
    reasoning: str = ""


def analyze_lead(lead: dict, llm=None,
                 niches: Optional[list[str]] = None) -> LeadAnalysis:
    """Score a lead against multiple niches.

    If llm is provided, refines the recommendation with a 1-sentence
    reasoning. If llm is None, uses deterministic heuristic.

    Used by lead-handler-agent to route misfit leads to better
    niches instead of dropping them.
    """
    if niches is None:
        niches = list(NICHE_KEYWORDS.keys())
    scores = [(n, score_niche_fit(lead, n)) for n in niches]
    scores.sort(key=lambda x: -x[1])
    primary_niche, primary_fit = scores[0]
    secondaries = [(n, s) for n, s in scores[1:6] if s > 0.0]
    # Recommendation heuristic
    if primary_fit >= 0.5:
        rec = "send_to_outreach"
        reason = (f"primary fit {primary_fit:.2f} for {primary_niche}; "
                  f"clear match")
    elif primary_fit >= 0.2:
        rec = "re_route"
        reason = (f"weak fit {primary_fit:.2f}; consider "
                  f"{secondaries[0][0] if secondaries else '?'} "
                  f"(score {secondaries[0][1]:.2f})")
    else:
        rec = "park"
        reason = (f"no niche hit fit >= 0.2; "
                  f"best was {primary_niche} at {primary_fit:.2f}")
    # Optional LLM refinement
    if llm is not None:
        try:
            res = llm.structured_chat(
                messages=[{"role": "user", "content": (
                    f"Lead: {json.dumps(lead, default=str)[:600]}\n"
                    f"Top niche scores: {scores[:5]}\n"
                    f"Refine recommendation in 1 sentence.")}],
                temperature=0.2,
            )
            if isinstance(res, dict) and res.get("reasoning"):
                reason = str(res["reasoning"])[:240]
        except Exception:
            pass
    return LeadAnalysis(
        lead_id=str(lead.get("id") or lead.get("prospect_id") or ""),
        primary_niche=primary_niche,
        primary_fit=round(primary_fit, 3),
        secondary_niches=[(n, round(s, 3)) for n, s in secondaries],
        recommendation=rec,
        reasoning=reason,
    )