"""
predictive_revenue.py — backward-compat wrapper for agent_harness.
Delegates to empire_os.predictive.predict_revenue.
"""

from empire_os.predictive import predict_revenue, detect_market_gaps, detect_leaks, detect_waste, generate_daily_report

def forecast(*args, **kwargs):
    """Alias for predict_revenue — used by agent_harness."""
    return predict_revenue(*args, **kwargs)

__all__ = ["predict_revenue", "detect_market_gaps", "detect_leaks", "detect_waste", "generate_daily_report", "forecast"]
