"""Read-only implementation evidence audit for recovered commercial assets.

Registry state is planning metadata, not proof that a product is live. This
module inspects the current checkout for bounded implementation evidence and
keeps runtime/production proof explicitly unknown unless an expected runtime
artifact is actually observable.

It never reads protected recovery/toop trees and grants no execution, pricing,
commercial, accounting or revenue-recognition authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from empire_os.commercial_recovery_registry import recovery_product_catalog


PROTECTED_PREFIXES = ("recovery/", "toop/")


@dataclass(frozen=True)
class EvidenceSpec:
    code_patterns: tuple[str, ...] = ()
    test_patterns: tuple[str, ...] = ()
    service_patterns: tuple[str, ...] = ()
    runtime_paths: tuple[str, ...] = ()


EVIDENCE_SPECS: dict[str, EvidenceSpec] = {
    "permit_intelligence": EvidenceSpec(
        code_patterns=("empire_os/permit_intelligence_runtime.py",),
        test_patterns=("tests/test_permit_intelligence_runtime.py",),
    ),
    "property_intelligence": EvidenceSpec(
        code_patterns=("empire_os/vertical_intelligence_runtime.py",),
        test_patterns=("tests/test_vertical_intelligence_runtime.py",),
    ),
    "private_capital_rollup": EvidenceSpec(
        code_patterns=(
            "empire_os/private_capital_snapshot.py",
            "empire_os/vertical_intelligence_runtime.py",
        ),
        test_patterns=(
            "tests/test_private_capital_snapshot.py",
            "tests/test_vertical_intelligence_runtime.py",
        ),
    ),
    "oil_gas_intelligence": EvidenceSpec(
        code_patterns=("empire_os/intelligence/**/*energy*.py",),
    ),
    "storm_weather_intelligence": EvidenceSpec(
        code_patterns=(
            "empire_os/storm_predictor.py",
            "empire_os/storm_revenue_multiplier.py",
            "empire_os/storm_service.py",
        ),
        test_patterns=(
            "tests/test_storm_and_sniper.py",
            "tests/test_storm_revenue_multiplier.py",
            "tests/test_storm_satellite_reddit.py",
        ),
        service_patterns=(
            "empire-storm-strike.service",
            "empire-storm-strike.timer",
        ),
    ),
    "satellite_volumetric_intelligence": EvidenceSpec(
        code_patterns=(
            "empire_os/satellite_scanner.py",
            "empire_os/satellite_service.py",
            "empire_os/spatial_physical_*.py",
        ),
        test_patterns=(
            "tests/test_spatial_physical_*.py",
            "tests/test_storm_satellite_reddit.py",
        ),
    ),
    "warehouse_industrial_radar": EvidenceSpec(
        code_patterns=("industrial_sniper.py",),
    ),
    "market_revenue_gps": EvidenceSpec(
        code_patterns=("empire_os/market_sweep_revenue_gps.py",),
        test_patterns=("tests/test_market_sweep_revenue_gps.py",),
        service_patterns=(
            "empire-market-sweep-daily.service",
            "empire-market-sweep-daily.timer",
        ),
        runtime_paths=("runtime/market_sweeps/revenue_gps_latest.json",),
    ),
    "lane_seat_corridor_exchange": EvidenceSpec(
        code_patterns=(
            "empire_os/buyer_allocation.py",
            "empire_os/buyer_capacity_intake.py",
            "empire_os/buyer_capacity_readiness.py",
            "empire_os/revenue_exchange_allocation_*.py",
            "empire_os/lanes.py",
            "empire_os/seat_corridors.py",
        ),
        test_patterns=(
            "tests/test_buyer_allocation.py",
            "tests/test_buyer_capacity_*.py",
            "tests/test_revenue_exchange_allocation_*.py",
        ),
    ),
    "revenue_pulse": EvidenceSpec(
        code_patterns=(
            "empire_os/revenue_pulse.py",
            "empire_os/revenue_pulse_api.py",
            "empire_os/revenue_pulse_reader.py",
        ),
        test_patterns=("tests/test_revenue_pulse*.py",),
        runtime_paths=("runtime/revenue_pulse/latest.json",),
    ),
    "search_intelligence_suite": EvidenceSpec(
        code_patterns=(
            "empire_os/search_intelligence/**/*.py",
            "empire_os/search_fabric/**/*.py",
        ),
        test_patterns=(
            "tests/search_intelligence/**/*.py",
            "tests/test_search_*.py",
        ),
        service_patterns=("empire-seo-loop.service", "empire-seo-loop.timer"),
    ),
    "revenue_leak_audit": EvidenceSpec(
        code_patterns=(
            "empire_os/revenue_pulse.py",
            "empire_os/conversion_intelligence.py",
        ),
        test_patterns=(
            "tests/test_revenue_pulse.py",
            "tests/test_conversion_intelligence.py",
        ),
    ),
    "intel_hourly": EvidenceSpec(),
    "omega_evaluation": EvidenceSpec(
        code_patterns=(
            "empire_os/omega_os.py",
            "empire_os/omega_worker.py",
            "empire_os/cortex_learning_loop.py",
        ),
        test_patterns=(
            "tests/test_omega_*.py",
            "tests/test_cortex_learning_loop.py",
        ),
    ),
    "opportunity_marketplace": EvidenceSpec(
        code_patterns=(
            "empire_os/marketplace.py",
            "empire_os/waterfall.py",
            "empire_os/revenue_exchange.py",
        ),
        test_patterns=(
            "tests/test_waterfall.py",
            "tests/test_revenue_exchange.py",
        ),
    ),
    "managed_growth": EvidenceSpec(
        code_patterns=(
            "empire_os/gtm_*.py",
            "empire_os/marketing.py",
            "empire_os/search_intelligence/**/*.py",
        ),
        test_patterns=(
            "tests/test_gtm_*.py",
            "tests/test_marketing.py",
        ),
        service_patterns=("empire-marketing-deploy.service",),
    ),
    "enterprise_white_label": EvidenceSpec(
        code_patterns=(
            "empire_os/enterprise_*.py",
            "empire_os/whitelabel.py",
        ),
        test_patterns=("tests/test_enterprise_*.py",),
    ),
}


def _safe_pattern(pattern: str) -> bool:
    clean = str(pattern or "").strip().lstrip("./")
    if not clean:
        return False
    lowered = clean.lower()
    return not any(
        lowered == prefix.rstrip("/") or lowered.startswith(prefix)
        for prefix in PROTECTED_PREFIXES
    )


def _relative_matches(
    root: Path,
    patterns: Iterable[str],
) -> list[str]:
    matches: set[str] = set()
    for pattern in patterns:
        if not _safe_pattern(pattern):
            continue
        for path in root.glob(pattern):
            try:
                relative = path.relative_to(root).as_posix()
            except ValueError:
                continue
            if not _safe_pattern(relative):
                continue
            if path.is_file():
                matches.add(relative)
    return sorted(matches)


def _runtime_evidence(
    root: Path,
    paths: Iterable[str],
) -> tuple[list[str], str]:
    configured = [
        path for path in paths if _safe_pattern(path)
    ]
    if not configured:
        return [], "NOT_CONFIGURED"

    observed = [
        path
        for path in configured
        if (root / path).is_file()
    ]
    return sorted(observed), (
        "ARTIFACT_OBSERVED" if observed else "UNKNOWN"
    )


def _implementation_state(
    *,
    code_present: bool,
    tests_present: bool,
    service_present: bool,
) -> str:
    if code_present and tests_present:
        return "CODE_AND_TESTS_PRESENT"
    if code_present:
        return "CODE_PRESENT_TESTS_NOT_OBSERVED"
    if tests_present:
        return "TESTS_PRESENT_CODE_NOT_OBSERVED"
    if service_present:
        return "SERVICE_CONFIG_ONLY"
    return "NO_REPO_EVIDENCE"


def build_recovery_implementation_audit(
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    products: list[dict[str, Any]] = []

    for product in recovery_product_catalog():
        key = str(product.get("key") or "").strip()
        spec = EVIDENCE_SPECS.get(key, EvidenceSpec())
        code = _relative_matches(root, spec.code_patterns)
        tests = _relative_matches(root, spec.test_patterns)
        services = _relative_matches(root, spec.service_patterns)
        runtime, runtime_state = _runtime_evidence(
            root,
            spec.runtime_paths,
        )
        implementation_state = _implementation_state(
            code_present=bool(code),
            tests_present=bool(tests),
            service_present=bool(services),
        )
        products.append({
            "key": key,
            "name": product.get("name"),
            "registered_state": product.get("state"),
            "implementation_state": implementation_state,
            "code_evidence": code,
            "test_evidence": tests,
            "service_evidence": services,
            "runtime_artifact_evidence": runtime,
            "runtime_proof": runtime_state,
            "live_production_claimed": False,
            "pricing_approved_by_audit": False,
            "actual_revenue_claimed": False,
            "execution_authority": "none",
        })

    implementation_counts: dict[str, int] = {}
    runtime_counts: dict[str, int] = {}
    for row in products:
        implementation = str(row["implementation_state"])
        runtime = str(row["runtime_proof"])
        implementation_counts[implementation] = (
            implementation_counts.get(implementation, 0) + 1
        )
        runtime_counts[runtime] = runtime_counts.get(runtime, 0) + 1

    return {
        "schema_version": "empire.commercial-recovery-audit.v1",
        "mode": "OBSERVE",
        "product_count": len(products),
        "implementation_state_counts": dict(
            sorted(implementation_counts.items())
        ),
        "runtime_proof_counts": dict(sorted(runtime_counts.items())),
        "products": products,
        "registry_state_is_production_proof": False,
        "runtime_artifact_is_revenue_proof": False,
        "protected_paths_read": False,
        "pricing_authority": "none",
        "commercial_authority": "none",
        "accounting_authority": "none",
        "revenue_recognition_authority": "none",
        "execution_authority": "none",
        "actual_revenue": False,
    }
