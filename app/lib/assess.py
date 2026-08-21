"""Assessment queries — the read layer behind the Governance-Hub-style Overview.

Every function returns a pandas DataFrame from system tables. All cost is at
LIST price (system.billing.list_prices); actual invoice varies by contract.
"""
from __future__ import annotations

from .auth import run_sql

# --- price join reused across queries -------------------------------------
_PRICED = """
  system.billing.usage u
  JOIN system.billing.list_prices lp
    ON u.sku_name = lp.sku_name
   AND u.usage_end_time >= lp.price_start_time
   AND (u.usage_end_time < lp.price_end_time OR lp.price_end_time IS NULL)
"""


# ---- COST pillar ----------------------------------------------------------
def spend_headline(lookback_days: int = 30):
    return run_sql(
        f"""
        SELECT
          round(sum(u.usage_quantity * lp.pricing.effective_list.default), 2) AS list_cost_usd,
          round(sum(CASE WHEN u.usage_date >= date_trunc('MONTH', current_date())
                         THEN u.usage_quantity * lp.pricing.effective_list.default END), 2) AS mtd_cost_usd,
          round(avg_daily, 2) AS avg_daily_usd
        FROM {_PRICED}
        CROSS JOIN (
          SELECT sum(u2.usage_quantity * lp2.pricing.effective_list.default) / {lookback_days} AS avg_daily
          FROM {_PRICED.replace('u.', 'u2.').replace('lp.', 'lp2.').replace(' u ', ' u2 ').replace(' lp ', ' lp2 ')}
          WHERE u2.usage_date >= current_date() - INTERVAL {lookback_days} DAYS
        )
        WHERE u.usage_date >= current_date() - INTERVAL {lookback_days} DAYS
        """
    )


def spend_by_product(lookback_days: int = 30):
    return run_sql(
        f"""
        SELECT u.billing_origin_product AS product,
               round(sum(u.usage_quantity * lp.pricing.effective_list.default), 2) AS list_cost_usd
        FROM {_PRICED}
        WHERE u.usage_date >= current_date() - INTERVAL {lookback_days} DAYS
        GROUP BY product ORDER BY list_cost_usd DESC
        """
    )


def tagging_coverage(tag_key: str = "cost_center", lookback_days: int = 30):
    return run_sql(
        f"""
        SELECT CASE WHEN u.custom_tags['{tag_key}'] IS NULL OR u.custom_tags['{tag_key}'] = ''
                    THEN 'untagged' ELSE 'tagged' END AS status,
               round(sum(u.usage_quantity * lp.pricing.effective_list.default), 2) AS list_cost_usd
        FROM {_PRICED}
        WHERE u.usage_date >= current_date() - INTERVAL {lookback_days} DAYS
        GROUP BY status
        """
    )


def spend_by_tag(tag_key: str = "cost_center", lookback_days: int = 30):
    return run_sql(
        f"""
        SELECT coalesce(u.custom_tags['{tag_key}'], '(untagged)') AS tag_value,
               round(sum(u.usage_quantity * lp.pricing.effective_list.default), 2) AS list_cost_usd
        FROM {_PRICED}
        WHERE u.usage_date >= current_date() - INTERVAL {lookback_days} DAYS
        GROUP BY tag_value ORDER BY list_cost_usd DESC
        """
    )


# ---- AI pillar ------------------------------------------------------------
def ai_spend(lookback_days: int = 30):
    return run_sql(
        f"""
        SELECT u.billing_origin_product AS product,
               round(sum(u.usage_quantity * lp.pricing.effective_list.default), 2) AS list_cost_usd
        FROM {_PRICED}
        WHERE u.usage_date >= current_date() - INTERVAL {lookback_days} DAYS
          AND (lower(u.billing_origin_product) LIKE '%serving%'
            OR lower(u.billing_origin_product) LIKE '%model%'
            OR lower(u.billing_origin_product) LIKE '%gpu%')
        GROUP BY product ORDER BY list_cost_usd DESC
        """
    )


# ---- DATA pillar ----------------------------------------------------------
def recent_audit(days: int = 7, limit: int = 200):
    return run_sql(
        f"""
        SELECT event_time, user_identity.email AS user_email, service_name,
               action_name, source_ip_address
        FROM system.access.audit
        WHERE event_date >= current_date() - INTERVAL {days} DAYS
        ORDER BY event_time DESC LIMIT {limit}
        """
    )


def access_summary(limit: int = 200):
    """Grants across UC securables (who can do what)."""
    return run_sql(
        f"""
        SELECT grantee, table_catalog, table_schema, table_name, privilege_type
        FROM system.information_schema.table_privileges
        ORDER BY grantee LIMIT {limit}
        """
    )
