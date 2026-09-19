"""Least-privilege PostgreSQL repository for Search Intelligence."""
from __future__ import annotations

import os
from typing import Any, Callable, Mapping, Sequence

from .repository import bounded_limit


class SearchRepositoryError(RuntimeError):
    pass


ROLE = "empire_search_reader"


class PostgresSearchRepository:
    """Tenant-scoped, read-only implementation of the SearchRepository contract."""

    def __init__(
        self,
        dsn: str,
        tenant_key: str,
        *,
        connect_factory: Callable | None = None,
    ) -> None:
        self.dsn = str(dsn or "").strip()
        self.tenant_key = str(tenant_key or "").strip()
        if not self.dsn:
            raise SearchRepositoryError(
                "dedicated Search Intelligence database DSN required"
            )
        if not self.tenant_key:
            raise SearchRepositoryError(
                "Search Intelligence tenant_key required"
            )

        if connect_factory is None:
            try:
                import psycopg
            except ImportError as exc:
                raise SearchRepositoryError(
                    "psycopg is required for Search Intelligence transport"
                ) from exc
            connect_factory = psycopg.connect
        self._connect = connect_factory

    @staticmethod
    def _row_dict(cursor, row) -> dict[str, Any]:
        names = [
            column.name if hasattr(column, "name") else column[0]
            for column in cursor.description
        ]
        return dict(zip(names, row))

    def _read(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        try:
            with self._connect(self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute(f"SET LOCAL ROLE {ROLE}")
                    cursor.execute(
                        "SELECT set_config('app.tenant_key', %s, true)",
                        (self.tenant_key,),
                    )
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    return [
                        self._row_dict(cursor, row)
                        for row in rows
                    ]
        except Exception as exc:
            raise SearchRepositoryError(
                "Search Intelligence read failed"
            ) from exc

    def summary(self) -> Mapping[str, Any]:
        rows = self._read(
            """
            SELECT
              (SELECT count(*)
                 FROM public.seo_pages p
                 JOIN public.seo_sites s ON s.id = p.site_id
                WHERE s.tenant_key = %s) AS pages,
              (SELECT count(*)
                 FROM public.seo_opportunities o
                 JOIN public.seo_sites s ON s.id = o.site_id
                WHERE s.tenant_key = %s) AS opportunities,
              (SELECT count(*)
                 FROM public.seo_pages p
                 JOIN public.seo_sites s ON s.id = p.site_id
                WHERE s.tenant_key = %s
                  AND p.index_state = 'INDEXED') AS indexed_pages,
              (SELECT count(*)
                 FROM public.seo_alerts a
                 JOIN public.seo_sites s ON s.id = a.site_id
                WHERE s.tenant_key = %s
                  AND a.status = 'open') AS open_alerts,
              (SELECT coalesce(sum(r.revenue_cents), 0)
                 FROM public.seo_revenue_attribution r
                 JOIN public.seo_sites s ON s.id = r.site_id
                WHERE s.tenant_key = %s) AS revenue_cents
            """,
            (self.tenant_key,) * 5,
        )
        if len(rows) != 1:
            raise SearchRepositoryError(
                "Search Intelligence summary returned invalid result"
            )
        return rows[0]

    def pages(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        return self._read(
            """
            SELECT
              p.id,p.site_id,p.url,p.slug,p.page_type,p.title,
              p.meta_description,p.canonical_url,p.robots_state,
              p.indexable,p.content_quality_score,p.opportunity_score,
              p.target_query,p.search_intent,p.industry,p.location,
              p.service,p.topic,p.entity_references,p.publish_state,
              p.index_state,p.first_published_at,p.last_modified_at,
              p.last_crawled_at,p.last_indexed_at,p.refresh_required,
              p.revenue_attributed_cents,p.leads_attributed,
              p.conversions_attributed,p.created_at,p.updated_at
            FROM public.seo_pages p
            JOIN public.seo_sites s ON s.id = p.site_id
            WHERE s.tenant_key = %s
            ORDER BY p.updated_at DESC, p.id
            LIMIT %s
            """,
            (self.tenant_key, bounded_limit(limit)),
        )

    def opportunities(
        self,
        *,
        limit: int,
    ) -> Sequence[Mapping[str, Any]]:
        return self._read(
            """
            SELECT
              o.id,o.site_id,o.query_id,o.query,o.topic,o.intent,
              o.commercial_intent,o.competitor_presence,
              o.current_empire_coverage,o.content_gap,
              o.target_page_type,o.relevance,o.authority_fit,
              o.trend_signal,o.conversion_history,
              o.revenue_history_cents,o.estimated_business_value_cents,
              o.intent_score,o.conversion_probability,o.freshness,
              o.competition,o.opportunity_score,o.score_reason,
              o.observed_at
            FROM public.seo_opportunities o
            JOIN public.seo_sites s ON s.id = o.site_id
            WHERE s.tenant_key = %s
            ORDER BY o.opportunity_score DESC NULLS LAST,
                     o.observed_at DESC,
                     o.id
            LIMIT %s
            """,
            (self.tenant_key, bounded_limit(limit)),
        )

    def indexation(
        self,
        *,
        limit: int,
    ) -> Sequence[Mapping[str, Any]]:
        return self._read(
            """
            SELECT
              i.id,i.page_id,p.url,i.state,i.source,
              i.details,i.observed_at
            FROM public.seo_indexation i
            JOIN public.seo_pages p ON p.id = i.page_id
            JOIN public.seo_sites s ON s.id = p.site_id
            WHERE s.tenant_key = %s
            ORDER BY i.observed_at DESC, i.id
            LIMIT %s
            """,
            (self.tenant_key, bounded_limit(limit)),
        )

    def decay(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        return self._read(
            """
            SELECT
              p.id AS page_id,p.url,p.topic,p.target_query,
              p.last_modified_at,p.last_crawled_at,p.last_indexed_at,
              p.refresh_required,p.content_quality_score,
              p.revenue_attributed_cents
            FROM public.seo_pages p
            JOIN public.seo_sites s ON s.id = p.site_id
            WHERE s.tenant_key = %s
              AND p.refresh_required = true
            ORDER BY p.updated_at DESC, p.id
            LIMIT %s
            """,
            (self.tenant_key, bounded_limit(limit)),
        )

    def cannibalisation(
        self,
        *,
        limit: int,
    ) -> Sequence[Mapping[str, Any]]:
        return self._read(
            """
            SELECT
              p.target_query AS query,
              count(*)::integer AS page_count,
              json_agg(p.url ORDER BY p.url) AS urls
            FROM public.seo_pages p
            JOIN public.seo_sites s ON s.id = p.site_id
            WHERE s.tenant_key = %s
              AND nullif(trim(p.target_query), '') IS NOT NULL
            GROUP BY p.target_query
            HAVING count(*) > 1
            ORDER BY count(*) DESC, p.target_query
            LIMIT %s
            """,
            (self.tenant_key, bounded_limit(limit)),
        )

    def alerts(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        return self._read(
            """
            SELECT
              a.id,a.site_id,a.page_id,p.url,a.alert_type,
              a.severity,a.evidence,a.status,a.created_at,a.resolved_at
            FROM public.seo_alerts a
            JOIN public.seo_sites s ON s.id = a.site_id
            LEFT JOIN public.seo_pages p ON p.id = a.page_id
            WHERE s.tenant_key = %s
            ORDER BY
              CASE a.severity
                WHEN 'critical' THEN 4
                WHEN 'high' THEN 3
                WHEN 'warning' THEN 2
                ELSE 1
              END DESC,
              a.created_at DESC,
              a.id
            LIMIT %s
            """,
            (self.tenant_key, bounded_limit(limit)),
        )

    def revenue(self, *, limit: int) -> Sequence[Mapping[str, Any]]:
        return self._read(
            """
            SELECT
              r.id,r.site_id,r.page_id,p.url,r.query,
              r.external_session_id,r.prospect_id,
              r.external_conversation_id,r.opportunity_id,
              r.fulfilment_order_id,r.commercial_event_id,
              r.revenue_cents,r.attribution_kind,
              r.occurred_at,r.recorded_at
            FROM public.seo_revenue_attribution r
            JOIN public.seo_sites s ON s.id = r.site_id
            LEFT JOIN public.seo_pages p ON p.id = r.page_id
            WHERE s.tenant_key = %s
            ORDER BY r.occurred_at DESC, r.id
            LIMIT %s
            """,
            (self.tenant_key, bounded_limit(limit)),
        )



def configured_search_repository_from_env(
    *,
    connect_factory: Callable | None = None,
) -> PostgresSearchRepository | None:
    """Return the gated repository only when both runtime bindings exist."""
    dsn = os.getenv("EMPIRE_SEARCH_READER_DSN", "").strip()
    tenant_key = os.getenv("EMPIRE_SEARCH_TENANT_KEY", "").strip()
    if not dsn or not tenant_key:
        return None
    return PostgresSearchRepository(
        dsn,
        tenant_key,
        connect_factory=connect_factory,
    )
