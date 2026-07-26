"""Cortex Intelligence System - Strategic Decision Engine

The Cortex processes real-time market data, predicts revenue,
monitors lead conversion, and delivers strategic recommendations
to Empire OS agents. Integrated with predictive analytics
and business intelligence for optimal revenue generation.
"""

from .cortex_ai_assistant import (
    ask_brain,
    get_snapshot,
    _rule_based_advice,
    ask_brain_legacy,
    get_brain_status,
)

from .cortex_brain_loop import run_cortex_brain_loop
from .cortex_scorer import (
    get_niche_score,
    re_score_existing,
)

from ..predictive import (
    predict_revenue,
    detect_market_gaps,
    detect_leaks,
    detect_waste,
)

__version__ = "1.0.0"
__all__ = [
    "ask_brain",
    "get_snapshot",
    "_rule_based_advice",
    "ask_brain_legacy",
    "get_brain_status",
    "run_cortex_brain_loop",
    "get_niche_score",
    "re_score_existing",
    "predict_revenue",
    "detect_market_gaps",
    "detect_leaks",
    "detect_waste",
]
