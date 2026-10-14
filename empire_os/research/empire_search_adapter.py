"""Thin, default-read-only bridge to EmpireOS-owned research infrastructure."""
from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from .deep_research_intake import ResearchLimits, run_research


def research_with_empire_search(
    question: str,
    *,
    limits: ResearchLimits = ResearchLimits(),
    search_fn: Callable[..., Mapping[str, Any]] | None = None,
    inspect_fn: Callable[[str], Mapping[str, Any]] | None = None,
    follow_up_fn: Callable[[str, list[dict[str, Any]], list[str]], Sequence[str]] | None = None,
    synthesize_fn: Callable[[str, list[dict[str, Any]]], Mapping[str, Any]] | None = None,
    operator_primary_urls: Sequence[str] = (),
    skip_discovery: bool = False,
) -> dict[str, Any]:
    """Use existing Empire search and official-source inspector, not new services.

    Runs only when explicitly invoked; neither search nor research executes at
    import. Current inspector only checks allowlisted official-document sites.
    Provider/cache implementation may update local operational health files;
    this bridge does not authorize SQL writes or commercial actions.
    """
    if search_fn is None:
        from empire_os.search_fabric.reliable_search import search_reliable
        search_fn = search_reliable
    if inspect_fn is None:
        from empire_os.system_improvement_research import inspect_primary_page
        inspect_fn = inspect_primary_page
    result = run_research(
        question,
        search_fn=search_fn,
        inspect_fn=inspect_fn,
        limits=limits,
        follow_up_fn=follow_up_fn,
        synthesize_fn=synthesize_fn,
        operator_primary_urls=operator_primary_urls,
        skip_discovery=skip_discovery,
    )
    result["provider_binding"] = "empire.search_fabric.reliable_search"
    result["inspector_binding"] = "empire.system_improvement_research.official_source"
    return result
