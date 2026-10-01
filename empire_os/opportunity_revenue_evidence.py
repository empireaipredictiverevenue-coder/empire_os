"""Strict transport of explicit canonical factor observations; never estimate."""
from collections import Counter
from datetime import datetime
import math
from typing import Any, Mapping

from empire_os.predictive_revenue_formula import CORE_FACTORS

FACTORS = (*CORE_FACTORS, "ltv_cents")


def _fresh(stamp: Any, now: datetime) -> bool:
    try:
        value = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        return value.tzinfo is not None and 0 <= (now - value).total_seconds() <= 86400
    except (AttributeError, TypeError, ValueError):
        return False


def bridge_factor_evidence(candidate, source_rows, *, source_timestamp, now):
    """Accept only one explicitly associated row; partial evidence stays partial.

    Callers supply rows from the candidate's fixed canonical source, never a
    buyer-capacity aggregate, Radar score or normalized planning proxy.
    """
    values, refs = {}, {}
    empty = {"predictive_revenue_inputs": values,
             "predictive_revenue_evidence_refs": refs}
    if not _fresh(source_timestamp, now):
        return empty
    key = candidate.get("opportunity_key")
    matches = [row for row in source_rows if isinstance(row, Mapping)
               and row.get("opportunity_key") == key and key]
    if len(matches) != 1:
        return empty
    observations = matches[0].get("predictive_revenue_observations")
    if not isinstance(observations, list):
        return empty
    counts = Counter(row.get("factor") for row in observations
                     if isinstance(row, Mapping) and isinstance(row.get("factor"), str))
    for row in observations:
        if not isinstance(row, Mapping):
            continue
        factor = row.get("factor")
        if not isinstance(factor, str) or factor not in FACTORS or counts[factor] != 1:
            continue
        value = row.get("value")
        links = row.get("evidence_refs")
        if (row.get("opportunity_key") != key
                or row.get("semantic_class") != "predictive_revenue_factor"
                or not _fresh(row.get("observed_at"), now)
                or type(value) not in (int, float)
                or not math.isfinite(value) or value < 0
                or (factor != "ltv_cents" and value > 1)
                or not isinstance(links, list) or not links
                or any(not isinstance(ref, str) or not ref.strip() for ref in links)):
            continue
        values[factor] = value
        refs[factor] = sorted({ref.strip() for ref in links})
    return empty
