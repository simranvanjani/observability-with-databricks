"""Auth & connection helpers.

The app authenticates in two layers:

* **Service principal (default)** — inside a Databricks App, ``WorkspaceClient()``
  auto-configures from the injected app credentials.
* **On-behalf-of (OBO) user** — when the app is deployed with *user authorization*
  scopes, each request carries the caller's token in the
  ``X-Forwarded-Access-Token`` header. Using it means every WRITE respects the
  operator's own permissions, so the app is never a privilege-escalation path.

Read paths (system tables) go through a SQL warehouse via the SQL connector.
"""
from __future__ import annotations

import os
from functools import lru_cache

from databricks.sdk import WorkspaceClient


def _forwarded_user_token() -> str | None:
    """Return the caller's OBO token if the app was granted user authorization."""
    try:
        import streamlit as st  # lazy: keeps pure logic importable without streamlit

        headers = st.context.headers  # available in Streamlit >= 1.37
        return headers.get("X-Forwarded-Access-Token")
    except Exception:
        return None


def get_workspace_client() -> WorkspaceClient:
    """WorkspaceClient acting as the logged-in operator when possible.

    Falls back to the app service principal (still governed by that SP's grants)
    when no forwarded user token is present, e.g. during local development.
    """
    token = _forwarded_user_token()
    if token:
        host = os.environ.get("DATABRICKS_HOST") or _client_host()
        return WorkspaceClient(host=host, token=token)
    return WorkspaceClient()  # SP creds from the app environment / local profile


@lru_cache(maxsize=1)
def _client_host() -> str | None:
    try:
        return WorkspaceClient().config.host
    except Exception:
        return os.environ.get("DATABRICKS_HOST")


def get_warehouse_id() -> str | None:
    return os.environ.get("DATABRICKS_WAREHOUSE_ID") or None


def sql_connection():
    """Return a databricks-sql-connector connection to the configured warehouse.

    Uses the OBO user token when available so reads honor the operator's grants
    on the ``system`` schemas.
    """
    from databricks import sql as dbsql

    warehouse_id = get_warehouse_id()
    if not warehouse_id:
        raise RuntimeError(
            "DATABRICKS_WAREHOUSE_ID is not set. Configure it in the app env "
            "(app.yaml) or deployment settings."
        )
    host = (_client_host() or "").replace("https://", "").rstrip("/")
    token = _forwarded_user_token() or get_workspace_client().config.token
    return dbsql.connect(
        server_hostname=host,
        http_path=f"/sql/1.0/warehouses/{warehouse_id}",
        access_token=token,
    )


def run_sql(query: str, params: dict | None = None):
    """Execute a read query and return a pandas DataFrame."""
    import pandas as pd

    with sql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or {})
            cols = [c[0] for c in cur.description] if cur.description else []
            rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)
