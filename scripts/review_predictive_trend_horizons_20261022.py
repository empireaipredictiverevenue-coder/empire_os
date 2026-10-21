"""Read-only trend readiness + optional original market-series research review.

Existing Cloud runtime remains unchanged; synthetic series cannot be
auto-promoted into live predictions, scientific training or paid signals.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from typing import Any

from empire_os.predictive_trend_horizon_review import (
    SCHEMA, TrendHorizonHold, review_trend_horizons,
)

RUNTIME=Path("/srv/empire_os/runtime/predictive_cloud/future_trend_latest.json")
MAX_INPUT_BYTES=160_000


def _source(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=MAX_INPUT_BYTES:
        raise TrendHorizonHold("untrusted trend source file")
    try:
        raw=json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError,OSError,ValueError):
        raise TrendHorizonHold("original trend source JSON unavailable") from None
    if type(raw) is not dict:
        raise TrendHorizonHold("trend source object required")
    return raw


def review_existing_cloud_runtime(path: Path = RUNTIME) -> dict:
    try:
        raw=_source(path)
    except (TrendHorizonHold,OSError):
        return {
            "schema_version":SCHEMA,
            "mode":"OBSERVE",
            "status":"EXISTING_CLOUD_FUTURE_TREND_SOURCE_UNAVAILABLE",
            "algorithm_available":False,
            "historical_trend_analysis_executed":False,
            "prediction_ready":False,
            "reviewable_original_market_series_authenticated":False,
            "future_horizons_days":[7,30,90],
            "database_writes":False,
            "execution_authority":"none",
        }
    if (raw.get("mode") != "OBSERVE"
            or raw.get("schema_version")!="empire.future_trend_intelligence.runtime.v1"
            or type(raw.get("analysis_executed")) is not bool
            or type(raw.get("prediction_ready")) is not bool
            or type(raw.get("algorithm_available")) is not bool
            or raw.get("actual_revenue") is not False
            or raw.get("execution_authority")!="none"):
        return {
            "schema_version":SCHEMA,
            "mode":"OBSERVE",
            "status":"EXISTING_CLOUD_TREND_RUNTIME_SECURITY_HOLD",
            "historical_trend_analysis_executed":False,
            "prediction_ready":False,
            "database_writes":False,
            "execution_authority":"none",
        }
    # The runtime currently provides only a module availability stub: no
    # original independently authenticated or recorded source time series.
    return {
        "schema_version":SCHEMA,
        "mode":"OBSERVE",
        "status":"EXISTING_CLOUD_TREND_OBSERVER_READ_ONLY",
        "cloud_component_schema":raw["schema_version"],
        "algorithm_available":raw["algorithm_available"],
        "historical_trend_analysis_executed":raw["analysis_executed"],
        "source_materializer_prediction_ready_reported":raw["prediction_ready"],
        "source_admission_state":raw.get("source_admission_state"),
        "source_blocker_codes":(
            [x for x in raw.get("blockers",[]) if type(x) is str and len(x)<160]
            if type(raw.get("blockers")) is list else []
        ),
        "reviewable_original_market_series_authenticated":False,
        "trend_horizons_days":[7,30,90],
        "research_trends_consumer_activation":False,
        "future_projection_or_calibration_verified":False,
        "true_conversion_revenue_proven":False,
        "database_writes":False,
        "execution_authority":"none",
    }


def example_contract() -> dict:
    return {
        "schema_version":"empire.predictive_intelligence.trend_series_intake.v1",
        "status":"UNFILLED_REAL_SOURCE_REQUIRED",
        "as_of":"<original UTC decision timestamp>",
        "series_contract":{
            "series_id":"<original stable source-series identifier>",
            "source_kind":"search_interest_index",
            "unit":"index_0_100",
            "geography":"<fixed region>",
            "vertical":"<fixed niche>",
            "source_name":"<same source/sampling definition for every point>",
        },
        "observations":[],
        "source_usage_rights_independently_verified":False,
        "not_a_customer_forecast":True,
    }


def review_file(path: Path, *, now:datetime) -> dict:
    raw=_source(path)
    if set(raw)!={"schema_version","as_of","series_contract","observations"} or raw["schema_version"]!="empire.predictive_intelligence.trend_series_intake.v1":
        raise TrendHorizonHold("unexpected source envelope")
    params=raw["series_contract"]
    if type(params) is not dict or set(params)!={
        "series_id","source_kind","unit","geography","vertical","source_name",
    }:
        raise TrendHorizonHold("incompatible original trend metric contract")
    output=review_trend_horizons(
        raw["observations"],as_of=raw["as_of"],review_at=now.isoformat(),
        **params
    )
    return {**output,
            "research_input_file_is_a_proven_data_source":False,
            "local_source_review_mode":"OWNER_SUPPLIED_RESEARCH_ONLY"}


def main(argv=None, *, now:datetime|None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-only",required=True,action="store_true")
    action=parser.add_mutually_exclusive_group()
    action.add_argument("--runtime",action="store_true")
    action.add_argument("--template",action="store_true")
    action.add_argument("--series-file")
    args=parser.parse_args(argv)
    try:
        if args.template:
            report=example_contract()
        elif args.series_file:
            report=review_file(Path(args.series_file),now=now or datetime.now(timezone.utc))
        else:
            report=review_existing_cloud_runtime()
        code=0
    except (TrendHorizonHold,OSError,ValueError,TypeError,KeyError):
        report={
            "schema_version":SCHEMA,
            "status":"TREND_SOURCE_RESEARCH_HELD",
            "mode":"OBSERVE",
            "commercial_forecast_authorized":False,
            "actual_revenue":False,
            "database_writes":False,
            "execution_authority":"none",
        }
        code=2
    print(json.dumps(report,sort_keys=True,allow_nan=False))
    return code


if __name__=="__main__":
    raise SystemExit(main())
