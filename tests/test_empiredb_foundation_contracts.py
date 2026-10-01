from __future__ import annotations

import ast
from pathlib import Path

from empire_os.data_query import DataFilter, FilterOperator
from empire_os.sb import _data_filter


ROOT = Path(__file__).resolve().parents[1]


def test_no_retired_request_json_imports():
    bad = []

    for root in ("empire_os", "scripts"):
        for path in (ROOT / root).rglob("*.py"):
            tree = ast.parse(
                path.read_text(),
                filename=str(path),
            )

            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    == "empire_os.qualification_worker_v2"
                    and any(
                        alias.name == "request_json"
                        for alias in node.names
                    )
                ):
                    bad.append(str(path.relative_to(ROOT)))

    assert bad == []


def test_like_is_first_class_operator():
    item = DataFilter.like("fact_key", "private_capital.%")

    assert item.operator is FilterOperator.LIKE
    assert item.value == "private_capital.%"


def test_postgrest_like_star_becomes_sql_wildcard():
    item = _data_filter(
        "prospect_id",
        "like.prospect_*",
    )

    assert item.operator is FilterOperator.LIKE
    assert item.value == "prospect_%"


def test_postgrest_ilike_star_becomes_sql_wildcard():
    item = _data_filter(
        "notes",
        "ilike.*permit*",
    )

    assert item.operator is FilterOperator.ILIKE
    assert item.value == "%permit%"


def test_both_backends_support_like():
    for rel in (
        "empire_os/data_backends/empiredb.py",
        "empire_os/data_backends/supabase_legacy.py",
    ):
        source = (ROOT / rel).read_text()

        assert "FilterOperator.LIKE" in source
        assert "FilterOperator.ILIKE" in source


def test_exchange_uses_buyer_repository():
    source = (
        ROOT / "scripts/refresh_commercial_exchange.py"
    ).read_text()

    assert "BuyerAllocationDataRepository" in source
    assert "fetch_buyer_rows(buyer_repository)" in source
    assert "fetch_buyer_rows(reader)" not in source


def test_observe_unknown_is_healthy_process_state():
    source = (
        ROOT / "scripts/run_enterprise_contact_repair.py"
    ).read_text()

    assert '"RUNTIME_RETRY_EXHAUSTED"' in source
    assert '"OBSERVE_ONLY_UNKNOWN"' not in source


def test_json_text_filter_column_is_allowed():
    from empire_os.data_query import (
        DataFilter,
        postgres_filter_column,
    )

    item = DataFilter.eq(
        "evidence->>niche",
        "solar",
    )

    assert item.column == "evidence->>niche"
    assert (
        postgres_filter_column(item.column)
        == "\"evidence\"->>'niche'"
    )
def test_nested_json_filter_column_compiles_safely():
    from empire_os.data_query import postgres_filter_column

    assert (
        postgres_filter_column(
            "evidence->market->>country"
        )
        == "\"evidence\"->'market'->>'country'"
    )
def test_json_filter_column_rejects_sql_injection_shape():
    import pytest

    from empire_os.data_query import DataFilter

    with pytest.raises(ValueError):
        DataFilter.eq(
            "evidence->>niche) OR TRUE --",
            "solar",
        )


def test_legacy_not_null_renderer_keeps_column():
    from empire_os.data_backends.supabase_legacy import (
        _filter_param,
    )
    from empire_os.data_query import DataFilter

    assert _filter_param(
        DataFilter.is_not_null("website")
    ) == (
        "website",
        "not.is.null",
    )



def test_deferred_enrichment_unit_has_bounded_batch():
    from pathlib import Path

    unit = Path(
        "deploy/systemd/"
        "empire-buyer-deferred-enrichment.service"
    ).read_text()

    assert (
        "run_buyer_deferred_enrichment.py --limit 2"
        in unit
    )
    assert "TimeoutStartSec=300" in unit


def test_enterprise_activation_unit_loads_empiredb():
    from pathlib import Path

    unit = Path(
        "deploy/systemd/"
        "empire-predictive-revenue-enterprise-activation.service"
    ).read_text()

    assert "EnvironmentFile=/etc/empire_os.env" in unit
    assert "EnvironmentFile=/etc/empiredb.env" in unit
