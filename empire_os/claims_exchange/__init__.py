"""Research-only contractor/carrier opportunity exchange.

No database, network, outbound, licensing or claims-adjusting execution.
"""
from .engine import assess_candidate, assess_offer, match_capacity, build_review_packets

__all__ = ["assess_candidate", "assess_offer", "match_capacity", "build_review_packets"]
