#!/usr/bin/env python3
"""Source-labelled, *unseen* real-world title probe on four Empire page titles.

This probe was assembled after the initial 20-query developer-authored run.
It uses exact public document titles from government, industry and Microsoft
documentation, with source URLs. It is not a randomly sampled buyer-query
benchmark, does not prove buyer intent or ranking, and its topical labels
remain human editorial judgements. DO NOT train/tune model against these rows.
"""
from __future__ import annotations

import argparse
import json
from typing import Any

from empire_os.search_intelligence.local_embedding_runtime import (
    IsolatedFastEmbedProcess, LocalSemanticEmbedder,
)
from scripts.benchmark_local_semantic import (
    collect_known_page_keywords, run_semantic_benchmark,
)


# Titles come from third-party public documents, NOT from Empire's marketing
# page titles or the 20 initial developer-authored training/evaluation prompts.
SOURCE_TITLES: tuple[tuple[str, str, str], ...] = (
    ("Elements of Roofing: A Guide for Building Owners", "roofing",
     "https://industry.nrca.net/nfnrcatest/eweb/DynamicPage.aspx?es3_key=B4C74537-3ED3-4BC6-B2F7-BAF9B2BD7A67&prd_key=32F06348-D721-4C37-8355-CDB739388356&site=nrca&webcode=NRCAStorePrdDetails"),
    ("Roofing 101 Module 1: The Basics", "roofing",
     "https://industry.nrca.net/nfnrcatest/eweb/DynamicPage.aspx?es3_key=529247d0-ac2e-45f1-b0c2-463a91d4aaeb&prd_key=81ABF843-EA0F-4653-AF0E-4C3F08142D70&site=nrca&webcode=NRCAStorePrdDetails"),
    ("High Performance Roof Systems: A Standard of Care for Designers and Contractors", "roofing",
     "https://www.nrca.net/roofingguidelines/Library/Detail?id=ab3csGQLmt0%3D"),
    ("Solar Photovoltaic Technology Basics", "solar",
     "https://www.energy.gov/cmei/systems/solar-photovoltaic-technology-basics"),
    ("Solar Photovoltaic System Design Basics", "solar",
     "https://www.energy.gov/cmei/systems/solar-photovoltaic-system-design-basics"),
    ("Homeowner's Guide to Solar", "solar",
     "https://www.energy.gov/cmei/systems/homeowners-guide-solar"),
    ("Heat Pump Systems", "hvac",
     "https://www.energy.gov/energysaver/heat-pump-systems"),
    ("Heating & Cooling", "hvac",
     "https://www.energy.gov/topics/heating-cooling"),
    ("Geothermal Heating & Cooling", "hvac",
     "https://www.energy.gov/hgeo/geothermal/geothermal-heating-cooling"),
    ("Forecast revenue accurately with Dynamics 365 Sales", "predictive-revenue-os",
     "https://learn.microsoft.com/en-us/dynamics365/sales/project-accurate-revenue-sales-forecasting"),
    ("View your forecast: Check pipeline health and track quota progress", "predictive-revenue-os",
     "https://learn.microsoft.com/en-us/dynamics365/sales/view-forecasts"),
    ("Configure forecasts in your organization", "predictive-revenue-os",
     "https://learn.microsoft.com/en-us/dynamics365/sales/configure-forecast"),
)


def run_source_title_review(corpus: list[dict[str, Any]], embedder: LocalSemanticEmbedder) -> dict[str, Any]:
    scored = run_semantic_benchmark(
        corpus, embedder,
        cases=tuple((title, sector) for title, sector, _ in SOURCE_TITLES),
        negative_cases=(),  # Do not report absent negatives as tested.
    )
    for record, source in zip(scored["sample_cases"], SOURCE_TITLES):
        assert record["query"] == source[0]
        record["source_url"] = source[2]
        record["source_type"] = "external_public_document_title"
    scored["schema_version"] = "empire.semantic_external_source_titles.v1"
    scored["source_document_title_count"] = len(SOURCE_TITLES)
    scored["source_titles_collected_after_initial_20_query_dev_run"] = True
    scored["source_titles_are_buyer_queries"] = False
    scored["independently_human_annotated"] = False
    scored["random_sample"] = False
    scored["result_implies_search_visibility"] = False
    scored["automatic_decision_authorized"] = False
    return scored


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-embed-cache", required=True)
    parser.add_argument("--local-embed-python", required=True)
    args = parser.parse_args()
    try:
        model = LocalSemanticEmbedder(
            model_cache=args.local_embed_cache,
            model_loader=lambda cache: IsolatedFastEmbedProcess(
                model_cache=cache, python_executable=args.local_embed_python,
            ),
        )
        result = run_source_title_review(collect_known_page_keywords(), model)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({
            "status": "UNAVAILABLE",
            "reason": type(exc).__name__,
        }), file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
