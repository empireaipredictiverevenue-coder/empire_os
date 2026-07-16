"""
AGI Marketing — autonomous content strategy & AEO generation agent.

Replaces the script-driven marketing pipeline with an agent that:
1. OBSERVE — analyze funnel data, existing AEO pages, coverage gaps
2. REASON — LLM decides which niche needs content, what angle to take
3. ACT — generates full publication-ready AEO content and deploys it
4. FEEDBACK — tracks page quality, identifies gaps for next cycle
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from empire_os.agent_core import Agent, OllamaClient
from empire_os.funnel import SQLiteBackend, FunnelState, list_states
from empire_os.synthetic_intelligence import (
    generate_aeo_content,
    analyze_market,
    MarketAnalysis,
)
from empire_os.aeo_surface import deploy_spec, list_pages, remove_page
from empire_os.marketing import AeoSpecDraft

logger = logging.getLogger("agi_marketing")

MARKETING_SYSTEM_PROMPT = """You are the AGI Marketing Strategist for Empire OS v3.

Your role:
1. Analyze market data and existing content to find coverage gaps
2. Decide which niche needs a new AEO page this cycle
3. Determine the best content angle based on market analysis

You are a senior content strategist. Think about audience, SEO,
and authority building. Output decisions as JSON."""


class AgiMarketingAgent(Agent):
    """AGI-powered Marketing that generates real content via LLM."""

    def __init__(
        self,
        backend: SQLiteBackend,
        llm: Optional[OllamaClient] = None,
        surface_root: str = "/srv/aeo",
        niches: Optional[list[str]] = None,
    ):
        super().__init__(
            name="agi-marketing",
            llm=llm,
            backend=backend,
        )
        self.surface_root = Path(surface_root)
        self.niches = niches or [
            "roofing", "hvac", "plumbing", "electrical",
            "mass_torts", "pest_control", "solar", "landscaping",
        ]

    def observe(self) -> dict:
        """Gather content coverage and funnel state."""
        # What pages already exist on the AEO surface
        existing_pages = list_pages(self.surface_root)

        # Which niches have leads in the funnel
        discovered = list_states(self.backend, state=FunnelState.DISCOVERED.value)
        niche_counts = {}
        for p in discovered:
            if p.notes:
                for n in self.niches:
                    if n in p.notes:
                        niche_counts[n] = niche_counts.get(n, 0) + 1

        # Niches without pages
        existing_niches = {p["niche"] for p in existing_pages}
        missing_pages = [n for n in self.niches if n not in existing_niches]

        return {
            "existing_pages": len(existing_pages),
            "existing_niches": list(existing_niches),
            "missing_pages": missing_pages,
            "niche_lead_counts": niche_counts,
            "total_leads_funnel": sum(niche_counts.values()),
            "cycle": self.context.cycle,
        }

    def reason(self, state: dict) -> str:
        """LLM decides which niche needs content and what angle."""
        prompt = f"""Content coverage analysis:
- Existing AEO pages: {state['existing_pages']} ({', '.join(state['existing_niches'])})
- Niches without pages: {state['missing_pages']}
- Lead distribution: {json.dumps(state['niche_lead_counts'])}
- Cycle: {state['cycle']}

Decide what action to take:
1. "generate" — create a new AEO page for a niche that needs one
2. "improve" — regenerate content for an existing page that could be better
3. "analyze" — run deep market analysis before deciding
4. "skip" — all niches have good coverage

Output JSON: {{"action": "...", "niche": "...", "angle_hint": "...", "reasoning": "..."}}"""

        result = self.llm.structured_chat(
            messages=[{"role": "user", "content": prompt}],
            system=MARKETING_SYSTEM_PROMPT,
            temperature=0.3,
        )
        return json.dumps(result)

    def act(self, decision: str) -> dict:
        """Execute the content decision."""
        try:
            d = json.loads(decision)
        except json.JSONDecodeError:
            d = {"action": "skip", "reasoning": "Parse failed"}

        action = d.get("action", "skip")
        niche = d.get("niche", "")
        angle_hint = d.get("angle_hint", "")
        reasoning = d.get("reasoning", "")

        result = {"action": action, "niche": niche, "reasoning": reasoning}

        if action in ("generate", "improve") and niche:
            # First, run market analysis to inform content
            try:
                analysis = analyze_market(niche=niche, backend=self.backend, llm=self.llm)
                result["market_urgency"] = analysis.urgency
            except Exception:
                analysis = None

            # Generate real content via LLM
            try:
                content = generate_aeo_content(
                    niche=niche,
                    market_analysis=analysis,
                    llm=self.llm,
                )
                result["content_length"] = content.word_count
                result["content_title"] = content.title

                # Map LLM output to AeoSpecDraft fields
                draft = AeoSpecDraft(
                    niche=niche,
                    target_audience=getattr(content, "target_audience", ""),
                    pain_points=getattr(content, "pain_points", ""),
                    key_questions="",
                    content_angle=content.title or angle_hint or niche,
                    tone="professional — authoritative",
                    word_count_target=content.word_count or 1500,
                    competitors="",
                    internal_links="",
                    body_html=content.html or "",
                    meta_description=content.meta_description or "",
                    call_to_action=f"Get a free {niche} consultation today",
                )
                from empire_os.aeo_surface import deploy_spec as deploy
                deployed_path = deploy(draft, surface_root=str(self.surface_root))
                result["deployed_path"] = str(deployed_path)
                # Read rendered HTML for hub sync
                try:
                    result["html_content"] = Path(deployed_path).read_text(encoding="utf-8")
                except Exception:
                    result["html_content"] = ""
                result["summary"] = (
                    f"Deployed '{content.title}' ({content.word_count} words) "
                    f"to {deployed_path}"
                )
            except Exception as e:
                logger.exception("Content generation failed for %s", niche)
                result["error"] = str(e)
                result["summary"] = f"Content generation failed: {e}"

        elif action == "analyze" and niche:
            try:
                analysis = analyze_market(niche=niche, backend=self.backend, llm=self.llm)
                result.update({
                    "urgency": analysis.urgency,
                    "angle": analysis.recommended_angle,
                    "opportunities": analysis.top_opportunities,
                })
                result["summary"] = f"Analyzed {niche}: urgency={analysis.urgency}"
            except Exception as e:
                result["error"] = str(e)
                result["summary"] = f"Analysis failed: {e}"

        else:
            result["summary"] = f"Skipped — {reasoning[:100]}"

        return result
