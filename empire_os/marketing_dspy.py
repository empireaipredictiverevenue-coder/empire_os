"""
Opt-in DSPy path for Marketing persona spec drafting.

The marketing persona tries this module first when drafting AEO specs.
If dspy-ai is not installed or not configured, it falls back to the
free-form template path.

To activate:
    pip install dspy-ai>=2.5,<4
    from empire_os.marketing_dspy import configure_lm
    configure_lm(model="gpt-4o", api_base="...")
"""

from __future__ import annotations

import logging

logger = logging.getLogger("marketing_dspy")

_configured = False


def is_configured() -> bool:
    return _configured


def configure_lm(model: str = "gpt-4o", api_base: str = "") -> None:
    """Configure the DSPy language model.

    Call this once at startup to opt into DSPy-powered drafting.
    """
    global _configured
    try:
        import dspy
        lm = dspy.LM(model=model, api_base=api_base)
        dspy.settings.configure(lm=lm)
        _configured = True
        logger.info("DSPy configured with model=%s", model)
    except ImportError:
        logger.warning("dspy-ai not installed — install with: pip install dspy-ai>=2.5,<4")
    except Exception as e:
        logger.warning("Failed to configure DSPy: %s", e)


def draft_with_dspy(backend, niche: str) -> "AeoSpecDraft":
    """Draft an AEO spec using DSPy.

    Falls back to the free-form draft on any error.
    """
    from empire_os.marketing import AeoSpecDraft

    try:
        import dspy

        class AeoSpecSignature(dspy.Signature):
            """Draft a complete AEO content spec for a niche market."""

            niche = dspy.InputField(desc="The niche market, e.g. 'hvac'")
            target_audience = dspy.OutputField(
                desc="Description of the target audience for this niche"
            )
            pain_points = dspy.OutputField(
                desc="Top 3-5 pain points this niche has"
            )
            key_questions = dspy.OutputField(
                desc="What users search for in this niche"
            )
            content_angle = dspy.OutputField(
                desc="The unique content angle for this niche"
            )
            tone = dspy.OutputField(
                desc="Content tone: professional, authoritative, local-friendly"
            )
            word_count_target = dspy.OutputField(
                desc="Recommended word count as a number"
            )
            competitors = dspy.OutputField(
                desc="Competing pages targeting this niche"
            )

        predictor = dspy.Predict(AeoSpecSignature)
        result = predictor(niche=niche)

        return AeoSpecDraft(
            niche=niche,
            target_audience=result.target_audience,
            pain_points=result.pain_points,
            key_questions=result.key_questions,
            content_angle=result.content_angle,
            tone=result.tone,
            word_count_target=int(result.word_count_target)
            if result.word_count_target.isdigit()
            else 1500,
            competitors=result.competitors,
            internal_links="DRAFT — available from sitemap",
        )
    except Exception as e:
        logger.warning("DSPy draft failed, falling back to free-form: %s", e)
        from empire_os.marketing import _draft_freeform
        return _draft_freeform(niche)
