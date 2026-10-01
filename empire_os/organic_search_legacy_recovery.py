"""Read-only recovery view for organic search assets and legacy marketing stores."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

AEO_REPORT = Path("runtime/search_intelligence/aeo_recovery/latest.json")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def build_recovery_manifest(
    root: str | Path,
    *,
    twenty_plugin_path: str | Path | None = None,
    listmonk_artifacts: tuple[str | Path, ...] = (),
) -> dict[str, Any]:
    root = Path(root)
    report = _read_json(root / AEO_REPORT)

    if report is None:
        organic = {
            "state": "UNKNOWN",
            "asset_count": None,
            "review_ready_count": None,
            "publish_allowed_count": None,
            "form_present_count": None,
            "blockers": ["aeo_recovery_report_missing"],
        }
    else:
        assets = [row for row in report.get("assets", []) if isinstance(row, dict)]
        review_ready = [
            row for row in assets
            if row.get("status") == "structure_ready_for_evidence_review"
            and not row.get("risk_flags")
        ]
        publish_allowed = [row for row in assets if row.get("publish_allowed") is True]
        forms = [row for row in assets if row.get("form_present") is True]
        blockers: list[str] = []
        if len(review_ready) != len(assets):
            blockers.append("asset_quality_or_risk_review")
        if not publish_allowed:
            blockers.append("evidence_review_and_publish_authority")
        if not forms:
            blockers.append("canonical_enquiry_capture")
        organic = {
            "state": "REVIEW_READY" if assets and len(review_ready) == len(assets) else "BLOCKED",
            "asset_count": len(assets),
            "niche_count": report.get("niche_count"),
            "metro_count": report.get("metro_count"),
            "unique_content_hashes": report.get("unique_content_hashes"),
            "review_ready_count": len(review_ready),
            "publish_allowed_count": len(publish_allowed),
            "form_present_count": len(forms),
            "risk_counts": report.get("risk_counts") or {},
            "blockers": blockers,
            "publishing_authority": False,
            "indexation_authority": False,
        }

    twenty_path = Path(twenty_plugin_path) if twenty_plugin_path else None
    twenty_plugin_present = bool(twenty_path and twenty_path.is_file())
    listmonk_present = any(Path(p).exists() for p in listmonk_artifacts)

    legacy = {
        "twenty": {
            "plugin_definition_present": twenty_plugin_present,
            "local_runtime_data_proven": False,
            "migration_proven": False,
            "recovery_state": "EXTERNAL_EXPORT_OR_INSTANCE_REQUIRED",
        },
        "listmonk": {
            "local_artifact_present": listmonk_present,
            "local_runtime_data_proven": False,
            "migration_proven": False,
            "recovery_state": "EXTERNAL_EXPORT_OR_INSTANCE_REQUIRED",
        },
        "safe_action": "inventory_and_compare_only",
        "automatic_import_allowed": False,
    }

    return {
        "schema_version": "empire.organic-search-legacy-recovery.v1",
        "mode": "OBSERVE",
        "organic_search": organic,
        "legacy_marketing_sources": legacy,
        "gates": {
            "canonical_enquiry_schema": True,
            "evidence_review": True,
            "publishing_or_indexation": True,
            "external_source_export_or_credentials": True,
        },
        "actions_performed": {
            "publish": False,
            "index": False,
            "import_leads": False,
            "send_outbound": False,
            "database_mutation": False,
        },
        "execution_authority": "none",
    }
