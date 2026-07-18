"""Revenue Dashboard — Marketplace analytics engine for real-time revenue tracking.

Provides comprehensive dashboard data for:
- Sales revenue (Stripe/PayPal integration)
- Leads generated and conversion metrics
- Platform usage and performance analytics
- Real-time market insights

Integrates with Empire OS existing systems:
- Empire OS v3 funnel (leads, conversions)
- Daily revenue snapshots
- Marketplace lead-to-cash pipeline
- Stripe/PayPal payment tracking
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import sqlite3

from empire_os.funnel import SQLiteBackend, count_by_state
from empire_os.daily_revenue import DailyRevenueSnapshotter

logger = logging.getLogger("revenue_dashboard")

DB_PATH = "/root/empire_os/empire_os.db"


class RevenueDashboard:
    """
    Real-time revenue dashboard for marketplace analytics.

    Consolidates data from multiple sources:
    - Live funnel counts (leads, conversions)
    - Daily revenue snapshots
    - Marketplace lead pricing and tiers
    - Agent performance metrics
    - Platform usage statistics
    """

    def __init__(self, backend: Optional[SQLiteBackend] = None):
        self.backend = backend or SQLiteBackend(DB_PATH)
        self.backend.ensure_schema()

    def get_dashboard_data(self) -> dict:
        """
        Get comprehensive dashboard data for all marketplace metrics.

        Returns:
            Complete dashboard payload with:
            - Revenue metrics (today/yesterday/last 7 days)
            - Lead generation and conversion analytics
            - Platform usage statistics
            - Real-time performance indicators
            - Market insights
        """
        try:
            # Core revenue metrics
            revenue_today = self._get_revenue_today()
            revenue_7day = self._get_revenue_7day()
            revenue_month = self._get_revenue_30day()

            # Lead metrics (from funnel)
            funnel_counts = count_by_state(self.backend)
            leads_total = sum(funnel_counts.values())
            lead_conversion_rate = self._calculate_conversion_rate(funnel_counts)

            # Marketplace metrics
            marketplace_data = self._get_marketplace_metrics()

            # Agent performance
            agent_performance = self._get_agent_performance()

            # Platform usage
            platform_usage = self._get_platform_usage()

            # Real-time indicators
            real_time = self._get_real_time_indicators()

            # Market insights
            market_insights = self._generate_market_insights(
                revenue_7day, funnel_counts, marketplace_data
            )

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "engine": "Empire OS Revenue Dashboard",
                "version": "3.0.0",

                # Revenue Metrics
                "revenue": {
                    "today": revenue_today,
                    "7day": revenue_7day,
                    "30day": revenue_month,
                    "growth_rate": self._calculate_growth_rate(revenue_7day),
                    "average_deal_size": self._calculate_average_deal_size(),
                    "payment_methods": self._get_payment_method_breakdown(),
                },

                # Lead Metrics
                "leads": {
                    "total": leads_total,
                    "by_state": funnel_counts,
                    "conversion_rate": lead_conversion_rate,
                    "conversion_by_stage": self._get_conversion_by_stage(funnel_counts),
                    "lead_sources": self._get_lead_sources(),
                    "quality_metrics": self._get_lead_quality_metrics(),
                },

                # Marketplace Metrics
                "marketplace": marketplace_data,

                # Performance Metrics
                "performance": agent_performance,

                # Platform Usage
                "platform": platform_usage,

                # Real-time Indicators
                "real_time": real_time,

                # Market Insights
                "insights": market_insights,

                # Summary KPIs
                "kpis": self._calculate_kpis(
                    revenue_today, leads_total, funnel_counts, marketplace_data
                ),
            }

        except Exception as e:
            logger.error("Dashboard data error: %s", e)
            return self._get_error_response(str(e))

    def _get_revenue_today(self) -> dict:
        """Get today's revenue (current day)."""
        today = datetime.now(timezone.utc).date().isoformat()

        # Check if we have today's revenue in daily_revenue_snapshots
        try:
            cursor = self.backend.execute(
                """SELECT gross_cents, settled_cents, settlement_count
                   FROM daily_revenue_snapshots
                   WHERE snapshot_date = ? AND tenant_id = 'default'""",
                (today,)
            )
            row = cursor.fetchone()

            if row:
                gross_usd = row["gross_cents"] / 100
                settled_usd = row["settled_cents"] / 100
                return {
                    "date": today,
                    "gross_revenue_usd": round(gross_usd, 2),
                    "settled_revenue_usd": round(settled_usd, 2),
                    "settlements_count": row["settlement_count"],
                    "pending_amount_usd": round(gross_usd - settled_usd, 2),
                }

        except Exception as e:
            logger.warning("Error fetching today revenue: %s", e)

        # Fallback: calculate from si_settlements for today
        try:
            cursor = self.backend.execute(
                """SELECT COALESCE(SUM(amount_cents), 0) as gross_cents,
                          COUNT(*) as settlement_count
                   FROM si_settlements
                   WHERE DATE(settled_at) = ?
                   AND settled_by != 'voided'""",
                (today,)
            )
            row = cursor.fetchone()

            if row:
                gross_usd = row["gross_cents"] / 100
                return {
                    "date": today,
                    "gross_revenue_usd": round(gross_usd, 2),
                    "settled_revenue_usd": round(gross_usd, 2),
                    "settlements_count": row["settlement_count"],
                    "pending_amount_usd": 0.0,
                }

        except Exception as e:
            logger.warning("Error fetching today revenue fallback: %s", e)

        # Return zero data if no revenue found
        return {
            "date": today,
            "gross_revenue_usd": 0.0,
            "settled_revenue_usd": 0.0,
            "settlements_count": 0,
            "pending_amount_usd": 0.0,
        }

    def _get_revenue_7day(self) -> dict:
        """Get revenue for the last 7 days."""
        revenue_data = []
        total_gross = 0.0
        total_settled = 0.0
        total_settlements = 0

        for i in range(7):
            date = (datetime.now(timezone.utc) - timedelta(days=i)).date().isoformat()

            try:
                cursor = self.backend.execute(
                    """SELECT gross_cents, settled_cents, settlement_count
                       FROM daily_revenue_snapshots
                       WHERE snapshot_date = ? AND tenant_id = 'default'""",
                    (date,)
                )
                row = cursor.fetchone()

                if row:
                    gross_usd = row["gross_cents"] / 100
                    settled_usd = row["settled_cents"] / 100
                    counts = row["settlement_count"]
                else:
                    # Fallback from si_settlements
                    cursor = self.backend.execute(
                        """SELECT COALESCE(SUM(amount_cents), 0) as gross_cents,
                              COUNT(*) as settlement_count
                       FROM si_settlements
                       WHERE DATE(settled_at) = ?
                       AND settled_by != 'voided'""",
                        (date,)
                    )
                    row = cursor.fetchone()
                    if row:
                        gross_usd = row["gross_cents"] / 100
                        settled_usd = gross_usd
                        counts = row["settlement_count"]
                    else:
                        gross_usd = settled_usd = 0.0
                        counts = 0

                revenue_data.append({
                    "date": date,
                    "gross_revenue_usd": round(gross_usd, 2),
                    "settled_revenue_usd": round(settled_usd, 2),
                    "settlements_count": counts,
                })

                total_gross += gross_usd
                total_settled += settled_usd
                total_settlements += counts

            except Exception as e:
                logger.warning("Error fetching 7day revenue for %s: %s", date, e)
                revenue_data.append({
                    "date": date,
                    "gross_revenue_usd": 0.0,
                    "settled_revenue_usd": 0.0,
                    "settlements_count": 0,
                })

        # Calculate 7-day growth rate (compare first 3 days vs last 3 days)
        if len(revenue_data) >= 6:
            first_half_gross = sum(
                d["gross_revenue_usd"] for d in revenue_data[:3]
            )
            second_half_gross = sum(
                d["gross_revenue_usd"] for d in revenue_data[3:6]
            )
            growth_rate = (
                ((second_half_gross - first_half_gross) / first_half_gross * 100)
                if first_half_gross > 0 else 0.0
            )
        else:
            growth_rate = 0.0

        return {
            "period_days": 7,
            "total_gross_usd": round(total_gross, 2),
            "total_settled_usd": round(total_settled, 2),
            "total_settlements": total_settlements,
            "growth_rate_pct": round(growth_rate, 2),
            "daily_data": revenue_data,
        }

    def _get_revenue_30day(self) -> dict:
        """Get revenue for the last 30 days."""
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=29)

        try:
            cursor = self.backend.execute(
                """SELECT COALESCE(SUM(gross_cents), 0) as total_gross,
                          COALESCE(SUM(settled_cents), 0) as total_settled,
                          COUNT(*) as total_settlements
                   FROM daily_revenue_snapshots
                   WHERE snapshot_date >= ? AND snapshot_date <= ?
                   AND tenant_id = 'default'""",
                (start_date.isoformat(), end_date.isoformat())
            )
            row = cursor.fetchone()

            if row:
                total_gross = row["total_gross"] / 100
                total_settled = row["total_settled"] / 100
                total_settlements = row["total_settlements"]

                # Calculate month-over-month growth (simple)
                prev_month_start = start_date - timedelta(days=30)
                prev_cursor = self.backend.execute(
                    """SELECT COALESCE(SUM(gross_cents), 0) as prev_gross
                       FROM daily_revenue_snapshots
                       WHERE snapshot_date >= ? AND snapshot_date < ?
                       AND tenant_id = 'default'""",
                    (prev_month_start.isoformat(), start_date.isoformat())
                )
                prev_row = prev_cursor.fetchone()
                prev_gross = prev_row["prev_gross"] / 100 if prev_row else 0.0

                mom_growth = (
                    ((total_gross - prev_gross) / prev_gross * 100)
                    if prev_gross > 0 else 0.0
                )

                return {
                    "period_days": 30,
                    "total_gross_usd": round(total_gross, 2),
                    "total_settled_usd": round(total_settled, 2),
                    "total_settlements": total_settlements,
                    "growth_rate_pct": round(mom_growth, 2),
                    "average_daily_usd": round(total_gross / 30, 2),
                }

        except Exception as e:
            logger.warning("Error fetching 30day revenue: %s", e)

        return {
            "period_days": 30,
            "total_gross_usd": 0.0,
            "total_settled_usd": 0.0,
            "total_settlements": 0,
            "growth_rate_pct": 0.0,
            "average_daily_usd": 0.0,
        }

    def _calculate_conversion_rate(self, funnel_counts: dict) -> float:
        """Calculate average conversion rate across funnel stages."""
        if not funnel_counts:
            return 0.0
        
        total_leads = sum(funnel_counts.values())
        if total_leads == 0:
            return 0.0
        
        # Use settled leads as conversion metric
        settled_leads = funnel_counts.get("settled", 0)
        conversion_rate = (settled_leads / total_leads) * 100
        
        return round(conversion_rate, 2)

    def _get_marketplace_metrics(self) -> dict:
        """Get marketplace-specific metrics and analytics."""
        metrics = {
            "active_subscriptions": 0,
            "lead_tiers_performance": {},
            "subscription_revenue": 0.0,
            "per_call_revenue": 0.0,
            "tier_breakdown": {},
            "recent_transactions": [],
        }

        try:
            # Lead tiers performance from funnel counts
            funnel_counts = count_by_state(self.backend)
            metrics["lead_tiers_performance"] = {
                "bronze": funnel_counts.get("discovered", 0) * 25,
                "silver": funnel_counts.get("matched", 0) * 75,
                "gold": funnel_counts.get("settled", 0) * 150,
            }

            # Subscription data from si_subscription
            cursor = self.backend.execute(
                """SELECT COUNT(DISTINCT tenant_id) as active_subs,
                          COALESCE(SUM(price_cents), 0) as monthly_revenue
                   FROM si_subscription
                   WHERE status = 'active'"""
            )
            row = cursor.fetchone()
            if row:
                metrics["active_subscriptions"] = row["active_subs"] or 0
                metrics["subscription_revenue"] = row["monthly_revenue"] / 100

            # Payment method breakdown
            metrics["payment_methods"] = self._get_payment_method_breakdown()

            # Recent transactions
            metrics["recent_transactions"] = self._get_recent_transactions(10)

        except Exception as e:
            logger.warning("Error fetching marketplace metrics: %s", e)

        return metrics

    def _get_payment_method_breakdown(self) -> dict:
        """Get revenue breakdown by payment method (Stripe/PayPal/Crypto)."""
        breakdown = {
            "stripe": 0.0,
            "paypal": 0.0,
            "crypto_usdc": 0.0,
            "manual": 0.0,
        }

        try:
            # Get settled revenue by payment method from charges table
            cursor = self.backend.execute(
                """SELECT processor, COALESCE(SUM(amount_cents), 0) as total_cents
                   FROM si_charges
                   WHERE status = 'succeeded'
                   GROUP BY processor"""
            )

            for row in cursor.fetchall():
                method = row["processor"]
                amount = row["total_cents"] / 100
                if method in breakdown:
                    breakdown[method] = round(amount, 2)

        except Exception as e:
            logger.warning("Error fetching payment method breakdown: %s", e)

        return breakdown

    def _get_recent_transactions(self, limit: int = 10) -> list:
        """Get recent marketplace transactions."""
        try:
            # Use settled leads as transactions
            cursor = self.backend.execute(
                """SELECT s.prospect_id, s.to_state, s.occurred_at, s.actor
                   FROM si_settlements s
                   WHERE s.settled_by != 'voided'
                   ORDER BY s.occurred_at DESC
                   LIMIT ?""",
                (limit,)
            )

            transactions = []
            for row in cursor.fetchall():
                # Get amount from si_charge or use default
                amount_cents = 0
                try:
                    charge_cursor = self.backend.execute(
                        "SELECT COALESCE(SUM(amount_cents), 0) FROM si_charges WHERE prospect_id = ?",
                        (row["prospect_id"],)
                    )
                    amount_cents = charge_cursor.fetchone()[0] or 0
                except Exception:
                    pass

                transactions.append({
                    "prospect_id": row["prospect_id"],
                    "state": row["to_state"],
                    "timestamp": row["occurred_at"],
                    "actor": row["actor"],
                    "amount_usd": round(amount_cents / 100, 2) if amount_cents else 0.0,
                    "status": "settled",
                })

            return transactions

        except Exception as e:
            logger.warning("Error fetching recent transactions: %s", e)
            return []

    def _get_agent_performance(self) -> dict:
        """Get performance metrics for all agents."""
        performance = {}

        try:
            # Import AGENT_GOALS from revenue_goals module
            from empire_os.revenue_goals import AGENT_GOALS
            
            for agent_name, goal_config in AGENT_GOALS.items():
                performance[agent_name] = {
                    "lever": goal_config.get("revenue_lever", ""),
                    "target": goal_config.get("baseline_target", 0),
                    "actual_outputs": 0,  # Simplified - would need agent-specific logic
                    "actual_revenue_usd": 0.0,  # Simplified - would need marketplace data
                    "progress_pct": 0.0,  # Simplified - would need actual vs target
                    "status": "unknown",  # Would need real status logic
                    "weekly_target_mrr": goal_config.get("baseline_target", 0) * 50,  # Estimate
                    "actual_mrr": 0.0,  # Simplified - would need real MRR
                }

        except Exception as e:
            logger.warning("Error fetching agent performance: %s", e)

        return performance

    def _get_platform_usage(self) -> dict:
        """Get platform usage statistics."""
        usage = {
            "total_leads_processed": 0,
            "active_prospects": 0,
            "system_health": "healthy",
            "peak_usage_hours": [],
            "resource_utilization": {},
        }

        try:
            # Total leads processed
            cursor = self.backend.execute(
                "SELECT COUNT(*) FROM si_funnel_event"
            )
            usage["total_leads_processed"] = cursor.fetchone()[0]

            # Active prospects (leads in non-final states)
            cursor = self.backend.execute(
                """SELECT COUNT(DISTINCT prospect_id) 
                   FROM si_funnel_event 
                   WHERE to_state NOT IN ('settled', 'done', 'collected')"""
            )
            usage["active_prospects"] = cursor.fetchone()[0] or 0

            # System health check - check recent activity
            from datetime import datetime, timedelta
            one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
            cursor = self.backend.execute(
                "SELECT COUNT(*) FROM si_funnel_event WHERE occurred_at > ?",
                (one_hour_ago,)
            )
            recent_activity = cursor.fetchone()[0]
            usage["system_health"] = "healthy" if recent_activity > 10 else "degraded"

        except Exception as e:
            logger.warning("Error fetching platform usage: %s", e)

        return usage

    def _get_real_time_indicators(self) -> dict:
        """Get real-time platform indicators."""
        indicators = {
            "current_hour_activity": 0,
            "lead_rate_per_hour": 0.0,
            "revenue_rate_per_hour": 0.0,
            "active_sessions": 0,
            "alerts_active": 0,
        }

        try:
            # Current hour activity
            cursor = self.backend.execute(
                """SELECT COUNT(*) FROM si_funnel_event
                   WHERE strftime('%Y-%m-%d %H:00:00', occurred_at) = strftime('%Y-%m-%d %H:00:00', 'now')"""
            )
            indicators["current_hour_activity"] = cursor.fetchone()[0] or 0

            # Lead rate per hour (last 24 hours)
            cursor = self.backend.execute(
                """SELECT COUNT(*) FROM si_funnel_event
                   WHERE occurred_at >= datetime('now', '-24 hours')"""
            )
            leads_24h = cursor.fetchone()[0] or 0
            indicators["lead_rate_per_hour"] = round(leads_24h / 24, 1)

            # Revenue rate per hour (last 24 hours)
            cursor = self.backend.execute(
                """SELECT COALESCE(SUM(amount_cents), 0) FROM si_settlements
                   WHERE settled_at >= datetime('now', '-24 hours')
                   AND settled_by != 'voided'"""
            )
            revenue_24h = cursor.fetchone()[0] or 0
            indicators["revenue_rate_per_hour"] = round(revenue_24h / 24 / 100, 2)

        except Exception as e:
            logger.warning("Error fetching real-time indicators: %s", e)

        return indicators

    def _generate_market_insights(self, revenue_7day: dict, funnel_counts: dict,
                                  marketplace_data: dict) -> dict:
        """Generate market insights and analytics."""
        insights = {
            "trending_topics": [],
            "performance_alerts": [],
            "market_opportunities": [],
            "risk_factors": [],
        }

        # Revenue trend analysis
        if revenue_7day["total_gross_usd"] > 0:
            if revenue_7day["growth_rate_pct"] > 10:
                insights["performance_alerts"].append({
                    "type": "revenue_growth",
                    "message": f"Strong revenue growth: {revenue_7day['growth_rate_pct']:.1f}% over last 7 days",
                    "severity": "positive",
                })
            elif revenue_7day["growth_rate_pct"] < -10:
                insights["performance_alerts"].append({
                    "type": "revenue_decline",
                    "message": f"Revenue decline: {revenue_7day['growth_rate_pct']:.1f}% over last 7 days",
                    "severity": "warning",
                })

        # Lead quality analysis
        total_leads = sum(funnel_counts.values())
        conversion_rate = (
            (funnel_counts.get("settled", 0) / total_leads * 100)
            if total_leads > 0 else 0
        )
        if conversion_rate < 5:
            insights["risk_factors"].append({
                "type": "low_conversion_rate",
                "message": f"Lead conversion rate is low: {conversion_rate:.1f}%",
                "severity": "medium",
            })
        elif conversion_rate > 20:
            insights["market_opportunities"].append({
                "type": "high_conversion",
                "message": f"Excellent conversion rate: {conversion_rate:.1f}%",
                "severity": "positive",
            })

        # Marketplace opportunities
        if marketplace_data.get("active_subscriptions", 0) < 10:
            insights["market_opportunities"].append({
                "type": "subscription_growth",
                "message": "Subscription base is small - consider growth strategies",
                "severity": "medium",
            })

        # Default insights if none generated
        if not insights["performance_alerts"] and not insights["market_opportunities"]:
            insights["trending_topics"].append({
                "topic": "Stable Operations",
                "message": "Platform operating normally with consistent performance",
                "confidence": "high",
            })

        return insights

    def _calculate_kpis(self, revenue_today: dict, leads_total: int,
                        funnel_counts: dict, marketplace_data: dict) -> dict:
        """Calculate key performance indicators."""
        kpis = {
            "daily_revenue_target_vs_actual": 0.0,
            "lead_velocity": 0.0,
            "customer_lifetime_value": 0.0,
            "platform_efficiency_score": 0.0,
            "market_health_score": 0.0,
        }

        # Daily revenue KPI (simple target: $1000/day)
        daily_target = 1000.0
        daily_actual = revenue_today["settled_revenue_usd"]
        kpis["daily_revenue_target_vs_actual"] = round(
            (daily_actual / daily_target * 100), 1
        ) if daily_target > 0 else 0.0

        # Lead velocity (leads per day this month)
        leads_per_day = leads_total / 30
        kpis["lead_velocity"] = round(leads_per_day, 1)

        # Customer lifetime value (simplified: total revenue / active customers)
        active_customers = marketplace_data.get("active_subscriptions", 1)
        total_revenue = revenue_today["settled_revenue_usd"]
        kpis["customer_lifetime_value"] = round(total_revenue / active_customers, 2) if active_customers > 0 else 0.0

        # Platform efficiency score (weighted average of conversion rates)
        total_leads = sum(funnel_counts.values())
        conversion_rate = (funnel_counts.get("settled", 0) / total_leads * 100) if total_leads > 0 else 0
        kpis["platform_efficiency_score"] = round(min(conversion_rate / 5, 100), 1)

        # Market health score (composite metric)
        revenue_health = min(revenue_today["settled_revenue_usd"] / 500, 1.0)  # Scale to $500 target
        lead_health = min(conversion_rate / 10, 1.0)  # Scale to 10% conversion
        subscription_health = min(marketplace_data.get("active_subscriptions", 0) / 5, 1.0)  # Scale to 5 subs
        kpis["market_health_score"] = round((revenue_health + lead_health + subscription_health) / 3 * 100, 1)

        return kpis

    def _calculate_growth_rate(self, revenue_7day: dict) -> float:
        """Calculate revenue growth rate."""
        return revenue_7day.get("growth_rate_pct", 0.0)

    def _calculate_average_deal_size(self) -> float:
        """Calculate average deal size from settled leads."""
        try:
            cursor = self.backend.execute(
                """SELECT AVG(amount_cents) as avg_amount
                   FROM si_charges
                   WHERE status = 'succeeded'"""
            )
            row = cursor.fetchone()
            return round(row["avg_amount"] / 100, 2) if row and row["avg_amount"] else 0.0
        except Exception as e:
            logger.warning("Error calculating average deal size: %s", e)
            return 0.0

    def _get_conversion_by_stage(self, funnel_counts: dict) -> dict:
        """Get conversion rates by stage."""
        if not funnel_counts:
            return {}

        total = sum(funnel_counts.values())
        return {
            stage: round((count / total * 100), 2)
            for stage, count in funnel_counts.items()
        }

    def _get_lead_sources(self) -> dict:
        """Get lead sources breakdown."""
        try:
            cursor = self.backend.execute(
                """SELECT source, COUNT(DISTINCT prospect_id) as count
                   FROM si_prospect_consent
                   WHERE source IS NOT NULL AND source != ''
                   GROUP BY source
                   ORDER BY count DESC
                   LIMIT 10"""
            )

            return {
                row["source"]: row["count"]
                for row in cursor.fetchall()
            }
        except Exception as e:
            logger.warning("Error fetching lead sources: %s", e)
            return {}

    def _get_lead_quality_metrics(self) -> dict:
        """Get lead quality metrics (tonality, scoring, etc.)."""
        metrics = {
            "high_value_leads": 0,
            "medium_value_leads": 0,
            "low_value_leads": 0,
            "average_lead_score": 0.0,
        }

        try:
            # Count leads by tier/qualitative scoring
            cursor = self.backend.execute(
                """SELECT COUNT(DISTINCT prospect_id) as count
                   FROM (
                     SELECT prospect_id
                     FROM si_funnel_event
                     WHERE to_state IN ('matched', 'settled', 'claimed')
                   )"""
            )
            metrics["high_value_leads"] = cursor.fetchone()[0] or 0

            cursor = self.backend.execute(
                """SELECT COUNT(DISTINCT prospect_id) as count
                   FROM si_funnel_event
                   WHERE to_state = 'matched'"""
            )
            metrics["medium_value_leads"] = cursor.fetchone()[0] or 0

            cursor = self.backend.execute(
                "SELECT COUNT(DISTINCT prospect_id) FROM si_funnel_event WHERE to_state = 'discovered'"
            )
            metrics["low_value_leads"] = cursor.fetchone()[0] or 0

        except Exception as e:
            logger.warning("Error fetching lead quality metrics: %s", e)

        return metrics

    def _get_error_response(self, error_message: str) -> dict:
        """Generate error response for dashboard data."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "engine": "Empire OS Revenue Dashboard",
            "version": "3.0.0",
            "error": "Dashboard data generation failed",
            "message": error_message,
            "fallback_data": self._get_minimal_fallback_data(),
        }

    def _get_minimal_fallback_data(self) -> dict:
        """Get minimal fallback data when dashboard generation fails."""
        return {
            "revenue": {"today": {"gross_revenue_usd": 0.0, "settled_revenue_usd": 0.0}},
            "leads": {"total": 0, "by_state": {}},
            "marketplace": {},
            "performance": {},
            "platform": {"system_health": "error"},
        }


def get_dashboard_json() -> dict:
    """
    Get formatted dashboard data as JSON-compatible dict.

    This is the main entry point for dashboard API endpoints.
    """
    dashboard = RevenueDashboard()
    return dashboard.get_dashboard_data()


if __name__ == "__main__":
    # Test the dashboard
    data = get_dashboard_json()
    print(json.dumps(data, indent=2, default=str))