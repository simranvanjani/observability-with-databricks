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
        # auth_type="pat" forces token auth. Without it the SDK also sees the
        # app's DATABRICKS_CLIENT_ID/SECRET (OAuth-M2M) and errors on ambiguous
        # ("cannot configure default credentials") auth.
        host = os.environ.get("DATABRICKS_HOST") or _client_host()
        return WorkspaceClient(host=host, token=token, auth_type="pat")
    return WorkspaceClient()  # SP creds from the app environment / local profile


@lru_cache(maxsize=1)
def _client_host() -> str | None:
    try:
        return WorkspaceClient().config.host
    except Exception:
        return os.environ.get("DATABRICKS_HOST")


def get_warehouse_id() -> str | None:
    return os.environ.get("DATABRICKS_WAREHOUSE_ID") or None


_NUMERIC_TYPES = {"DECIMAL", "DOUBLE", "FLOAT", "LONG", "INT", "SHORT", "BYTE", "BIGINT"}


def run_sql(query: str, params: dict | None = None):
    """Execute a statement via the SDK Statement Execution API → pandas DataFrame.

    Uses the SDK (already bundled with databricks-sdk) rather than
    databricks-sql-connector, so the app has no heavy native dependency to build
    at deploy time. Numeric columns are coerced from the string result payload.
    """
    import time

    import pandas as pd
    from databricks.sdk.service.sql import StatementState

    warehouse_id = get_warehouse_id()
    if not warehouse_id:
        raise RuntimeError(
            "DATABRICKS_WAREHOUSE_ID is not set. Configure it in the app env "
            "(app.yaml) or deployment settings."
        )

    w = get_workspace_client()
    resp = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id, statement=query, wait_timeout="50s")
    while resp.status and resp.status.state in (StatementState.PENDING, StatementState.RUNNING):
        time.sleep(1)
        resp = w.statement_execution.get_statement(resp.statement_id)

    if resp.status and resp.status.state != StatementState.SUCCEEDED:
        err = resp.status.error.message if resp.status.error else str(resp.status.state)
        raise RuntimeError(f"SQL failed: {err}")

    cols_meta = resp.manifest.schema.columns if (resp.manifest and resp.manifest.schema) else []
    names = [c.name for c in cols_meta]
    data = (resp.result.data_array if resp.result else None) or []
    df = pd.DataFrame(data, columns=names)
    for c in cols_meta:  # result payload is all strings; restore numeric dtypes
        tname = str(c.type_name).split(".")[-1].upper()
        if tname in _NUMERIC_TYPES and c.name in df.columns:
            df[c.name] = pd.to_numeric(df[c.name], errors="coerce")
    return df
